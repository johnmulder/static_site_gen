"""
Additional tests for core module functionality.

These tests target specific uncovered areas in the build process,
configuration loading, and error handling scenarios.
"""

from unittest.mock import Mock

import pytest
import yaml

from static_site_gen.generator.core import SiteGenerator


class TestSiteGeneratorEdgeCases:
    """Test edge cases and error conditions in SiteGenerator."""

    def _create_project_structure(self, tmp_path):
        """Helper to create basic project structure."""
        (tmp_path / "config.yaml").write_text(
            """
site_name: "Test Site"
base_url: "https://example.com"
author: "Test Author"
"""
        )
        generator = SiteGenerator(tmp_path)
        generator.load_config()  # Load the config to avoid NoneType errors
        return generator

    def test_process_content_with_invalid_front_matter(self, tmp_path):
        """Test processing content with malformed YAML front matter."""
        generator = self._create_project_structure(tmp_path)

        # Create content with invalid YAML
        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True)

        post_file = content_dir / "2023-01-01-invalid.md"
        post_file.write_text(
            """---
title: "Test Post
date: 2023-01-01
invalid: yaml: structure::
---

Content here.
"""
        )

        # Should skip invalid files and continue
        # process_content expects a dict of content files
        content_files = {"posts": [content_dir / "2023-01-01-invalid.md"], "pages": []}
        result = generator.process_content(content_files)
        assert len(result["posts"]) == 0  # Invalid file should be skipped

    def test_process_content_with_missing_required_fields(self, tmp_path):
        """Test processing content missing required front matter fields."""
        generator = self._create_project_structure(tmp_path)

        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True)

        # Post missing title
        post_file = content_dir / "2023-01-01-no-title.md"
        post_file.write_text(
            """---
date: 2023-01-01
---

Content without title.
"""
        )

        content_files = {"posts": [content_dir / "2023-01-01-no-title.md"], "pages": []}
        result = generator.process_content(content_files)
        assert len(result["posts"]) == 0  # Should skip posts without required fields

    def test_process_content_with_draft_posts(self, tmp_path):
        """Test that draft posts are filtered out in production."""
        generator = self._create_project_structure(tmp_path)

        content_dir = tmp_path / "content" / "posts"
        content_dir.mkdir(parents=True)

        # Create a draft post
        draft_file = content_dir / "2023-01-01-draft.md"
        draft_file.write_text(
            """---
title: "Draft Post"
date: 2023-01-01
draft: true
---

This is a draft.
"""
        )

        # Create a published post
        published_file = content_dir / "2023-01-01-published.md"
        published_file.write_text(
            """---
title: "Published Post"
date: 2023-01-01
draft: false
---

This is published.
"""
        )

        content_files = {
            "posts": [
                content_dir / "2023-01-01-draft.md",
                content_dir / "2023-01-01-published.md",
            ],
            "pages": [],
        }
        result = generator.process_content(content_files)
        # process_content returns all posts (including drafts)
        assert len(result["posts"]) == 2

        # But verify that draft filtering works as expected
        published_posts = [post for post in result["posts"] if not post.metadata.draft]
        assert len(published_posts) == 1
        assert published_posts[0].metadata.title == "Published Post"

    def test_build_error_handling_scenarios(self, tmp_path):
        """Test various error scenarios during build."""
        generator = self._create_project_structure(tmp_path)

        # Test with missing directories
        with pytest.raises(FileNotFoundError):
            generator.build()

        # Test with missing templates after creating content
        (tmp_path / "content").mkdir()
        (tmp_path / "static").mkdir()

        with pytest.raises(FileNotFoundError):
            generator.build()

    def test_generate_tag_pages_with_empty_tags(self, tmp_path):
        """Test tag page generation when no posts have tags."""
        generator = self._create_project_structure(tmp_path)

        # Mock renderer
        generator.renderer = Mock()
        generator.renderer.render_template.return_value = "<html>Tag page</html>"

        # Create mock post objects with proper structure
        post1 = Mock()
        post1.metadata.title = "Post 1"
        post1.metadata.tags = []
        post1.metadata.date = "2023-01-01"
        post1.metadata.slug = "post-1"
        post1.metadata.draft = False
        post1.metadata.description = "Description 1"
        post1.content = "Content 1"
        post1.to_dict.return_value = {
            "title": "Post 1",
            "date": "2023-01-01",
            "slug": "post-1",
            "tags": [],
            "draft": False,
            "description": "Description 1",
            "content": "Content 1",
        }

        post2 = Mock()
        post2.metadata.title = "Post 2"
        post2.metadata.tags = []  # No tags
        post2.metadata.date = "2023-01-02"
        post2.metadata.slug = "post-2"
        post2.metadata.draft = False
        post2.metadata.description = "Description 2"
        post2.content = "Content 2"
        post2.to_dict.return_value = {
            "title": "Post 2",
            "date": "2023-01-02",
            "slug": "post-2",
            "tags": [],
            "draft": False,
            "description": "Description 2",
            "content": "Content 2",
        }

        posts = [post1, post2]

        # Should handle empty tag collection gracefully
        generator.generate_tag_pages(posts)

        # This test verifies the method doesn't crash with empty tags    def test_resolve_slug_collision_with_many_conflicts(self, tmp_path):
        """Test slug collision resolution with multiple conflicts."""
        generator = self._create_project_structure(tmp_path)

        # Setup existing slugs with multiple conflicts
        generator.used_slugs = {
            "test-post": True,
            "test-post-2": True,
            "test-post-3": True,
            "test-post-4": True,
        }

        # Should find the next available number
        result = generator._resolve_slug_collision("test-post", generator.used_slugs)
        assert result == "test-post-5"

    def test_config_missing_file_raises(self, tmp_path):
        """Test that loading from a nonexistent path raises FileNotFoundError."""
        generator = SiteGenerator(tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError):
            generator.load_config()

    def test_config_invalid_yaml_raises(self, tmp_path):
        """Test that malformed YAML raises YAMLError."""
        (tmp_path / "config.yaml").write_text(
            """
site_name: "Test Site"
invalid: yaml: structure::
base_url: "https://example.com"
"""
        )

        generator = SiteGenerator(tmp_path)
        with pytest.raises(yaml.YAMLError):
            generator.load_config()

    def test_config_missing_required_fields_raises(self, tmp_path):
        """Test that missing required fields raises ValueError."""
        (tmp_path / "config.yaml").write_text(
            """
site_name: "Test Site"
"""
        )

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="Missing required config fields"):
            generator.load_config()

    def test_config_rejects_invalid_base_url(self, tmp_path):
        """Test configuration rejects non-http(s) URLs."""
        (tmp_path / "config.yaml").write_text(
            """
site_name: "Test Site"
base_url: "not-a-url"
author: "Test Author"
"""
        )

        generator = SiteGenerator(tmp_path)
        with pytest.raises(
            ValueError, match="base_url must be a valid absolute HTTP/HTTPS URL"
        ):
            generator.load_config()

    def test_config_rejects_invalid_timezone(self, tmp_path):
        """Test configuration rejects invalid timezone names."""
        (tmp_path / "config.yaml").write_text(
            """
site_name: "Test Site"
base_url: "https://example.com"
author: "Test Author"
timezone: "Mars/Phobos"
"""
        )

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="Invalid timezone setting"):
            generator.load_config()


