"""
Shared test fixtures for the static site generator test suite.

Provides reusable project scaffolding, sample content, and configuration
so individual test files do not need to rebuild these from scratch.
"""

# pylint: disable=redefined-outer-name
import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def sample_config():
    """Return a valid config dict suitable for writing to YAML."""
    return {
        "site_name": "Test Blog",
        "base_url": "https://test.example.com",
        "author": "Test Author",
        "timezone": "UTC",
        "posts_per_page": 5,
        "output_dir": "site",
        "description": "A test blog",
        "markdown_extensions": ["toc"],
    }


@pytest.fixture
def sample_project(tmp_path, sample_config):
    """
    Create a minimal but complete project structure in tmp_path.

    Includes config, templates (copied from real project), content dirs,
    and static dir. Returns the project root path.
    """
    import yaml  # pylint: disable=import-outside-toplevel

    # Config
    (tmp_path / "config.yaml").write_text(yaml.dump(sample_config))

    # Content directories
    posts_dir = tmp_path / "content" / "posts"
    pages_dir = tmp_path / "content" / "pages"
    posts_dir.mkdir(parents=True)
    pages_dir.mkdir(parents=True)

    # Copy real templates (including feed.xml)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    for src in (PROJECT_ROOT / "templates").iterdir():
        if src.is_file():
            shutil.copy(src, template_dir / src.name)

    # Static directory
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "style.css").write_text("body { margin: 0; }")

    return tmp_path


@pytest.fixture
def sample_post_content():
    """Return front matter + markdown string for a valid post."""
    return (FIXTURES_DIR / "sample_post.md").read_text()


@pytest.fixture
def draft_post_content():
    """Return front matter + markdown string for a draft post."""
    return (FIXTURES_DIR / "draft_post.md").read_text()


@pytest.fixture
def minimal_post_content():
    """Return front matter + markdown string for a minimal post."""
    return (FIXTURES_DIR / "minimal_post.md").read_text()


@pytest.fixture
def sample_page_content():
    """Return front matter + markdown string for a static page."""
    return (FIXTURES_DIR / "sample_page.md").read_text()
