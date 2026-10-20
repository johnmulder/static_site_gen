"""Prefix configuration and generated routes share one public mount path."""

from argparse import Namespace
from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

import pytest
import yaml

from static_site_gen.cli import cmd_build, cmd_init
from static_site_gen.generator.core import SiteConfig, SiteGenerator
from static_site_gen.generator.renderer import TemplateRenderer


def configure(project, base_url):
    path = project / "config.yaml"
    settings = yaml.safe_load(path.read_text(encoding="utf-8"))
    settings.update(base_url=base_url, posts_per_page=1)
    path.write_text(yaml.safe_dump(settings), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.com/blog", "https://example.com/blog"),
        ("HTTPS://EXAMPLE.COM/blog/", "https://example.com/blog"),
        ("https://example.com/nested/blog/", "https://example.com/nested/blog"),
        ("http://localhost:8000/blog/", "http://localhost:8000/blog"),
        (
            "https://example.com/日本語/",
            "https://example.com/%E6%97%A5%E6%9C%AC%E8%AA%9E",
        ),
        ("https://example.com/%62log/", "https://example.com/blog"),
        ("https://example.com/my%20blog/", "https://example.com/my%20blog"),
        ("https://example.com/%e6%97%a5/", "https://example.com/%E6%97%A5"),
        ("https://example.com/%23%3f%25/", "https://example.com/%23%3F%25"),
    ],
)
def test_config_canonicalizes_prefix(sample_project, url, expected):
    config = SiteConfig.from_yaml(configure(sample_project, url))
    assert config.base_url == expected
    assert config.url_prefix == urlsplit(expected).path


@pytest.mark.parametrize(
    "prefix",
    [
        "//",
        "/blog//",
        "/blog//child",
        "/./",
        "/../",
        "/blog/../child",
        "/%2e/",
        "/%2E%2E/",
        "/blog%2fchild/",
        "/blog%5Cchild/",
        "/bad%/",
        "/bad%0/",
        "/bad%zz/",
        "/%FF/",
        "/%C0%AF/",
        "/%00/",
        "/%0A/",
        "/%7F/",
        "/%20blog/",
        "/blog%20/",
        "/blog;params/",
        "/%3Bparams/",
        "/\ud800/",
    ],
)
def test_invalid_prefix_preserves_published_site(sample_project, capsys, prefix):
    SiteGenerator(sample_project).build()
    site = sample_project / "site"
    before = {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    }
    configure(sample_project, "https://example.com" + prefix)
    assert cmd_build(Namespace(project_dir=str(sample_project), drafts=False)) == 1
    assert "base_url" in capsys.readouterr().out
    assert {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    } == before
    assert not list(sample_project.glob(".site-build-*"))


