"""Release acceptance rejects mismatched packages and unresolved generated links."""

import zipfile

import pytest

from scripts.check_installed_artifacts import (
    TEMPLATES,
    inspect_artifact,
    validate_site,
)


def _wheel(
    tmp_path,
    *,
    missing=None,
    version="0.1.0a1",
    license_name="MIT",
    license_content="MIT License\nPermission is hereby granted",
    template="template",
):
    artifact = tmp_path / "static_site_gen.whl"
    files = {
        "static_site_gen/__init__.py": "",
        "static_site_gen/__main__.py": "",
        "static_site_gen/cli.py": "",
        "static_site_gen-0.1.0a1.dist-info/licenses/LICENSE": license_content,
        "static_site_gen-0.1.0a1.dist-info/METADATA": (
            "Metadata-Version: 2.4\nName: static-site-gen\n"
            f"Version: {version}\nLicense-Expression: {license_name}\n"
        ),
        **{
            f"static_site_gen/resources/templates/{name}": template
            for name in TEMPLATES
        },
    }
    files.pop(missing, None)
    with zipfile.ZipFile(artifact, "w") as wheel:
        for name, content in files.items():
            wheel.writestr(name, content)
    return artifact


def test_distribution_version_must_match_selected_candidate(tmp_path):
    artifact = _wheel(tmp_path)
    assert inspect_artifact(artifact, "0.1.0a1") == "0.1.0a1"
    with pytest.raises(RuntimeError, match="unexpected version"):
        inspect_artifact(artifact, "0.1.0a2")


@pytest.mark.parametrize(
    "missing",
    [
        "static_site_gen/resources/templates/feed.xml",
        "static_site_gen-0.1.0a1.dist-info/licenses/LICENSE",
    ],
)
def test_distribution_requires_templates_and_license(tmp_path, missing):
    with pytest.raises(RuntimeError, match="missing"):
        inspect_artifact(_wheel(tmp_path, missing=missing))


def test_distribution_requires_expected_license_metadata(tmp_path):
    with pytest.raises(RuntimeError, match="license metadata"):
        inspect_artifact(_wheel(tmp_path, license_name="unknown"))


def test_distribution_rejects_empty_templates(tmp_path):
    with pytest.raises(RuntimeError, match="empty template"):
        inspect_artifact(_wheel(tmp_path, template=""))


def test_distribution_rejects_incorrect_license_contents(tmp_path):
    with pytest.raises(RuntimeError, match="incorrect MIT license contents"):
        inspect_artifact(_wheel(tmp_path, license_content="incorrect"))


def test_site_validation_resolves_reserved_characters_and_checks_xml(tmp_path):
    (tmp_path / "topic#?%20").mkdir()
    (tmp_path / "topic#?%20/index.html").write_text("<p>Content</p>")
    (tmp_path / "index.html").write_text(
        '<a href="/topic%23%3F%2520/">Topic</a>'
        '<a href="https://elsewhere.example/path">External</a>'
        '<a href="#section">Anchor</a>'
    )
    (tmp_path / "feed.xml").write_text("<rss><channel/></rss>")
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/topic%23%3F%2520/</loc></url></urlset>"
    )
    validate_site(tmp_path)
    (tmp_path / "topic#?%20/index.html").unlink()
    with pytest.raises(RuntimeError, match="broken local link"):
        validate_site(tmp_path)


def test_site_validation_rejects_wrong_xml_root(tmp_path):
    (tmp_path / "feed.xml").write_text("<html/>")
    with pytest.raises(RuntimeError, match="RSS channel"):
        validate_site(tmp_path)
