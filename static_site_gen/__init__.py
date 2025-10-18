"""
A minimal Python-based static site generator.

This package provides functionality to convert Markdown files with YAML front matter
into a clean HTML blog with template-based rendering.
"""

__version__ = "0.1.0"
__author__ = "John Mulder"

from .cli import main
from .generator.core import SiteGenerator

__all__ = ["main", "SiteGenerator"]