@pytest.mark.parametrize("template_source", ["project", "packaged"])
@pytest.mark.parametrize("prefix", ["", "/blog", "/nested/日本語"])
def test_all_generated_route_families_use_prefix(
    sample_project, tmp_path, template_source, prefix
):
    project = sample_project
    if template_source == "packaged":
        project = tmp_path / "packaged"
        assert cmd_init(Namespace(project_name=str(project))) == 0
    for path in (project / "content").rglob("*.md"):
        path.unlink()
    configure(project, "https://example.com" + prefix + "/")
    slug = "日本語#?%20/part"
    tag = "tag-" + slug
    for filename, post_slug, day in [
        ("first", slug, 19),
        ("second", "second", 18),
        ("third", "third", 17),
    ]:
        metadata = {
            "title": filename,
            "date": f"2026-10-{day}",
            "slug": post_slug,
            "tags": [tag],
        }
        (project / f"content/posts/{filename}.md").write_text(
            "---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\nBody.\n",
            encoding="utf-8",
        )
    (project / "content/pages/about.md").write_text(
        "---\ntitle: About\ndate: 2026-10-19\n---\nAbout.\n", encoding="utf-8"
    )
    SiteGenerator(project).build()
    mount = quote(prefix, safe="/")
    site = project / "site"
    expected_post = mount + "/posts/" + quote(slug, safe="") + "/"
    expected_tag = mount + "/tag/" + quote(tag, safe="") + "/"
    homepage = (site / "index.html").read_text(encoding="utf-8")
    for route in [
        "/",
        "/static/style.css",
        "/feed.xml",
        "/about/",
        "/tag/",
        "/page/2/",
    ]:
        assert f'href="{mount}{route}"' in homepage
    assert f'href="{expected_post}"' in homepage
    assert f'href="{expected_tag}"' in homepage
    second = (site / "page/2/index.html").read_text(encoding="utf-8")
    assert f'href="{mount}/" class="pagination-link"' in second
    assert f'href="{mount}/page/3/"' in second
    third = (site / "page/3/index.html").read_text(encoding="utf-8")
    assert f'href="{mount}/page/2/" class="pagination-link"' in third
    assert f'href="{expected_tag}"' in (site / "posts" / slug / "index.html").read_text(
        encoding="utf-8"
    )
    assert f'href="{expected_tag}"' in (site / "tag/index.html").read_text(
        encoding="utf-8"
    )
    assert f'href="{expected_post}"' in (site / "tag" / tag / "index.html").read_text(
        encoding="utf-8"
    )
    assert (site / "about/index.html").is_file()
    if prefix:
        assert not (site / prefix.lstrip("/")).exists()
    feed = ElementTree.parse(site / "feed.xml")
    assert feed.findtext("./channel/link") == "https://example.com" + mount
    assert feed.findtext("./channel/item/link") == "https://example.com" + expected_post
    assert feed.findtext("./channel/item/guid") == "https://example.com" + expected_post
    atom_link = feed.find("./channel/{http://www.w3.org/2005/Atom}link")
    assert atom_link is not None
    assert atom_link.get("href") == "https://example.com" + mount + "/feed.xml"
    sitemap = ElementTree.parse(site / "sitemap.xml")
    urls = [element.text for element in sitemap.findall("{*}url/{*}loc")]
    assert "https://example.com" + mount + "/" in urls
    assert "https://example.com" + expected_post in urls
    assert "https://example.com" + expected_tag in urls
    assert "https://example.com" + mount + "/about/" in urls


def test_site_url_filter_uses_each_render_context(tmp_path):
    (tmp_path / "link.html").write_text(
        '{{ "/about/?view=all#top" | site_url }}', encoding="utf-8"
    )
    renderer = TemplateRenderer(tmp_path)
    for prefix in ["/blog", "/blog/", "", "/", "/second"]:
        config = SiteConfig("Test", "https://example.com" + prefix, "Author")
        assert (
            renderer.render_template("link.html", {"site": config})
            == prefix.removesuffix("/") + "/about/?view=all#top"
        )


def test_authored_links_are_preserved(sample_project):
    configure(sample_project, "https://example.com/blog/")
    content = """---
title: Authored links
date: 2026-10-19
---
[Relative](../../about/) and [Root](/about/) and [External](https://other.example/).
"""
    (sample_project / "content/posts/links.md").write_text(content, encoding="utf-8")
    SiteGenerator(sample_project).build()
    page = (sample_project / "site/posts/authored-links/index.html").read_text(
        encoding="utf-8"
    )
    assert '<a href="../../about/">Relative</a>' in page
    assert '<a href="/about/">Root</a>' in page
    assert '<a href="https://other.example/">External</a>' in page


@pytest.mark.parametrize(
    "path", ["https://example.com/", "//example.com/", "about/", ""]
)
def test_site_url_requires_root_relative_path(tmp_path, path):
    (tmp_path / "link.html").write_text("{{ route | site_url }}", encoding="utf-8")
    renderer = TemplateRenderer(tmp_path)
    with pytest.raises(ValueError, match="root-relative"):
        renderer.render_template(
            "link.html",
            {
                "route": path,
                "site": SiteConfig("Test", "https://example.com/blog", "Author"),
            },
        )


def test_template_copies_remain_identical():
    root = Path(__file__).resolve().parents[1]
    for template in (root / "templates").iterdir():
        assert (
            template.read_bytes()
            == (
                root / "static_site_gen/resources/templates" / template.name
            ).read_bytes()
        )
