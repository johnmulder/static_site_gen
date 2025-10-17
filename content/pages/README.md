# Static Pages

This directory contains static page content in Markdown format with YAML front matter.

Static pages are standalone content like About, Contact, or other informational pages that are not part of the chronological blog feed.

## Front Matter Schema

Each page should include YAML front matter with these fields:

### Required Fields

- `title`: Page title (string)
- `date`: Creation/update date (YYYY-MM-DD format)

### Optional Fields

- `description`: Short summary for meta tags
- `slug`: Custom URL slug (auto-generated from title if omitted)
- `draft`: Boolean flag to exclude from production builds

## URL Generation

Pages are generated at: `/<slug>/index.html`

Examples:

- `about.md` -> `/about/index.html`
- `contact.md` -> `/contact/index.html`

## Example Page Structure

```markdown
---
title: "About"
date: 2025-10-17
description: "Learn more about this site and its author"
slug: about
---

# About This Site

Your page content goes here...
```
