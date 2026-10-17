"""
A minimal Python-based static site generator.

This package provides functionality to convert Markdown files with YAML front matter
into a clean HTML blog with template-based rendering.
"""

from importlib.metadata import version

__version__ = version("static-site-gen")
__author__ = "John Mulder"

from .cli import main
from .generator.core import SiteGenerator

__all__ = ["main", "SiteGenerator"]
