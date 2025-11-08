"""
Additional tests for renderer module edge cases.

These tests target specific uncovered functionality in template rendering,
error handling, and edge cases.
"""

import pytest
from jinja2 import TemplateNotFound, TemplateSyntaxError

from static_site_gen.generator.renderer import TemplateRenderer


class TestRendererEdgeCases:
    """Test edge cases and error conditions in TemplateRenderer."""

    def test_template_not_found_error(self, tmp_path):
        """Test behavior when template file doesn't exist."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        renderer = TemplateRenderer(templates_dir)

        with pytest.raises(TemplateNotFound):
            renderer.render_template("nonexistent.html", {})

    def test_template_syntax_error(self, tmp_path):
        """Test behavior with invalid template syntax."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create template with syntax error
        (templates_dir / "bad.html").write_text(
            """
{% extends "base.html" %}
{% block content %}
    {% for item in items %}
        <p>{{ item.title }}</p>
    {% # Missing endfor %}
{% endblock %}
"""
        )

        renderer = TemplateRenderer(templates_dir)

        with pytest.raises(TemplateSyntaxError):
            renderer.render_template("bad.html", {"items": []})

    def test_missing_template_variable(self, tmp_path):
        """Test behavior when template references undefined variable."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create template that references undefined variable
        (templates_dir / "undefined_var.html").write_text(
            """
<h1>{{ title | default("No Title") }}</h1>
"""
        )

        renderer = TemplateRenderer(templates_dir)

        # Should render with default value when variable is missing
        result = renderer.render_template("undefined_var.html", {})
        assert "<h1>No Title</h1>" in result

    def test_complex_template_inheritance_chain(self, tmp_path):
        """Test complex template inheritance with multiple levels."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create base template
        (templates_dir / "base.html").write_text(
            """
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Default Title{% endblock %}</title>
</head>
<body>
    <header>{% block header %}Default Header{% endblock %}</header>
    <main>{% block content %}{% endblock %}</main>
    <footer>{% block footer %}Default Footer{% endblock %}</footer>
</body>
</html>
"""
        )

        # Create intermediate template
        (templates_dir / "layout.html").write_text(
            """
{% extends "base.html" %}
{% block header %}
<h1>Site Header</h1>
{% endblock %}
{% block footer %}
<p>Site Footer</p>
{% endblock %}
"""
        )

        # Create final template
        (templates_dir / "page.html").write_text(
            """
{% extends "layout.html" %}
{% block title %}{{ page_title }}{% endblock %}
{% block content %}
<article>{{ content }}</article>
{% endblock %}
"""
        )

        renderer = TemplateRenderer(templates_dir)

        result = renderer.render_template(
            "page.html", {"page_title": "Test Page", "content": "<p>Hello World</p>"}
        )

        assert "Test Page" in result
        assert "Site Header" in result
        assert "Site Footer" in result
        # HTML content should be escaped for security
        assert "&lt;p&gt;Hello World&lt;/p&gt;" in result

    def test_autoescape_security_feature(self, tmp_path):
        """Test that HTML content is properly escaped for security."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create template that outputs user content
        (templates_dir / "content.html").write_text(
            """
<div>{{ user_content }}</div>
"""
        )

        renderer = TemplateRenderer(templates_dir)

        # Test with potentially malicious content
        malicious_content = '<script>alert("xss")</script>'

        result = renderer.render_template(
            "content.html", {"user_content": malicious_content}
        )

        # Should be escaped
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_template_with_filters_and_functions(self, tmp_path):
        """Test templates using Jinja2 built-in filters."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        (templates_dir / "filters.html").write_text(
            """
<p>Title: {{ title | title }}</p>
<p>Count: {{ items | length }}</p>
<p>Upper: {{ text | upper }}</p>
<p>Default: {{ missing_var | default("fallback") }}</p>
"""
        )

        renderer = TemplateRenderer(templates_dir)

        result = renderer.render_template(
            "filters.html",
            {"title": "hello world", "items": [1, 2, 3, 4, 5], "text": "testing"},
        )

        assert "Title: Hello World" in result
        assert "Count: 5" in result
        assert "Upper: TESTING" in result
        assert "Default: fallback" in result

    def test_empty_template_directory(self, tmp_path):
        """Test renderer initialization with empty template directory."""
        templates_dir = tmp_path / "empty_templates"
        templates_dir.mkdir()

        # Should initialize without error
        renderer = TemplateRenderer(templates_dir)
        assert renderer is not None

        # But should fail when trying to render non-existent template
        with pytest.raises(TemplateNotFound):
            renderer.render_template("anything.html", {})

    def test_nested_template_directories(self, tmp_path):
        """Test templates in nested directories."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create nested structure
        blog_dir = templates_dir / "blog"
        blog_dir.mkdir()

        (templates_dir / "base.html").write_text(
            """
<!DOCTYPE html>
<html><body>{% block content %}{% endblock %}</body></html>
"""
        )

        (blog_dir / "post.html").write_text(
            """
{% extends "base.html" %}
{% block content %}
<article>
    <h1>{{ post.title }}</h1>
    <div>{{ post.content }}</div>
</article>
{% endblock %}
"""
        )

        renderer = TemplateRenderer(templates_dir)

        result = renderer.render_template(
            "blog/post.html",
            {"post": {"title": "Test Post", "content": "Test content"}},
        )

        assert "Test Post" in result
        assert "Test content" in result
        assert "<article>" in result
