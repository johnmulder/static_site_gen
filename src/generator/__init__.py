"""
Static Site Generator Package.

A minimal Python-based static site generator that converts Markdown files
with YAML front matter into a clean HTML blog. The generator follows a
layered architecture with clear separation of concerns:

- Content processing (parsing, validation)
- Template rendering (Jinja2-based)
- File generation (clean URL structure)
- Asset management (static file copying)

The package emphasizes simplicity and maintainability while providing
the core functionality needed for a personal blog site.
"""

__version__ = "0.1.0"
__author__ = "John Mulder"

# Main package exports will be defined as implementation progresses
__all__ = []
