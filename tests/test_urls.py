"""Generated links use the same encoded routes as their output files."""

from argparse import Namespace
from xml.etree import ElementTree

import pytest
import yaml
from markupsafe import escape

from static_site_gen.cli import cmd_init
from static_site_gen.generator.core import SiteGenerator
from static_site_gen.generator.output import (
    generate_page_url,
    generate_post_url,
    generate_tag_url,
)


@pytest.mark.parametrize("template_source", ["project", "packaged"])
@pytest.mark.parametrize(
    "slug",
    [
        "日本語",
        "topic#part",
        "topic?part",
        "topic%20part",
        "topic/part",
        'quote"&value',
    ],
)
def test_generated_urls_match_encoded_routes(
    sample_project, tmp_path, template_source, slug
):
    project = sample_project
    if template_source == "packaged":
        project = tmp_path / "packaged-site"
        assert cmd_init(Namespace(project_name=str(project))) == 0
        for path in (project / "content").rglob("*.md"):
            path.unlink()

    title = 'A <b>title</b> & "quotes"'
    description = '<img src=x onerror="alert(1)">'
    tag = f"tag-{slug}"
    metadata = {
        "title": title,
        "date": "2025-10-17",
        "slug": slug,
        "tags": [tag],
        "description": description,
    }
    content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\nBody.\n"
    (project / "content/posts/post.md").write_text(content, encoding="utf-8")
    (project / "content/pages/page.md").write_text(content, encoding="utf-8")

    generator = SiteGenerator(project)
    generator.build()
    site = project / "site"
    post_url = generate_post_url(slug)
    page_url = generate_page_url(slug)
    tag_url = generate_tag_url(tag)

    index = (site / "index.html").read_text(encoding="utf-8")
    post = (site / "posts" / slug / "index.html").read_text(encoding="utf-8")
    tag_page = (site / "tag" / tag / "index.html").read_text(encoding="utf-8")
    tag_index = (site / "tag/index.html").read_text(encoding="utf-8")
    assert f'href="{post_url}"' in index
    assert f'href="{post_url}"' in tag_page
    assert f'href="{tag_url}"' in index
    assert f'href="{tag_url}"' in post
    assert f'href="{tag_url}"' in tag_index
    assert (site / slug / "index.html").is_file()

    assert str(escape(title)) in index
    assert str(escape(description)) in index
    assert str(escape(tag)) in tag_index
    assert title not in index
    assert description not in index

    assert generator.config is not None
    base_url = generator.config.base_url
    feed = ElementTree.parse(site / "feed.xml")
    assert feed.findtext("./channel/item/link") == base_url + post_url
    assert feed.findtext("./channel/item/guid") == base_url + post_url
    assert feed.findtext("./channel/item/title") == title
    assert feed.findtext("./channel/item/description") == description

    sitemap = ElementTree.parse(site / "sitemap.xml")
    assert [url.text for url in sitemap.findall("{*}url/{*}loc")] == [
        base_url + "/",
        base_url + post_url,
        base_url + page_url,
        base_url + tag_url,
    ]
