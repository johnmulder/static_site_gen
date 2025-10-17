# Static Site Generator

A minimal static site generation tool for creating a personal blog from Markdown files with YAML front matter.\
This tool converts content into clean, responsive HTML using Jinja2 templates.

## Project Goals

Turn Markdown posts with front matter into a static HTML blog with clean URLs, index page, tags, and RSS, using simple templates.

## Content Model

### Source Format

- **Markdown** files with **YAML front matter** at the top.
- Front matter example:

```yaml
---
title: "My First Post"
date: 2025-08-07
tags: [python, static-site]
draft: false
description: "A short summary for cards/RSS/meta"
slug: my-first-post
---
```

**Body:** Markdown below the front matter.

## URL Structure

- **Posts:** `/posts/<slug>/index.html`
- **Home page:** `/index.html`
- **Tags:** `/tag/<tag>/index.html`
- **Static assets:** `/static/...`

## Directory Layout

```
static-site-gen/
|-- src/                         # Source code layer
|   |-- generator/               # Core generator package
|   |   |-- __init__.py
|   |   |-- core.py             # Main build engine
|   |   |-- parser.py           # Content parsing
|   |   |-- renderer.py         # Template rendering
|   |   +-- utils.py            # Utilities
|   +-- cli.py                   # Command-line interface
|-- content/                     # Content layer
|   |-- posts/
|   |   +-- 2025-08-07-my-first-post.md
|   +-- pages/
|       +-- about.md
|-- templates/                   # Presentation layer
|   |-- base.html
|   |-- post.html
|   |-- index.html
|   +-- tag.html
|-- static/
|   +-- style.css
|-- site/                        # Generated site
|-- config.yaml
|-- requirements.txt
|-- pyproject.toml
+-- README.md
```

## Templates

- **base.html** -- shared layout with `<header>` and `<footer>`.
- **post.html** -- extends `base.html`, renders title, date, tags, and post body.
- **index.html** -- extends `base.html`, lists posts.
- **tag.html** -- extends `base.html`, lists posts for a single tag.

## Build Process

1. Load `config.yaml` for site-wide settings (title, base URL, author, timezone).

1. Walk through `content/posts/*.md` and `content/pages/*.md`.

1. For each file:

   - Split YAML front matter and Markdown body.
   - Parse and validate metadata.
   - Convert Markdown -> HTML.
   - Derive slug if missing (kebab-case of title).
   - Render with the correct template.
   - Save to `site/.../index.html`.

1. After processing posts:

   - Build `index.html` from sorted post list.
   - Build `/tag/<tag>/` pages from tag index.
   - Build `feed.xml` (RSS).

1. Copy static assets to `site/static`.

## Configuration Example

```yaml
site_name: "John's Blog"
base_url: "https://example.com"
author: "John Mulder"
timezone: "America/Denver"
posts_per_page: 20
```

## Usage

```bash
# Build the site
python -m src.cli build

# Serve locally for development
python -m http.server -d site
```

## Dependencies

- `markdown` (Markdown parsing)
- `jinja2` (templating)
- `pyyaml` (front matter parsing)
