"""
Tests for utility functions in the generator.utils module.

These tests cover file operations, URL generation, and data manipulation
functions used throughout the site generation process.
"""

from datetime import datetime

import pytest

from static_site_gen.generator.output import (
    clean_output_dir,
    collect_posts_by_tag,
    copy_static_files,
    ensure_dir,
    filter_published_posts,
    generate_page_url,
    generate_pagination_url,
    generate_post_url,
    generate_tag_url,
    paginate_posts,
    sort_posts_by_date,
    write_file,
)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_ensure_dir_creates_directory(self, tmp_path):
        """Test that ensure_dir creates directories."""
        test_dir = tmp_path / "test" / "nested" / "dir"
        assert not test_dir.exists()

        ensure_dir(test_dir)

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_dir_handles_existing_directory(self, tmp_path):
        """Test that ensure_dir works with existing directories."""
        test_dir = tmp_path / "existing"
        test_dir.mkdir()

        # Should not raise an error
        ensure_dir(test_dir)

        assert test_dir.exists()

    def test_copy_static_files_success(self, tmp_path):
        """Test successful static file copying."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"

        # Create source structure
        source_dir.mkdir()
        (source_dir / "style.css").write_text("body { margin: 0; }")
        (source_dir / "script.js").write_text("console.log('hello');")

        nested_dir = source_dir / "images"
        nested_dir.mkdir()
        (nested_dir / "logo.png").write_text("fake image data")

        copy_static_files(source_dir, dest_dir)

        # Verify files were copied
        assert (dest_dir / "style.css").exists()
        assert (dest_dir / "script.js").exists()
        assert (dest_dir / "images" / "logo.png").exists()

        # Verify content
        assert (dest_dir / "style.css").read_text() == "body { margin: 0; }"

    def test_copy_static_files_source_not_found(self, tmp_path):
        """Test error when source directory doesn't exist."""
        source_dir = tmp_path / "nonexistent"
        dest_dir = tmp_path / "dest"

        with pytest.raises(
            FileNotFoundError, match="Static source directory not found"
        ):
            copy_static_files(source_dir, dest_dir)

    def test_copy_static_files_overwrites_existing_dest(self, tmp_path):
        """Test that copying overwrites existing destination."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"

        # Create source
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("new content")

        # Create existing destination with different content
        dest_dir.mkdir()
        (dest_dir / "old_file.txt").write_text("old content")

        copy_static_files(source_dir, dest_dir)

        # Old file should be gone, new file should exist
        assert not (dest_dir / "old_file.txt").exists()
        assert (dest_dir / "file.txt").exists()
        assert (dest_dir / "file.txt").read_text() == "new content"

    def test_generate_post_url(self):
        """Test post URL generation."""
        assert generate_post_url("my-post") == "/posts/my-post/"
        assert generate_post_url("test-123") == "/posts/test-123/"

    def test_generate_tag_url(self):
        """Test tag URL generation with encoding."""
        assert generate_tag_url("python") == "/tag/python/"
        assert generate_tag_url("C++") == "/tag/C%2B%2B/"
        assert generate_tag_url("machine learning") == "/tag/machine%20learning/"

    def test_generate_page_url(self):
        """Test page URL generation."""
        assert generate_page_url("about") == "/about/"
        assert generate_page_url("contact-us") == "/contact-us/"

    def test_write_file_creates_file_and_dirs(self, tmp_path):
        """Test that write_file creates files and directories."""
        file_path = tmp_path / "nested" / "dir" / "test.txt"
        content = "Hello, world!"

        write_file(file_path, content)

        assert file_path.exists()
        assert file_path.read_text() == content
        assert file_path.parent.exists()

    def test_collect_posts_by_tag(self):
        """Test collecting posts by tags."""
        posts = [
            {"title": "Post 1", "tags": ["python", "web"]},
            {"title": "Post 2", "tags": ["python", "data"]},
            {"title": "Post 3", "tags": ["web"]},
            {"title": "Post 4", "tags": []},  # No tags
            {"title": "Post 5"},  # Missing tags field
        ]

        result = collect_posts_by_tag(posts)

        assert len(result["python"]) == 2
        assert len(result["web"]) == 2
        assert len(result["data"]) == 1
        assert "nonexistent" not in result

    def test_sort_posts_by_date_newest_first(self):
        """Test sorting posts by date (newest first)."""
        posts = [
            {"title": "Old", "date": datetime(2020, 1, 1)},
            {"title": "New", "date": datetime(2025, 1, 1)},
            {"title": "Middle", "date": datetime(2022, 1, 1)},
        ]

        result = sort_posts_by_date(posts)

        assert result[0]["title"] == "New"
        assert result[1]["title"] == "Middle"
        assert result[2]["title"] == "Old"

    def test_sort_posts_by_date_oldest_first(self):
        """Test sorting posts by date (oldest first)."""
        posts = [
            {"title": "Old", "date": datetime(2020, 1, 1)},
            {"title": "New", "date": datetime(2025, 1, 1)},
            {"title": "Middle", "date": datetime(2022, 1, 1)},
        ]

        result = sort_posts_by_date(posts, reverse=False)

        assert result[0]["title"] == "Old"
        assert result[1]["title"] == "Middle"
        assert result[2]["title"] == "New"

    def test_filter_published_posts(self):
        """Test filtering out draft posts."""
        posts = [
            {"title": "Published 1", "draft": False},
            {"title": "Draft 1", "draft": True},
            {"title": "Published 2"},  # No draft field (defaults to published)
            {"title": "Draft 2", "draft": True},
        ]

        result = filter_published_posts(posts)

        assert len(result) == 2
        assert result[0]["title"] == "Published 1"
        assert result[1]["title"] == "Published 2"

    def test_clean_output_dir_with_existing_dir(self, tmp_path):
        """Test cleaning existing output directory."""
        output_dir = tmp_path / "site"
        output_dir.mkdir()

        # Add some files
        (output_dir / "index.html").write_text("old content")
        (output_dir / "subdir").mkdir()
        (output_dir / "subdir" / "file.txt").write_text("old file")

        clean_output_dir(output_dir)

        # Directory should exist but be empty
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert len(list(output_dir.iterdir())) == 0

    def test_clean_output_dir_with_nonexistent_dir(self, tmp_path):
        """Test cleaning nonexistent output directory."""
        output_dir = tmp_path / "nonexistent"

        clean_output_dir(output_dir)

        # Directory should be created
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert len(list(output_dir.iterdir())) == 0

    def test_paginate_posts_splits_into_expected_pages(self):
        """Test pagination splits post lists correctly."""
        posts = [
            {"title": f"Post {i}", "date": datetime(2025, 1, i)} for i in range(1, 8)
        ]

        pages = paginate_posts(posts, posts_per_page=3)

        assert len(pages) == 3
        assert pages[0]["page_number"] == 1
        assert len(pages[0]["posts"]) == 3
        assert pages[0]["has_next"] is True
        assert pages[0]["next_url"] == "/page/2/"
        assert pages[2]["page_number"] == 3
        assert len(pages[2]["posts"]) == 1
        assert pages[2]["has_next"] is False

    def test_generate_pagination_url(self):
        """Test URL generation for pagination pages."""
        assert generate_pagination_url(1) == "/"
        assert generate_pagination_url(2) == "/page/2/"
