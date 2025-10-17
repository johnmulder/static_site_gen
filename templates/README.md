# Jinja2 Templates

This directory contains Jinja2 templates for rendering HTML output from Markdown content.

## Template Inheritance Structure

The template system uses Jinja2's inheritance pattern:

- `base.html` - Shared layout with header, footer, and common HTML structure
- `post.html` - Individual blog post template (extends base.html)
- `index.html` - Homepage with chronological post listing (extends base.html)
- `tag.html` - Tag archive pages showing posts by tag (extends base.html)

## Template Inheritance Pattern

All page templates extend `base.html`:

```jinja2
{% extends "base.html" %}

{% block title %}{{ post.title }}{% endblock %}

{% block content %}
<article>
    <h1>{{ post.title }}</h1>
    <time>{{ post.date }}</time>
    <div class="content">
        {{ post.content | safe }}
    </div>
</article>
{% endblock %}
```

## Available Template Blocks

- `{% block title %}` - Page title for <title> tag
- `{% block content %}` - Main page content area
- `{% block head %}` - Additional <head> content (optional)
- `{% block scripts %}` - JavaScript includes (optional)

## Template Context Data

Templates receive context data including:

- `site` - Site configuration (site_name, base_url, author)
- `post` - Current post data (for post.html)
- `posts` - List of posts (for index.html, tag.html)
- `tags` - Available tags collection
- `current_tag` - Current tag (for tag.html)
