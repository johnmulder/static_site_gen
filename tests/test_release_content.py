"""Release regressions for content validation and Markdown setup."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from static_site_gen.cli import cmd_build
from static_site_gen.generator.core import SiteGenerator
from static_site_gen.generator.parser import ParseError, parse_content_file


def set_extensions(project, extensions):
    config = project / "config.yaml"
    settings = yaml.safe_load(config.read_text())
    if extensions is None:
        settings.pop("markdown_extensions", None)
    else:
        settings["markdown_extensions"] = extensions
    config.write_text(yaml.safe_dump(settings))


@pytest.mark.parametrize("extensions", [[""], [" "], ["missing_release_extension_123"]])
def test_bad_extension_setup_preserves_previous_site(
    sample_project, capsys, extensions
):
    generator = SiteGenerator(sample_project)
    generator.build()
    site = sample_project / "site"
    before = {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    }
    set_extensions(sample_project, extensions)

    with patch.object(SiteGenerator, "discover_content") as discover:
        assert cmd_build(Namespace(project_dir=str(sample_project), drafts=False)) == 1

    discover.assert_not_called()
    assert "Configuration error:" in capsys.readouterr().out
    assert {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    } == before


def test_extension_initialization_exception_is_a_controlled_failure(
    sample_project, capsys
):
    with patch(
        "static_site_gen.generator.core.markdown.Markdown",
        side_effect=RuntimeError("extension failed to initialize"),
    ):
        assert cmd_build(Namespace(project_dir=str(sample_project), drafts=False)) == 1

    assert "extension failed to initialize" in capsys.readouterr().out
    assert not (sample_project / "site").exists()


@pytest.mark.parametrize(
    "extensions, expected_table", [(None, True), ([], False), (["tables"], True)]
)
def test_omitted_and_empty_extension_configuration_differ(
    sample_project, extensions, expected_table
):
    set_extensions(sample_project, extensions)
    path = sample_project / "content/posts/table.md"
    path.write_text(
        "---\ntitle: Table\ndate: 2025-10-17\n---\n"
        "| Left | Right |\n| ---- | ----- |\n| one | two |\n"
    )

    SiteGenerator(sample_project).build()

    html = (sample_project / "site/posts/table/index.html").read_text()
    assert ("<table>" in html) is expected_table


def test_standalone_parser_empty_extensions_disable_optional_features(tmp_path):
    path = tmp_path / "table.md"
    path.write_text(
        "---\ntitle: Table\ndate: 2025-10-17\n---\n"
        "| Left | Right |\n| ---- | ----- |\n| one | two |\n"
    )

    assert "<table>" in parse_content_file(path).content
    assert "<table>" not in parse_content_file(path, []).content


@pytest.mark.parametrize("field", ["slug", "tags"])
@pytest.mark.parametrize(
    "value",
    ["..", ".", "bad\\route", "bad\x00route", "leading /segment", "a/ b", "a" * 256],
)
def test_malformed_route_metadata_is_logged_and_skipped(
    sample_project, caplog, field, value
):
    metadata: dict[str, object] = {"title": "Invalid", "date": "2025-10-17"}
    metadata[field] = [value] if field == "tags" else value
    invalid = sample_project / "content/posts/invalid.md"
    invalid.write_text("---\n" + yaml.safe_dump(metadata) + "---\nInvalid body.")
    valid = sample_project / "content/posts/valid.md"
    valid.write_text("---\ntitle: Valid\ndate: 2025-10-17\n---\nValid body.")

    with pytest.raises(ParseError) as error:
        parse_content_file(invalid)
    assert str(invalid) in str(error.value)

    SiteGenerator(sample_project).build()

    assert (sample_project / "site/posts/valid/index.html").is_file()
    assert "Invalid body" not in (sample_project / "site/index.html").read_text()
    assert str(invalid) in caplog.text
    assert "Error processing post" in caplog.text


def test_duplicate_normalized_tags_count_post_once(sample_project):
    metadata = {
        "title": "One post",
        "date": "2025-10-17",
        "tags": ["Python", " python ", "Testing", "PYTHON"],
    }
    path = sample_project / "content/posts/post.md"
    path.write_text("---\n" + yaml.safe_dump(metadata) + "---\nBody.")

    assert parse_content_file(path).metadata.tags == ["python", "testing"]
    SiteGenerator(sample_project).build()

    site = sample_project / "site"
    assert (site / "tag/python/index.html").read_text().count('class="post-item"') == 1
    assert "python (1)" in (site / "tag/index.html").read_text()


def test_backup_cleanup_failure_reports_successful_publication(
    sample_project, monkeypatch, caplog
):
    from static_site_gen.generator import output

    generator = SiteGenerator(sample_project)
    generator.build()
    previous = (sample_project / "site/index.html").read_bytes()
    path = sample_project / "content/posts/new.md"
    path.write_text("---\ntitle: Newly published\ndate: 2025-10-17\n---\nNew body.")
    remove = output.shutil.rmtree

    def fail_backup_cleanup(path, *args, **kwargs):
        if Path(path).name.startswith(".site-previous-"):
            raise PermissionError("cleanup denied")
        return remove(path, *args, **kwargs)

    monkeypatch.setattr(output.shutil, "rmtree", fail_backup_cleanup)

    assert cmd_build(Namespace(project_dir=str(sample_project), drafts=False)) == 0

    assert "Newly published" in (sample_project / "site/index.html").read_text()
    backups = list(sample_project.glob(".site-previous-*"))
    assert len(backups) == 1
    assert (backups[0] / "index.html").read_bytes() == previous
    assert "New site published" in caplog.text
    assert str(backups[0]) in caplog.text
