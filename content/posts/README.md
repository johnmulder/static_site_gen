# Blog Posts

This directory contains blog post content in Markdown format with YAML front matter.

## Naming Convention

Posts should follow the naming pattern: `YYYY-MM-DD-slug.md`

Examples:

- `2025-08-07-my-first-post.md`
- `2025-10-15-python-static-sites.md`

## Front Matter Schema

Each post must include YAML front matter with the following fields:

### Required Fields

- `title`: Post title (string)
- `date`: Publication date (YYYY-MM-DD format)

### Optional Fields

- `tags`: List of tags for categorization
- `draft`: Boolean flag to exclude from production builds
- `description`: Short summary for RSS/meta tags
- `slug`: Custom URL slug (auto-generated from title if omitted)

## Example Post Structure

```markdown
---
title: "My First Post"
date: 2025-08-07
tags: [python, static-site]
draft: false
description: "A short summary for cards/RSS/meta"
slug: my-first-post
---

# Post Content

Your Markdown content goes here...
```
