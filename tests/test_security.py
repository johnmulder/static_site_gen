"""
Security tests for path traversal prevention.

These tests verify that the system properly prevents path traversal attacks
and other security vulnerabilities while allowing legitimate operations.
"""

import pytest

from static_site_gen.generator.output import get_output_path


class TestPathTraversalSecurity:
    """Test path traversal attack prevention."""

    @pytest.mark.parametrize(
        "url_path",
        [
            "/posts/../../../etc/passwd/",
            "/posts/../sensitive-file/",
            "/posts/../../outside-dir/",
            "/../../../root-level/",
            "/posts/normal/../../../escape/",
            "/posts/./../../escape/",
        ],
    )
    def test_path_traversal_with_dots_blocked(self, tmp_path, url_path):
        """Test that ../ sequences are blocked."""
        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            get_output_path(tmp_path, url_path)

    @pytest.mark.parametrize(
        "url_path",
        [
            "/posts\\escape/",
            "\\root-level\\",
        ],
    )
    def test_windows_backslash_blocked(self, tmp_path, url_path):
        """Test that Windows-style path separators are blocked."""
        with pytest.raises(ValueError, match="Invalid path separator"):
            get_output_path(tmp_path, url_path)

    @pytest.mark.parametrize(
        "url_path",
        [
            "/posts\\..\\..\\windows-style/",
            "\\..\\..\\root-level\\",
        ],
    )
    def test_backslash_with_traversal_blocked(self, tmp_path, url_path):
        """Test paths with both backslashes and .. are caught."""
        with pytest.raises(ValueError, match="Path traversal attempt detected"):
            get_output_path(tmp_path, url_path)

    @pytest.mark.parametrize(
        "url_path, expected_rel",
        [
            ("/posts/my-post/", "posts/my-post/index.html"),
            ("/tag/python/", "tag/python/index.html"),
            ("/about/", "about/index.html"),
            ("/", "index.html"),
            (
                "/posts/long-title-with-hyphens/",
                "posts/long-title-with-hyphens/index.html",
            ),
            ("/posts/unicode-测试/", "posts/unicode-测试/index.html"),
            ("/posts/with-numbers-123/", "posts/with-numbers-123/index.html"),
        ],
    )
    def test_legitimate_paths_allowed(self, tmp_path, url_path, expected_rel):
        """Test that legitimate paths work correctly."""
        result = get_output_path(tmp_path, url_path)
        assert result == tmp_path / expected_rel

    @pytest.mark.parametrize(
        "url_path",
        ["", "/", "///"],
    )
    def test_empty_and_root_paths(self, tmp_path, url_path):
        """Test handling of empty and root paths."""
        result = get_output_path(tmp_path, url_path)
        assert result == tmp_path / "index.html"

    def test_path_stays_within_base_directory(self, tmp_path):
        """Test that resolved paths stay within base directory."""
        base_dir = tmp_path / "site"
        base_dir.mkdir()

        result = get_output_path(base_dir, "/posts/test/")
        resolved_result = result.resolve()
        resolved_base = base_dir.resolve()

        assert str(resolved_result).startswith(str(resolved_base))

    @pytest.mark.parametrize(
        "url_path, expected_rel",
        [
            ("/posts/title-with-dashes/", "posts/title-with-dashes/index.html"),
            (
                "/posts/title_with_underscores/",
                "posts/title_with_underscores/index.html",
            ),
            ("/posts/title.with.dots/", "posts/title.with.dots/index.html"),
            ("/posts/title with spaces/", "posts/title with spaces/index.html"),
        ],
    )
    def test_special_characters_in_paths(self, tmp_path, url_path, expected_rel):
        """Test handling of special characters in legitimate paths."""
        result = get_output_path(tmp_path, url_path)
        assert result == tmp_path / expected_rel
