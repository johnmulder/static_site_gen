"""
Command-line interface for the static site generator.

This module provides the main entry point for the static site generator,
implementing a clean CLI interface for building and managing sites.

Commands:
- build: Generate the static site from content and templates
- serve: Start a local development server (future enhancement)
- clean: Remove generated site files (future enhancement)

The CLI handles:
- Argument parsing and validation
- Configuration file discovery and loading
- Build process orchestration
- Error reporting and user feedback
- Exit code management for CI/CD integration

Usage patterns:
    python -m src.cli build
    python -m src.cli build --config custom-config.yaml
    python -m src.cli build --output custom-site-dir

The interface emphasizes:
- Simple, predictable commands
- Clear error messages and help text
- Sensible defaults with override options
- Progress indication for long operations
- Proper exit codes for automation

Design principles:
- Single command responsibility
- Fail fast with helpful messages
- Consistent argument patterns
- No interactive prompts (automation-friendly)
"""
