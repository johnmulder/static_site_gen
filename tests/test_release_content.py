"""Release regressions for content validation and Markdown setup."""

from argparse import Namespace
from unittest.mock import patch

import pytest
import yaml

from static_site_gen.cli import cmd_build
from static_site_gen.generator.core import SiteGenerator
from static_site_gen.generator.parser import parse_content_file


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
