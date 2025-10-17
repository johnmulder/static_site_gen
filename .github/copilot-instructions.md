# Copilot Instructions - Static Site Generator

## Project Overview

This is a minimal Python-based static site generator that converts Markdown files with YAML front matter into a clean HTML blog. The project emphasizes simplicity and follows a clear content -> template -> output pipeline.

## Core Architecture

### Content Processing Pipeline

1. **Parse** YAML front matter + Markdown body from `content/posts/*.md` and `content/pages/*.md`
2. **Transform** Markdown to HTML using the `markdown` library
3. **Render** with Jinja2 templates based on content type
4. **Output** to clean URL structure: `/posts/<slug>/index.html`

### Key Components to Implement

- `src/generator/` - Core generator package with layered architecture
- `src/cli.py` - Command-line interface and main entry point
- `config.yaml` - Site-wide settings (title, base_url, author, timezone)
- `templates/` - Jinja2 templates with inheritance (`base.html` -> `post.html`, `index.html`, `tag.html`)
- `content/` - Source Markdown files with front matter
- `static/` - CSS/JS assets (copied to `site/static/`)

## Expected Directory Structure

```
static-site-gen/                 # Project root
|-- src/                         # Source code layer
|   |-- generator/               # Core generator package
|   |   |-- __init__.py
|   |   |-- core.py             # Main build engine
|   |   |-- parser.py           # Content parsing
|   |   |-- renderer.py         # Template rendering
|   |   +-- utils.py            # Utilities
|   +-- cli.py                   # Command-line interface
|-- content/                     # Content layer
|   |-- posts/                   # Blog posts with YYYY-MM-DD-slug.md naming
|   +-- pages/                   # Static pages (about.md, etc.)
|-- templates/                   # Presentation layer
|   |-- base.html               # Shared layout with header/footer
|   |-- post.html               # Individual post template
|   |-- index.html              # Homepage with post listing
|   +-- tag.html                # Tag archive pages
|-- static/                      # Static assets
|   +-- style.css               # Site styles
|-- site/                        # Generated site (git-ignored)
|-- config.yaml                  # Site configuration
|-- requirements.txt             # Dependencies
|-- pyproject.toml              # Modern Python project config
+-- README.md
```

## Content Model Conventions

### Front Matter Schema

Required: `title`, `date`
Optional: `tags` (list), `draft` (boolean), `description`, `slug`

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

### URL Generation Rules

- Posts: `/posts/<slug>/index.html` (slug auto-generated from title if missing)
- Tags: `/tag/<tag>/index.html`
- Pages: `/<slug>/index.html`
- Static assets: `/static/...`

## Implementation Guidelines

### Template Inheritance Pattern

Use Jinja2 template inheritance with `base.html` providing shared layout:

- `{% extends "base.html" %}` in all page templates
- `{% block content %}...{% endblock %}` for page-specific content
- `{% block title %}...{% endblock %}` for page titles

### Build Process Flow

1. Load and validate `config.yaml`
1. Scan `content/` directory for Markdown files
1. Parse front matter and validate required fields
1. Convert Markdown -> HTML with extensions
1. Render templates with content data
1. Generate index page from sorted posts
1. Create tag archive pages
1. Build RSS feed (`feed.xml`)
1. Copy static assets to `site/static/`

### Error Handling Priorities

- Validate front matter fields before processing
- Handle missing slugs (auto-generate from title)
- Skip draft posts unless in development mode
- Graceful handling of malformed Markdown/YAML

## Dependencies

- `markdown` - Markdown parsing with extensions support
- `jinja2` - Template rendering engine
- `pyyaml` - YAML front matter parsing

## Development Tooling

- `pytest` - Testing framework (development dependency)
- `black`
- `isort`
- `mdformat`
- `ruff`
- `pytest`

## Development Workflow

- Run `python -m src.cli build` to build site
- Output goes to `site/` directory
- Serve locally for testing: `python -m http.server -d site`
- Configuration changes require full rebuild

## Coding Standards

### 0. Guiding Ethos

Code should invite understanding.\
Good software is not just functional -- it is *legible thought*.\
Generate and refactor Python code as though explaining an idea to a future collaborator of good will and limited time.

### 1. AI Behavior Preamble

When writing or refactoring code:

- **Primary Objective:** produce Python that is *clear, minimal, and conceptually deep*.
- **Prioritize** long-term readability over short-term cleverness.
- **Avoid** over-generalization, "Clean Code fragmentation," or needless patterns.
- **Balance** explicitness with rhythm -- the code should read naturally in Python's idiom.
- When rules conflict, follow this hierarchy:
  1. **Clarity of intent**
  2. **Simplicity of structure**
  3. **Depth of abstraction**
  4. **Harmony with the surrounding codebase**

### 2. Structural Rules

- Each module should embody a *single, coherent idea*.
- Prefer **deep modules** (simple interface, rich implementation) over thin wrappers.
- **Hide complexity, not meaning** -- interfaces should name the problem domain, not internal mechanics.
- Avoid "manager," "util," or "helper" suffixes; express intent.
- Let architecture *emerge* through iteration, not anticipation.

### 3. Functions and Classes

- Keep functions short but **complete in thought**; don't explode logic into fragments.
- Function names are **verbs**; class names are **nouns**.
- Classes should clarify boundaries, not multiply them.
- Use `@dataclass` for simple data aggregates; no inheritance unless it pays for itself.
- Favor composition over hierarchy.

### 4. Pythonic Practices

- Follow **PEP 8**, but value **clarity over conformance**.
- **Use pure ASCII** in code and documentation when possible - avoid Unicode symbols, fancy quotes, em-dashes, etc.
- Prefer:
  - `with` for resource handling
  - f-strings for formatting
  - comprehensions for obvious collection transforms
  - `enumerate`, `zip`, unpacking over index loops
- Return early; flatten control flow.
- Avoid cleverness disguised as terseness.

### 5. Documentation and Comments

- Docstrings describe *purpose and contract*, not implementation.
- Inline comments explain *why this is hard*, not *what this does*.
- If a comment paraphrases the code, delete it.
- If a comment captures reasoning, preserve it.
- **Character encoding**: Use pure ASCII characters in code, comments, and documentation when possible. Replace Unicode symbols with ASCII equivalents:
  - Use `->` instead of `->`
  - Use `--` instead of `--` (em-dash)
  - Use regular quotes `"` instead of smart quotes `""`
  - Use `...` instead of `...` (ellipsis character)

### 6. Testing

- Write tests that reveal **behavior**, not internals.
- Use **pytest** with descriptive names and parametrization.
- Keep tests **fast, isolated, and explicit**.
- A test should read like an example of correct reasoning.

### 7. Refactoring Guidance

When improving code:

- Simplify public interfaces first; internal cleanup follows.
- Inline trivial abstractions; extract only when repeated or conceptually distinct.
- Rename freely for clarity -- words cost less than confusion.
- Prefer deletion to addition when removing noise clarifies intent.
- Never optimize before measuring.
- Preserve correctness above aesthetic purity.

### 8. Review Checklist

Before accepting or generating code:

1. Can the purpose be explained in one sentence?
2. Is the naming intentional and domain-aligned?
3. Is complexity hidden behind a simple surface?
4. Could a new contributor follow the flow without external context?
5. Would this design make the *next change easier*?

### 9. Synthesis

> **Goal:** Clean + Pythonic + Deep.\
> **Formula:** clarity x intent x simplicity x encapsulated complexity.\
> **Motto:** *Write code that respects the reader.*
