"""Installed acceptance checks URLs in the configured public mount."""

from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

import pytest

from scripts.check_installed_artifacts import _check_link, validate_site


def _site(output: Path, base_url: str) -> None:
    prefix = urlsplit(base_url).path.rstrip("/")
    for name, content in {
        "index.html": (
            f'<a href="{prefix}/about/">About</a>'
            f'<link href="{prefix}/feed.xml" rel="alternate">'
            f'<link href="{prefix}/static/style.css" rel="stylesheet">'
            '<a href="about/">Relative about</a>'
        ),
        "about/index.html": '<a href="../">Home</a>',
        "posts/entry/index.html": '<img src="../../static/image.svg">',
        "static/style.css": "body { margin: 0; }",
        "static/image.svg": '<svg xmlns="http://www.w3.org/2000/svg"/>',
        "feed.xml": (
            '<rss xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f"<link>{base_url}</link>"
            f'<atom:link href="{base_url}/feed.xml"/>'
            f"<item><link>{base_url}/posts/entry/</link>"
            f'<guid isPermaLink="true">{base_url}/posts/entry/</guid>'
            "</item></channel></rss>"
        ),
        "sitemap.xml": (
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{base_url}/</loc></url>"
            f"<url><loc>{base_url}/posts/entry/</loc></url></urlset>"
        ),
    }.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.com",
        "https://blog.example.test/blog",
        "https://example.com:8443/nested/blog",
        "https://example.com/%E6%97%A5%E6%9C%AC%E8%AA%9E/blog",
    ],
)
def test_validation_accepts_root_nested_and_encoded_mounts(tmp_path, base_url):
    _site(tmp_path, base_url)
    validate_site(tmp_path, base_url)


def test_relative_links_resolve_from_the_public_document_url(tmp_path):
    base_url = "https://example.com/nested/blog"
    _site(tmp_path, base_url)
    assert _check_link(
        tmp_path,
        tmp_path / "posts/entry/index.html",
        "../../static/style.css?version=1#ignored",
        base_url,
    ) == ("/nested/blog/static/style.css?version=1", tmp_path / "static/style.css")
    assert _check_link(tmp_path, tmp_path / "index.html", "about", base_url) == (
        "/nested/blog/about",
        tmp_path / "about/index.html",
    )


@pytest.mark.parametrize(
    "link",
    [
        "/about/",
        "/nested/about/",
        "/nested/blog-outside/about/",
        "https://example.com/about/",
        "../../../about/",
    ],
)
def test_missing_prefix_and_relative_mount_escape_are_rejected(tmp_path, link):
    base_url = "https://example.com/nested/blog"
    _site(tmp_path, base_url)
    with pytest.raises(RuntimeError, match="configured URL prefix"):
        _check_link(tmp_path, tmp_path / "posts/entry/index.html", link, base_url)


def test_unintentionally_doubled_prefix_is_a_missing_target(tmp_path):
    _site(tmp_path, "https://example.com/blog")
    with pytest.raises(RuntimeError, match="broken local link"):
        _check_link(
            tmp_path,
            tmp_path / "index.html",
            "/blog/blog/about/",
            "https://example.com/blog",
        )


def test_route_named_like_mount_is_not_mistaken_for_a_doubled_prefix(tmp_path):
    _site(tmp_path, "https://example.com/blog")
    (tmp_path / "blog").mkdir()
    destination = tmp_path / "blog/index.html"
    destination.write_text("<p>A real page named blog</p>", encoding="utf-8")
    assert _check_link(
        tmp_path, tmp_path / "index.html", "/blog/blog/", "https://example.com/blog"
    ) == ("/blog/blog/", destination)


@pytest.mark.parametrize(
    "link", ["/blog/%2e%2e/outside.html", "/blog/..%2Foutside.html"]
)
def test_encoded_parent_paths_cannot_escape_output(tmp_path, link):
    output = tmp_path / "site"
    _site(output, "https://example.com/blog")
    (tmp_path / "outside.html").write_text("Outside", encoding="utf-8")
    with pytest.raises(RuntimeError, match="escapes output"):
        _check_link(output, output / "index.html", link, "https://example.com/blog")


