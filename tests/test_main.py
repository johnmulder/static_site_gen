"""Tests for the __main__.py entry point."""

from unittest.mock import patch

from static_site_gen.__main__ import main


def test_main_is_importable():
    """The main function is importable from __main__."""
    assert callable(main)


def test_main_with_no_args_returns_nonzero():
    """Running main with no arguments prints help and returns 1."""
    with patch("sys.argv", ["static_site_gen"]):
        result = main()
    assert result == 1
