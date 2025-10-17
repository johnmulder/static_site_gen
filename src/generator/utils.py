"""
Utility functions and helpers for the static site generator.

This module provides common utility functions used across the generator
components. Utilities are organized by functional area:

File Operations:
- Directory creation and cleanup
- File copying with error handling
- Path normalization across platforms
- Safe file writing with atomic operations

Content Processing:
- Slug generation from titles (Unicode-safe, kebab-case)
- Date parsing and formatting
- URL generation and validation
- Text processing helpers

Configuration:
- YAML loading with validation
- Environment variable handling
- Default value management
- Type conversion utilities

The utilities emphasize:
- Cross-platform compatibility
- Robust error handling
- Clear function interfaces
- Performance for common operations

Design principles:
- Pure functions where possible
- Consistent return types and error handling
- Comprehensive docstrings with examples
- No side effects unless explicitly documented
"""