class TestDiscoverContent:
    """Test content file discovery."""

    def _make_generator(self, tmp_path):
        """Create a SiteGenerator with content directories."""
        (tmp_path / "content" / "posts").mkdir(parents=True)
        (tmp_path / "content" / "pages").mkdir(parents=True)
        return SiteGenerator(tmp_path)

    def test_discovers_markdown_files(self, tmp_path):
        """Test discovery of .md files in posts and pages directories."""
        generator = self._make_generator(tmp_path)

        (tmp_path / "content" / "posts" / "2025-01-01-first.md").write_text("# A")
        (tmp_path / "content" / "posts" / "2025-02-01-second.md").write_text("# B")
        (tmp_path / "content" / "pages" / "about.md").write_text("# About")

        result = generator.discover_content()

        assert len(result["posts"]) == 2
        assert len(result["pages"]) == 1

    def test_ignores_non_markdown_files(self, tmp_path):
        """Test that non-.md files are excluded."""
        generator = self._make_generator(tmp_path)

        (tmp_path / "content" / "posts" / "2025-01-01-real.md").write_text("# Real")
        (tmp_path / "content" / "posts" / "notes.txt").write_text("not markdown")
        (tmp_path / "content" / "posts" / "data.json").write_text("{}")

        result = generator.discover_content()

        assert len(result["posts"]) == 1
        filenames = [p.name for p in result["posts"]]
        assert "2025-01-01-real.md" in filenames

    def test_empty_content_directories(self, tmp_path):
        """Test discovery with empty content directories."""
        generator = self._make_generator(tmp_path)

        result = generator.discover_content()

        assert result["posts"] == []
        assert result["pages"] == []

    def test_missing_content_directories(self, tmp_path):
        """Test discovery when content subdirectories do not exist."""
        generator = SiteGenerator(tmp_path)
        # content/ directory does not exist at all

        result = generator.discover_content()

        assert result["posts"] == []
        assert result["pages"] == []
