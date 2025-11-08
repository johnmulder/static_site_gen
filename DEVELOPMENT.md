# Development Guide

## Project Architecture

### Core Components

- `static_site_gen/generator/core.py` - Main build engine and orchestration
- `static_site_gen/generator/parser.py` - Content parsing and front matter validation
- `static_site_gen/generator/renderer.py` - Jinja2 template rendering
- `static_site_gen/generator/utils.py` - Utility functions for file operations
- `static_site_gen/cli.py` - Command-line interface

### Build Process Implementation

1. **Configuration Loading**: Load and validate `config.yaml` for site-wide settings
1. **Content Discovery**: Scan `content/posts/*.md` and `content/pages/*.md`
1. **Content Processing**: For each file:
   - Split YAML front matter and Markdown body
   - Parse and validate metadata
   - Convert Markdown to HTML
   - Generate slug if missing (kebab-case from title)
   - Render with appropriate template
   - Write to `site/.../index.html`
1. **Index Generation**: Build homepage from sorted post list
1. **Tag Pages**: Generate `/tag/<tag>/` pages from tag index
1. **Static Assets**: Copy `static/` to `site/static/`

### Template System

Uses Jinja2 with template inheritance:

- `base.html` - Shared layout with header/footer
- `post.html` - Individual blog post (extends base)
- `page.html` - Static pages like About (extends base)
- `index.html` - Homepage with post listing (extends base)
- `tag.html` - Tag archive pages (extends base)

### Content Model

#### Front Matter Schema

- **Required**: `title`, `date`
- **Optional**: `tags` (list), `draft` (boolean), `description`, `slug`

#### URL Generation

- Posts: `/posts/<slug>/index.html`
- Pages: `/<slug>/index.html`
- Tags: `/tag/<tag>/index.html`
- Static: `/static/...`

## Development Setup

### Prerequisites

- Python 3.8+
- Virtual environment recommended

### Installation

```bash
# Clone repository
git clone https://github.com/johnmulder/static_site_gen.git
cd static_site_gen

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .[dev]
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=static_site_gen --cov-report=term-missing

# Run specific test file
pytest tests/test_parser.py
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint code
ruff check .

# Format Markdown
mdformat README.md DEVELOPMENT.md
```

### Testing Coverage

Current coverage: **89%** (438/490 statements)

Key test areas:

- Content parsing and validation
- Template rendering
- URL generation and file operations
- CLI interface
- Security (path traversal protection)
- Error handling

## Project Structure

```
static_site_gen/
├── static_site_gen/              # Main package
│   ├── __init__.py
│   ├── __main__.py              # Entry point for `python -m static_site_gen`
│   ├── cli.py                   # Command-line interface
│   └── generator/               # Core generator modules
│       ├── __init__.py
│       ├── core.py              # Main build engine
│       ├── parser.py            # Content parsing
│       ├── renderer.py          # Template rendering
│       └── utils.py             # Utility functions
├── content/                     # Content source files
│   ├── posts/                   # Blog posts (YYYY-MM-DD-slug.md)
│   └── pages/                   # Static pages
├── templates/                   # Jinja2 templates
├── static/                      # Static assets (CSS, JS, images)
├── site/                        # Generated output (git-ignored)
├── tests/                       # Test suite
├── config.yaml                  # Site configuration
├── pyproject.toml              # Python project configuration
└── requirements.txt            # Production dependencies
```

## Configuration Options

### Required Settings

```yaml
site_name: "My Blog"
base_url: "https://example.com"
author: "Author Name"
```

### Optional Settings

```yaml
timezone: "UTC"                    # IANA timezone name
posts_per_page: 5                 # Posts per page for pagination
output_dir: "site"                # Output directory
description: "Site description"
keywords: ["blog", "personal"]
markdown_extensions:              # Additional Markdown extensions
  - "codehilite"
  - "tables"
  - "toc"
```

## Security Considerations

- **Path Traversal Protection**: All file paths are validated to prevent directory traversal attacks
- **URL Encoding**: Handles URL-encoded path traversal attempts
- **Template Security**: Jinja2 auto-escaping enabled by default
- **Input Validation**: Front matter and configuration are strictly validated

## Error Handling

### Fail-Fast Scenarios

- Missing or invalid `config.yaml`
- Template directory not found
- Invalid YAML front matter syntax

### Graceful Handling

- Missing optional front matter fields (logs warning, continues)
- Invalid dates (skips post or uses filename date)
- Missing static files

### Error Message Format

```
Error in content/posts/my-post.md: Missing required field 'date'
```

## Contributing

1. Fork the repository
1. Create a feature branch (`git checkout -b feature/amazing-feature`)
1. Make your changes
1. Add tests for new functionality
1. Ensure all tests pass (`pytest`)
1. Run code quality checks (`black .`, `ruff check .`)
1. Commit your changes (`git commit -m 'Add amazing feature'`)
1. Push to the branch (`git push origin feature/amazing-feature`)
1. Open a Pull Request

## Release Process

1. Update version in `pyproject.toml`
1. Update `CHANGELOG.md` with new features and fixes
1. Run full test suite
1. Create git tag (`git tag v0.2.0`)
1. Push tag (`git push --tags`)
1. Build and publish to PyPI (if configured)
