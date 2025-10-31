"""
Tests for the command-line interface module.

These tests cover all CLI functionality including build command,
initialization, error handling, and argument parsing.
"""

import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from static_site_gen.cli import cmd_build, cmd_init, main


class TestCLI:
    """Test command-line interface functionality."""

    def test_main_with_help_flag(self):
        """Test main function with help flag."""
        with (
            patch("sys.argv", ["cli.py", "--help"]),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0
        output = mock_stdout.getvalue()
        assert "usage:" in output.lower()

    def test_main_with_build_command(self):
        """Test main function with build command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create minimal project structure
            (temp_path / "config.yaml").write_text(
                """
site_name: "Test Site"
base_url: "https://example.com" 
author: "Test Author"
"""
            )

            (temp_path / "content").mkdir()
            (temp_path / "templates").mkdir()
            (temp_path / "static").mkdir()

            # Create minimal templates
            (temp_path / "templates" / "base.html").write_text(
                """
<!DOCTYPE html>
<html>
<head><title>{{ site.site_name }}</title></head>
<body>{% block content %}{% endblock %}</body>
</html>
"""
            )

            (temp_path / "templates" / "index.html").write_text(
                """
{% extends "base.html" %}
{% block content %}<h1>{{ site.site_name }}</h1>{% endblock %}
"""
            )

            with (
                patch("sys.argv", ["cli.py", "build"]),
                patch("os.getcwd", return_value=str(temp_path)),
            ):
                exit_code = main()

            # Verify build completed successfully
            assert exit_code == 0
            assert (temp_path / "site").exists()  # Site directory should be created

    def test_main_with_init_command(self):
        """Test main function with init command."""
        with patch("sys.argv", ["cli.py", "init", "test-project"]):
            exit_code = main()
            # Init command currently returns 1 (not implemented)
            assert exit_code == 1

    def test_main_with_unknown_command(self):
        """Test main function with unknown command."""
        with (
            patch("sys.argv", ["cli.py", "unknown"]),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2  # argparse error code
        error_output = mock_stderr.getvalue()
        assert (
            "unknown" in error_output.lower()
            or "invalid choice" in error_output.lower()
        )

    def test_cmd_build_success(self):
        """Test successful build command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create project structure
            (temp_path / "config.yaml").write_text(
                """
site_name: "Test Site"
base_url: "https://example.com"
author: "Test Author"
"""
            )

            (temp_path / "content").mkdir()
            (temp_path / "templates").mkdir()
            (temp_path / "static").mkdir()

            # Create templates
            (temp_path / "templates" / "base.html").write_text(
                """
<!DOCTYPE html>
<html>
<head><title>{{ site.site_name }}</title></head>
<body>{% block content %}{% endblock %}</body>
</html>
"""
            )

            (temp_path / "templates" / "index.html").write_text(
                """
{% extends "base.html" %}
{% block content %}<h1>{{ site.site_name }}</h1>{% endblock %}
"""
            )

            # Mock args with correct attribute name
            args = Mock()
            args.project_dir = str(temp_path)

            # Should complete without errors
            exit_code = cmd_build(args)

            # Verify success
            assert exit_code == 0
            assert (temp_path / "site").exists()  # Site directory should be created

    def test_cmd_build_with_missing_config(self):
        """Test build command with missing configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            args = Mock()
            args.project_dir = str(temp_path)

            # Should return error code instead of raising
            exit_code = cmd_build(args)
            assert exit_code == 1

    def test_cmd_build_with_invalid_config(self):
        """Test build command with invalid configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create invalid config
            (temp_path / "config.yaml").write_text(
                """
invalid: yaml: structure::
"""
            )

            args = Mock()
            args.project_dir = str(temp_path)

            # Should return error code instead of raising
            exit_code = cmd_build(args)
            assert exit_code == 1

    def test_cmd_build_with_missing_directories(self):
        """Test build command with missing required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config but no other directories
            (temp_path / "config.yaml").write_text(
                """
site_name: "Test Site"
base_url: "https://example.com"
author: "Test Author"
"""
            )

            args = Mock()
            args.project_dir = str(temp_path)

            # Should return error code instead of raising
            exit_code = cmd_build(args)
            assert exit_code == 1

    def test_cmd_init_success(self):
        """Test init command (currently not implemented)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            args = Mock()
            args.project_name = "test-project"

            # Currently returns 1 because not implemented
            exit_code = cmd_init(args)
            assert exit_code == 1

    def test_cmd_init_not_implemented(self):
        """Test that init command is not yet implemented."""
        args = Mock()
        args.project_name = "test-project"

        exit_code = cmd_init(args)
        assert exit_code == 1  # Not implemented yet

    def test_error_handling_in_main(self):
        """Test error handling in main function."""
        # Test with build command that returns error code
        with patch("sys.argv", ["cli.py", "build", "--project-dir", "/nonexistent"]):
            exit_code = main()
            assert exit_code == 1  # Should return error code

    def test_main_no_args_shows_help(self):
        """Test that main with no args shows help."""
        with patch("sys.argv", ["cli.py"]):
            exit_code = main()
            assert exit_code == 1  # Returns 1 when showing help
