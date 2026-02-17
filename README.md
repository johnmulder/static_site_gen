# Static Site Generator

A minimal Python-based static site generator that converts Markdown files with YAML front matter into a clean, fast HTML blog.

## Features

- **Simple Content Management**: Write posts in Markdown with YAML front matter
- **Clean URLs**: SEO-friendly URLs like `/posts/my-post/` instead of `/posts/my-post.html`
- **Tag System**: Automatic tag pages for organizing content
- **Template System**: Customizable Jinja2 templates with inheritance
- **Fast Builds**: Efficient processing of content and assets
- **Static Assets**: Automatic copying of CSS, images, and other static files

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/johnmulder/static_site_gen.git
cd static_site_gen

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Optional: install development tools
pip install -e .[dev]
```

### Create Your First Post

1. **Create a post** in `content/posts/`:

```bash
# content/posts/2025-10-30-my-first-post.md
---
title: "My First Blog Post"
date: 2025-10-30
tags: [blog, welcome]
description: "Welcome to my new blog built with a static site generator"
---

# Welcome to My Blog

This is my first post using the static site generator!

## Features I Love

- Simple Markdown writing
- Clean URLs
- Fast loading pages
```

1. **Configure your site** in `config.yaml`:

```yaml
site_name: "My Blog"
base_url: "https://yourdomain.com"
author: "Your Name"
description: "My personal blog"
```

1. **Build your site**:

```bash
python -m static_site_gen build
```

1. **Preview locally**:

```bash
python -m http.server -d site
# Visit http://localhost:8000
```

## Content Structure

### Writing Posts

Create Markdown files in `content/posts/` with this structure:

```markdown
---
title: "Your Post Title"           # Required
date: 2025-10-30                  # Required (YYYY-MM-DD)
tags: [python, web, tutorial]     # Optional
description: "Post summary"       # Optional
slug: custom-url-slug             # Optional (auto-generated from title)
draft: false                      # Optional (default: false)
---

# Your Content Here

Write your post content in Markdown below the front matter.
```

### Creating Pages

Create static pages in `content/pages/`:

```bash
# content/pages/about.md
---
title: "About Me"
date: 2025-10-30
---

# About Me

This is my about page.
```

### URL Structure

Your content will be accessible at clean URLs:

- **Posts**: `https://yoursite.com/posts/my-first-post/`
- **Pages**: `https://yoursite.com/about/`
- **Tags**: `https://yoursite.com/tag/python/`
- **Homepage**: `https://yoursite.com/`

## Customization

### Templates

Customize the look of your site by editing templates in the `templates/` directory:

- `base.html` - Shared layout (header, footer, navigation)
- `index.html` - Homepage with post listings
- `post.html` - Individual blog post pages
- `page.html` - Static pages like About
- `tag.html` - Tag archive pages

### Styling

Add your CSS styles to `static/style.css`. All files in the `static/` directory are copied to your generated site.

### Configuration

Edit `config.yaml` to customize your site:

```yaml
# Required settings
site_name: "My Blog"
base_url: "https://yourdomain.com"
author: "Your Name"

# Optional settings
timezone: "UTC"
posts_per_page: 5
description: "My personal blog"
keywords: ["blog", "personal"]

# Markdown extensions
markdown_extensions:
  - "codehilite"    # Syntax highlighting
  - "tables"        # Table support
  - "toc"          # Table of contents
```

## Commands

### Build Site

```bash
python -m static_site_gen build
```

Generates your complete site in the `site/` directory.

### Initialize New Project

```bash
python -m static_site_gen init
```

*(Coming soon)* Creates a new site with sample content and templates.

### Development Workflow

```bash
# Build your site
python -m static_site_gen build

# Start local server
python -m http.server -d site

# Open http://localhost:8000 in your browser
```

## Deployment

After building your site with `python -m static_site_gen build`, you can deploy the `site/` directory to any static hosting service:

- **GitHub Pages**: Push the `site/` directory to your repository
- **Netlify**: Drag and drop the `site/` folder
- **Vercel**: Deploy from your Git repository
- **Any web server**: Upload the `site/` directory contents

## Project Structure

```ascii
your-blog/
├── content/                  # Your content
│   ├── posts/               # Blog posts (YYYY-MM-DD-slug.md)
│   └── pages/               # Static pages
├── templates/               # HTML templates
│   ├── base.html           # Shared layout
│   ├── index.html          # Homepage
│   ├── post.html           # Blog post template
│   ├── page.html           # Static page template
│   └── tag.html            # Tag archive template
├── static/                  # Static assets (CSS, images, etc.)
│   └── style.css           # Your styles
├── site/                    # Generated site (auto-created)
├── config.yaml             # Site configuration
└── requirements.txt        # Python dependencies
```

## Requirements

- Python 3.12 or higher
- Dependencies: `markdown`, `jinja2`, `pyyaml`

## Development Quality Checks

```bash
ruff check .
black --check .
isort --check-only .
mypy static_site_gen
pytest --cov=static_site_gen --cov-report=term-missing
```

For detailed development information, see [DEVELOPMENT.md](DEVELOPMENT.md).
