"""
Main entry point for the static site generator package.

This module allows the package to be run as:
    python -m static_site_gen
"""

from .cli import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
