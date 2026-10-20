"""Release regressions for the supported domain-root URL contract."""

from argparse import Namespace
from xml.etree import ElementTree

import pytest
import yaml

from static_site_gen.cli import cmd_build
from static_site_gen.generator.core import SiteConfig, SiteGenerator


def set_base_url(project, base_url):
    config = project / "config.yaml"
    settings = yaml.safe_load(config.read_text())
    settings["base_url"] = base_url
    config.write_text(yaml.safe_dump(settings))
    return config


@pytest.mark.parametrize(
    "base_url, expected",
    [
        ("https://example.com", "https://example.com"),
        ("https://example.com/", "https://example.com"),
        ("HTTPS://EXAMPLE.COM/", "https://example.com"),
        ("http://localhost:8080/", "http://localhost:8080"),
        ("http://[::1]:8080/", "http://[::1]:8080"),
    ],
)
def test_root_urls_have_consistent_feed_and_sitemap(sample_project, base_url, expected):
    config = set_base_url(sample_project, base_url)
    assert SiteConfig.from_yaml(config).base_url == expected

    SiteGenerator(sample_project).build()

    site = sample_project / "site"
    assert ElementTree.parse(site / "feed.xml").findtext("./channel/link") == expected
    assert (
        ElementTree.parse(site / "sitemap.xml").findtext("{*}url/{*}loc")
        == expected + "/"
    )
    assert 'href="/static/style.css"' in (site / "index.html").read_text()


@pytest.mark.parametrize(
    "base_url, error",
    [
        ("https://example.com//", "unsafe path prefix"),
        ("https://example.com/;params", "unsafe path prefix"),
        ("https://example.com?search=term", "query string or fragment"),
        ("https://example.com/#section", "query string or fragment"),
        ("https://example.com?", "query string or fragment"),
        ("https://user:password@example.com", "credentials"),
        ("https://user@example.com", "credentials"),
        ("https://example.com:invalid", "valid absolute HTTP/HTTPS"),
        ("https://[invalid]", "valid absolute HTTP/HTTPS"),
        ("https://bad host", "valid absolute HTTP/HTTPS"),
        ("https://bad\x00host", "valid absolute HTTP/HTTPS"),
        ("https://example.com\\bad", "valid absolute HTTP/HTTPS"),
    ],
)
def test_unsupported_urls_fail_without_changing_output(
    sample_project, capsys, base_url, error
):
    SiteGenerator(sample_project).build()
    site = sample_project / "site"
    before = {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    }
    set_base_url(sample_project, base_url)

    assert cmd_build(Namespace(project_dir=str(sample_project), drafts=False)) == 1

    assert error in capsys.readouterr().out
    assert {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    } == before