def test_symlinked_file_cannot_escape_output(tmp_path):
    output = tmp_path / "site"
    _site(output, "https://example.com/blog")
    outside = tmp_path / "outside.html"
    outside.write_text("Outside", encoding="utf-8")
    (output / "outside.html").symlink_to(outside)
    with pytest.raises(RuntimeError, match="escapes output"):
        _check_link(
            output,
            output / "index.html",
            "/blog/outside.html",
            "https://example.com/blog",
        )


def test_mount_and_reserved_route_characters_are_decoded_once(tmp_path):
    base_url = "https://example.com/%E6%97%A5%E6%9C%AC%E8%AA%9E/blog"
    _site(tmp_path, base_url)
    destination = tmp_path / "topic#?%20/index.html"
    destination.parent.mkdir()
    destination.write_text("Topic", encoding="utf-8")
    public_path = urlsplit(base_url).path + "/" + quote("topic#?%20", safe="") + "/"
    assert _check_link(tmp_path, tmp_path / "index.html", public_path, base_url) == (
        public_path,
        destination,
    )


@pytest.mark.parametrize(
    "link",
    [
        "https://elsewhere.example/path",
        "//elsewhere.example/path",
        "http://example.com/other-origin",
        "https://example.com:8443/other-origin",
        "mailto:author@example.com",
        "data:image/svg+xml,example",
        "#section",
        "?version=1",
    ],
)
def test_authored_external_links_and_document_references_are_not_local_files(
    tmp_path, link
):
    _site(tmp_path, "https://example.com/blog")
    assert (
        _check_link(tmp_path, tmp_path / "index.html", link, "https://example.com/blog")
        is None
    )


@pytest.mark.parametrize(
    ("document", "selector", "attribute"),
    [
        ("feed.xml", "./channel/link", None),
        ("feed.xml", "./channel/item/link", None),
        ("feed.xml", "./channel/item/guid", None),
        ("feed.xml", "./channel/{http://www.w3.org/2005/Atom}link", "href"),
        ("sitemap.xml", "{*}url/{*}loc", None),
    ],
)
@pytest.mark.parametrize(
    "link",
    [
        "http://example.com/blog/",
        "https://example.com:8443/blog/",
        "https://example.com:0/blog/",
        "https://elsewhere.example/blog/",
        "//example.com/blog/",
        "/blog/",
        "",
    ],
)
def test_machine_owned_xml_urls_require_the_configured_origin(
    tmp_path, document, selector, attribute, link
):
    base_url = "https://example.com/blog"
    _site(tmp_path, base_url)
    path = tmp_path / document
    tree = ElementTree.parse(path)
    element = tree.find(selector)
    assert element is not None
    if attribute:
        element.set(attribute, link)
    else:
        element.text = link
    tree.write(path, encoding="utf-8")
    with pytest.raises(RuntimeError, match="configured site origin"):
        validate_site(tmp_path, base_url)


def test_xml_urls_with_missing_or_repeated_prefix_fail(tmp_path):
    base_url = "https://example.com/blog"
    _site(tmp_path, base_url)
    path = tmp_path / "sitemap.xml"
    original = path.read_text(encoding="utf-8")
    for replacement, message in [
        ("https://example.com/posts/entry/", "configured URL prefix"),
        ("https://example.com/blog/blog/posts/entry/", "broken local link"),
        ("https://example.com/blog/missing/", "broken local link"),
    ]:
        path.write_text(
            original.replace(base_url + "/posts/entry/", replacement), encoding="utf-8"
        )
        with pytest.raises(RuntimeError, match=message):
            validate_site(tmp_path, base_url)


def test_non_permalink_rss_guid_is_not_interpreted_as_a_url(tmp_path):
    base_url = "https://example.com/blog"
    _site(tmp_path, base_url)
    path = tmp_path / "feed.xml"
    tree = ElementTree.parse(path)
    element = tree.find("./channel/item/guid")
    assert element is not None
    element.set("isPermaLink", "false")
    element.text = "post-identity"
    tree.write(path, encoding="utf-8")
    validate_site(tmp_path, base_url)
