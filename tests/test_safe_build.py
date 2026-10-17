"""Regression checks for source protection and publishing complete builds."""

from argparse import Namespace
from pathlib import Path
from stat import S_IMODE
from unittest.mock import patch

import pytest
from jinja2 import TemplateSyntaxError

from static_site_gen.cli import cmd_build, cmd_init
from static_site_gen.generator.core import SiteGenerator
from static_site_gen.generator.output import publish_output


def init_project(root: Path) -> Path:
    project = root / "blog"
    assert cmd_init(Namespace(project_name=str(project))) == 0
    return project


def set_output(project: Path, output: str) -> None:
    config = project / "config.yaml"
    config.write_text(
        config.read_text().replace('output_dir: "site"', f'output_dir: "{output}"')
    )


@pytest.mark.parametrize(
    "output",
    [
        ".",
        "..",
        "content",
        "content/published",
        "templates",
        "templates/site",
        "static",
        "static/site",
        "config.yaml",
        ".git",
        ".git/site",
    ],
)
def test_build_rejects_source_overlap_before_mutating(tmp_path, output):
    project = init_project(tmp_path)
    sentinel = project / "sentinel.txt"
    sentinel.write_text("source evidence")
    set_output(project, output)
    before = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }

    assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1

    assert {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.parametrize("target", ["root", "content", "outside"])
def test_build_resolves_output_symlinks_before_mutating(tmp_path, target):
    project = init_project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("outside evidence")
    destination = {"root": project, "content": project / "content", "outside": outside}[
        target
    ]
    (project / "output-link").symlink_to(destination, target_is_directory=True)
    set_output(project, "output-link")

    assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1
    assert (project / "config.yaml").exists()
    assert (project / "content/posts").is_dir()
    assert sentinel.read_text() == "outside evidence"


def test_build_rejects_an_ancestor_of_a_resolved_source(tmp_path):
    project = init_project(tmp_path)
    (project / "sources").mkdir()
    (project / "content").rename(project / "sources/content")
    (project / "content").symlink_to(
        project / "sources/content", target_is_directory=True
    )
    set_output(project, "sources")

    assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1
    assert (project / "sources/content/posts").is_dir()


@pytest.mark.parametrize(
    "marker", [".bash_profile", ".bashrc", ".zshrc", "Desktop", "Documents"]
)
def test_build_preserves_output_containing_user_files(tmp_path, marker):
    project = init_project(tmp_path)
    output = project / "site"
    output.mkdir()
    evidence = output / marker
    if marker in {"Desktop", "Documents"}:
        evidence.mkdir()
        evidence = evidence / "sentinel.txt"
    evidence.write_text("user evidence")

    with patch(
        "static_site_gen.generator.core.SiteGenerator._generate_site"
    ) as generate:
        assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1

    generate.assert_not_called()
    assert evidence.read_text() == "user evidence"
    assert not list(project.glob(".site-build-*"))


def test_build_rechecks_user_files_before_publication(tmp_path):
    project = init_project(tmp_path)
    SiteGenerator(project).build()
    previous = (project / "site/index.html").read_bytes()
    generate = SiteGenerator._generate_site
    evidence = project / "site/.bashrc"

    def generate_with_user_file(generator, include_drafts):
        generate(generator, include_drafts)
        evidence.write_text("user evidence")

    with patch.object(SiteGenerator, "_generate_site", generate_with_user_file):
        assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1

    assert evidence.read_text() == "user evidence"
    assert (project / "site/index.html").read_bytes() == previous
    assert not list(project.glob(".site-build-*"))


def test_init_uses_packaged_templates_then_builds(tmp_path):
    with patch(
        "static_site_gen.cli.__file__",
        str(tmp_path / "installed/static_site_gen/cli.py"),
    ):
        project = init_project(tmp_path)
    assert (project / "templates/post.html").is_file()
    set_output(project, "artifacts/site")
    generator = SiteGenerator(project)
    generator.build()
    output = project / "artifacts/site"
    assert generator.output_dir == output
    assert (output / "index.html").is_file()
    assert (output / "posts/hello-world/index.html").is_file()
    assert (output / "about/index.html").is_file()
    assert (output / "feed.xml").is_file()


@pytest.mark.parametrize(
    "template",
    ["post.html", "tag.html", "tag_index.html", "feed.xml", "page.html", "sitemap.xml"],
)
def test_failed_render_keeps_previous_site_and_returns_nonzero(tmp_path, template):
    project = init_project(tmp_path)
    generator = SiteGenerator(project)
    generator.build()
    before = {
        path.relative_to(project / "site"): path.read_bytes()
        for path in (project / "site").rglob("*")
        if path.is_file()
    }
    (project / "templates" / template).unlink()

    assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1

    assert {
        path.relative_to(project / "site"): path.read_bytes()
        for path in (project / "site").rglob("*")
        if path.is_file()
    } == before
    assert not list(project.glob(".site-build-*"))


def test_failed_write_keeps_previous_site_and_returns_nonzero(tmp_path):
    project = init_project(tmp_path)
    SiteGenerator(project).build()
    previous = (project / "site/index.html").read_bytes()
    with patch(
        "static_site_gen.generator.core.write_file", side_effect=OSError("disk full")
    ):
        assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1
    assert (project / "site/index.html").read_bytes() == previous


def test_invalid_template_returns_nonzero_without_publishing(tmp_path):
    project = init_project(tmp_path)
    with patch(
        "static_site_gen.generator.renderer.TemplateRenderer.render_template",
        side_effect=TemplateSyntaxError("invalid", 1),
    ):
        assert cmd_build(Namespace(project_dir=str(project), drafts=False)) == 1
    assert not (project / "site").exists()


def test_publish_failure_restores_previous_output(tmp_path, monkeypatch):
    output = tmp_path / "site"
    staged = tmp_path / "staging"
    output.mkdir()
    staged.mkdir()
    (output / "index.html").write_text("previous")
    (staged / "index.html").write_text("new")
    replace = Path.replace

    def fail_publish(path, destination):
        if path == staged:
            raise OSError("publication failed")
        return replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_publish)
    with pytest.raises(OSError, match="publication failed"):
        publish_output(staged, output)
    assert (output / "index.html").read_text() == "previous"
    assert not list(tmp_path.glob(".site-previous-*"))


def test_successful_rebuild_replaces_output_without_stale_files(tmp_path):
    project = init_project(tmp_path)
    generator = SiteGenerator(project)
    generator.build()
    (project / "site/stale.html").write_text("stale")
    generator.build()
    assert not (project / "site/stale.html").exists()
    assert (project / "site/index.html").is_file()
    assert not list(project.glob(".site-previous-*"))


def test_new_output_uses_normal_directory_permissions(tmp_path):
    project = init_project(tmp_path)
    expected = tmp_path / "normal-directory"
    expected.mkdir()

    SiteGenerator(project).build()

    assert S_IMODE((project / "site").stat().st_mode) == S_IMODE(
        expected.stat().st_mode
    )


@pytest.mark.parametrize("mode", [0o755, 0o750, 0o700])
def test_rebuild_preserves_output_permissions(tmp_path, mode):
    project = init_project(tmp_path)
    generator = SiteGenerator(project)
    generator.build()
    output = project / "site"
    output.chmod(mode)
    expected = S_IMODE(output.stat().st_mode)

    generator.build()

    assert S_IMODE(output.stat().st_mode) == expected
