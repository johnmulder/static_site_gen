"""
Content parsing and validation module.

This module handles the parsing of Markdown files with YAML front matter,
extracting and validating metadata, and preparing content for rendering.
Core responsibilities:

- YAML front matter extraction and parsing
- Markdown body separation and processing
- Content metadata validation (required/optional fields)
- Slug generation from titles (kebab-case conversion)
- Date parsing and timezone handling
- Tag processing and normalization

Supported front matter schema:
- Required: title, date
- Optional: tags (list), draft (boolean), description, slug

The parser handles various edge cases:
- Missing slugs (auto-generated from title)
- Invalid dates (graceful error handling)
- Malformed YAML (clear error messages)
- Unicode characters in titles and content
- Empty or missing front matter sections

Design principles:
- Validate early, fail with clear messages
- Handle encoding issues gracefully
- Preserve original content when possible
- Generate helpful error context (file paths, line numbers)
"""
