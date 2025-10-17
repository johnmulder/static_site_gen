"""
Core build engine for the static site generator.

This module contains the main build orchestration logic that coordinates
the entire content -> template -> output pipeline. It manages:

- Site configuration loading and validation
- Content discovery and processing coordination
- Template rendering coordination
- Output directory management
- Static asset copying
- Build process error handling

The core engine implements the build process flow:
1. Load and validate config.yaml
2. Scan content/ directory for Markdown files
3. Parse front matter and validate required fields
4. Convert Markdown -> HTML with extensions
5. Render templates with content data
6. Generate index page from sorted posts
7. Create tag archive pages
8. Build RSS feed (feed.xml)
9. Copy static assets to site/static/

Design principles:
- Single responsibility: orchestration only
- Fail fast on configuration errors
- Clear error messages with file paths
- Stateless operation (no persistent state assumed)
"""
