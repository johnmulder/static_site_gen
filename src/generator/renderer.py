"""
Template rendering module using Jinja2.

This module manages the template rendering system for converting parsed
content into HTML output. It handles:

- Jinja2 template environment setup and configuration
- Template inheritance system (base.html -> specific templates)
- Context data preparation for template rendering
- Template loading and caching
- Error handling for missing or malformed templates

Template inheritance pattern:
- base.html: Shared layout with header/footer
- post.html: Individual post template (extends base.html)
- index.html: Homepage with post listing (extends base.html)
- tag.html: Tag archive pages (extends base.html)

Template context data includes:
- Content metadata (title, date, tags, etc.)
- Site configuration (site_name, base_url, author)
- Navigation data (post listings, tag collections)
- Build metadata (generation time, etc.)

The renderer supports:
- Clean URL generation (/posts/<slug>/index.html)
- Template block inheritance ({% block content %}, {% block title %})
- Auto-escaping for security
- Custom filters and functions as needed

Design principles:
- Separation of content and presentation
- Consistent context data structure
- Clear error messages for template issues
- Performance through template caching
"""
