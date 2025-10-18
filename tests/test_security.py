"""
Security tests for path traversal prevention.

These tests verify that the system properly prevents path traversal attacks
and other security vulnerabilities while allowing legitimate operations.
"""

from pathlib import Path

import pytest
from static_site_gen.generator.utils import get_output_path


class TestPathTraversalSecurity:
    """Test path traversal attack prevention."""

    def test_path_traversal_with_dots_blocked(self, tmp_path):
        """Test that ../ sequences are blocked."""
        malicious_paths = [
            "/posts/../../../etc/passwd/",
            "/posts/../sensitive-file/",
            "/posts/../../outside-dir/",
            "/../../../root-level/",
            "/posts/normal/../../../escape/",
            "/posts/./../../escape/",
        ]

        for url_path in malicious_paths:
            with pytest.raises(ValueError, match="Path traversal attempt detected"):
                get_output_path(tmp_path, url_path)

    def test_windows_style_traversal_blocked(self, tmp_path):
        """Test that Windows-style path separators are blocked."""
        # Paths with backslashes but no .. (to test specific backslash detection)
        backslash_paths = [
            "/posts\\escape/",
            "\\root-level\\",
        ]

        for url_path in backslash_paths:
            with pytest.raises(ValueError, match="Invalid path separator"):
                get_output_path(tmp_path, url_path)

        # Paths with both backslashes and .. (caught by .. check first)
        traversal_with_backslash = [
            "/posts\\..\\..\\windows-style/",
            "\\..\\..\\root-level\\",
        ]

        for url_path in traversal_with_backslash:
            with pytest.raises(ValueError, match="Path traversal attempt detected"):
                get_output_path(tmp_path, url_path)

    def test_legitimate_paths_allowed(self, tmp_path):
        """Test that legitimate paths work correctly."""
        legitimate_cases = [
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
        ]

        for url_path, expected_rel_path in legitimate_cases:
            result = get_output_path(tmp_path, url_path)
            expected = tmp_path / expected_rel_path
            assert result == expected

    def test_empty_and_root_paths(self, tmp_path):
        """Test handling of empty and root paths."""
        test_cases = [
            ("", "index.html"),
            ("/", "index.html"),
            ("///", "index.html"),  # Multiple slashes
        ]

        for url_path, expected_rel_path in test_cases:
            result = get_output_path(tmp_path, url_path)
            expected = tmp_path / expected_rel_path
            assert result == expected

    def test_path_stays_within_base_directory(self, tmp_path):
        """Test that resolved paths stay within base directory."""
        # Create a base directory structure
        base_dir = tmp_path / "site"
        base_dir.mkdir()

        # Test normal paths
        result = get_output_path(base_dir, "/posts/test/")
        resolved_result = result.resolve()
        resolved_base = base_dir.resolve()

        # Verify the result path is within the base directory
        assert str(resolved_result).startswith(str(resolved_base))

    def test_special_characters_in_paths(self, tmp_path):
        """Test handling of special characters in legitimate paths."""
        # These should work (URL-encoded characters are handled upstream)
        legitimate_special = [
            ("/posts/title-with-dashes/", "posts/title-with-dashes/index.html"),
            (
                "/posts/title_with_underscores/",
                "posts/title_with_underscores/index.html",
            ),
            ("/posts/title.with.dots/", "posts/title.with.dots/index.html"),
            (
                "/posts/title with spaces/",
                "posts/title with spaces/index.html",
            ),  # Spaces handled upstream
        ]

        for url_path, expected_rel_path in legitimate_special:
            result = get_output_path(tmp_path, url_path)
            expected = tmp_path / expected_rel_path
            assert result == expected
