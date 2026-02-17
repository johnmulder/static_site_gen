"""
Tests for the command-line interface module.

These tests cover all CLI functionality including build command,
initialization, error handling, and argument parsing.
"""

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

            assert exit_code == 0
            assert (temp_path / "site").exists()

    def test_main_with_init_command(self):
        """Test main function with init command."""
        with patch("sys.argv", ["cli.py", "init", "test-project"]):
            exit_code = main()
            assert exit_code == 1

    def test_main_with_unknown_command(self):
        """Test main function with unknown command."""
        with (
            patch("sys.argv", ["cli.py", "unknown"]),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 2
        error_output = mock_stderr.getvalue()
        assert (
            "unknown" in error_output.lower()
            or "invalid choice" in error_output.lower()
        )

    def test_cmd_build_success(self):
        """Test successful build command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

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

            args = Mock()
            args.project_dir = str(temp_path)

            exit_code = cmd_build(args)

            assert exit_code == 0
            assert (temp_path / "site").exists()

    def test_cmd_build_with_missing_config(self):
        """Test build command with missing configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            args = Mock()
            args.project_dir = str(temp_path)

            exit_code = cmd_build(args)
            assert exit_code == 1

    def test_cmd_build_with_invalid_config(self):
        """Test build command with invalid configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "config.yaml").write_text(
                """
invalid: yaml: structure::
"""
            )

            args = Mock()
            args.project_dir = str(temp_path)

            exit_code = cmd_build(args)
            assert exit_code == 1

    def test_cmd_build_with_missing_directories(self):
        """Test build command with missing required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "config.yaml").write_text(
                """
site_name: "Test Site"
base_url: "https://example.com"
author: "Test Author"
"""
            )

            args = Mock()
            args.project_dir = str(temp_path)

            exit_code = cmd_build(args)
            assert exit_code == 1

    def test_init_command_not_implemented(self):
        """Test init command (currently not implemented)."""
        args = Mock()
        args.command = "init"

        # The cmd_init function just prints a message and returns 1
        exit_code = cmd_init(args)
        assert exit_code == 1

    def test_cmd_init_not_implemented(self):
        """Test that init command is not yet implemented."""
        args = Mock()
        args.project_name = "test-project"

        exit_code = cmd_init(args)
        assert exit_code == 1

    def test_error_handling_in_main(self):
        """Test error handling in main function."""
        with patch("sys.argv", ["cli.py", "build", "--project-dir", "/nonexistent"]):
            exit_code = main()
            assert exit_code == 1

    def test_main_no_args_shows_help(self):
        """Test that main with no args shows help."""
        with patch("sys.argv", ["cli.py"]):
            exit_code = main()
            assert exit_code == 1
