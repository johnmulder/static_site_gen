"""Release regressions for output namespace ownership."""

from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from static_site_gen.cli import cmd_build
from static_site_gen.generator.core import SiteGenerator


def write_content(project: Path, kind: str, name: str, **fields: object) -> Path:
    """Write one content source with a predictable body."""
    metadata = {"title": name, "date": "2025-10-17", **fields}
    path = project / "content" / kind / f"{name}.md"
    path.write_text(
        "---\n" + yaml.safe_dump(metadata) + f"---\nBody for {name}.\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "slug, owner",
    [
        ("tag", "tag index"),
        ("posts/existing", "existing.md"),
        ("tag/topic", "existing.md"),
        ("static", "static assets"),
        ("static/custom", "static assets"),
        ("feed.xml", "RSS feed"),
        ("sitemap.xml", "sitemap"),
        ("page/2", "pagination page 2"),
        ("index.html/child", "homepage"),
    ],
)
def test_conflicting_page_preserves_previous_site(sample_project, capsys, slug, owner):
    write_content(sample_project, "posts", "existing", slug="existing", tags=["topic"])
    write_content(sample_project, "posts", "second", slug="second")
    config = sample_project / "config.yaml"
    settings = yaml.safe_load(config.read_text())
    settings["posts_per_page"] = 1
    config.write_text(yaml.safe_dump(settings))
    SiteGenerator(sample_project).build()
    site = sample_project / "site"
    before = {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    }
    conflict = write_content(sample_project, "pages", "conflicting", slug=slug)

    assert cmd_build(Namespace(project_dir=str(sample_project), drafts=False)) == 1

    diagnostic = capsys.readouterr().out
    assert "Output route conflict" in diagnostic
    assert str(conflict) in diagnostic
    assert owner in diagnostic
    assert slug.split("/")[0] in diagnostic
    assert {
        path.relative_to(site): path.read_bytes()
        for path in site.rglob("*")
        if path.is_file()
    } == before
    assert not list(sample_project.glob(".site-build-*"))


@pytest.mark.parametrize("slug", ["/", "/nested", "nested/", "nested//child"])
def test_ambiguous_route_is_skipped(sample_project, caplog, slug):
    valid = write_content(sample_project, "posts", "valid")
    invalid = write_content(sample_project, "pages", "invalid", slug=slug)

    SiteGenerator(sample_project).build()

    assert (sample_project / "site/posts/valid/index.html").is_file()
    assert "No posts yet" not in (sample_project / "site/index.html").read_text()
    assert str(invalid) in caplog.text
    assert str(valid) not in caplog.text


def test_duplicate_slugs_have_stable_numeric_suffixes(sample_project):
    later = write_content(sample_project, "posts", "z-last", slug="same")
    earlier = write_content(sample_project, "posts", "a-first", slug="same")
    generator = SiteGenerator(sample_project)
    generator.load_config()

    processed = generator.process_content({"posts": [later, earlier], "pages": []})

    assert [(post.filepath, post.metadata.slug) for post in processed["posts"]] == [
        (earlier, "same"),
        (later, "same-2"),
    ]


@pytest.mark.parametrize(
    "first_slug, second_slug", [("Case", "case"), ("caf\u00e9", "cafe\u0301")]
)
def test_host_filesystem_aliases_are_rejected(
    sample_project, capsys, first_slug, second_slug
):
    probe = sample_project / "case-probe"
    probe.mkdir()
    (probe / first_slug).touch()
    if not (probe / second_slug).exists():
        pytest.skip("The host filesystem distinguishes these path names")
    first = write_content(sample_project, "posts", "first", slug=first_slug)
    second = write_content(sample_project, "posts", "second", slug=second_slug)

    assert cmd_build(Namespace(project_dir=str(sample_project), drafts=False)) == 1

    diagnostic = capsys.readouterr().out
    assert str(first) in diagnostic
    assert str(second) in diagnostic
    assert not (sample_project / "site").exists()
