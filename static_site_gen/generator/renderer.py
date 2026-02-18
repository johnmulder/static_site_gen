"""
Template rendering engine for static site generation.

This module handles template loading, rendering, and inheritance using Jinja2.
Provides clean separation between content and presentation layers.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class TemplateRenderer:
    """
    Jinja2 template renderer with inheritance support.

    Manages template loading, rendering, and provides context data
    for site generation. Supports template inheritance through Jinja2's
    built-in extends mechanism.
    """

    def __init__(self, template_dir: Path):
        """
        Initialize renderer with template directory.

        Args:
            template_dir: Path to directory containing Jinja2 templates

        Raises:
            FileNotFoundError: If template directory doesn't exist
        """
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,  # Security: auto-escape HTML
            trim_blocks=True,  # Clean whitespace handling
            lstrip_blocks=True,
        )

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """
        Render template with given context data.

        Args:
            template_name: Name of template file (e.g., 'post.html')
            context: Dictionary of variables to pass to template

        Returns:
            Rendered HTML string

        Raises:
            TemplateNotFound: If template file doesn't exist
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except TemplateNotFound as e:
            raise TemplateNotFound(
                f"Template '{template_name}' not found in {self.template_dir}"
            ) from e

    def render_post(
        self, post_data: dict[str, Any], site_config: dict[str, Any]
    ) -> str:
        """
        Render individual blog post using post.html template.

        Args:
            post_data: Parsed post metadata and content
            site_config: Site-wide configuration data

        Returns:
            Rendered post HTML
        """
        context = {
            "post": post_data,
            "site": site_config,
            "page_title": post_data.get("title", "Untitled Post"),
        }
        return self.render_template("post.html", context)

    def render_index(self, posts: list, site_config: dict[str, Any]) -> str:
        """
        Render homepage with list of posts using index.html template.

        Args:
            posts: List of post metadata dictionaries, sorted by date
            site_config: Site-wide configuration data

        Returns:
            Rendered index HTML
        """
        context = {
            "posts": posts,
            "site": site_config,
            "page_title": site_config.get("site_name", "Blog"),
        }
        return self.render_template("index.html", context)

    def render_index_page(
        self, posts: list, site_config: dict[str, Any], pagination: dict[str, Any]
    ) -> str:
        """
        Render paginated index page using index.html template.

        Args:
            posts: List of post metadata dictionaries for this page
            site_config: Site-wide configuration data
            pagination: Pagination context (current_page, total_pages, etc.)

        Returns:
            Rendered paginated index HTML
        """
        page_title = site_config.get("site_name", "Blog")
        if pagination["current_page"] > 1:
            page_title += f" - Page {pagination['current_page']}"

        context = {
            "posts": posts,
            "site": site_config,
            "pagination": pagination,
            "page_title": page_title,
        }
        return self.render_template("index.html", context)

    def render_tag_page(
        self, tag: str, posts: list, site_config: dict[str, Any]
    ) -> str:
        """
        Render tag archive page using tag.html template.

        Args:
            tag: Tag name for this archive
            posts: List of posts with this tag
            site_config: Site-wide configuration data

        Returns:
            Rendered tag archive HTML
        """
        context = {
            "tag": tag,
            "posts": posts,
            "site": site_config,
            "page_title": f"Posts tagged '{tag}'",
        }
        return self.render_template("tag.html", context)

    def render_page(
        self,
        page_data: dict[str, Any],
        site_config: dict[str, Any],
        template_name: str | None = None,
    ) -> str:
        """
        Render static page with optional custom template.

        Args:
            page_data: Parsed page metadata and content
            site_config: Site-wide configuration data
            template_name: Optional custom template (defaults to 'page.html')

        Returns:
            Rendered page HTML
        """
        template = template_name or "page.html"
        context = {
            "page": page_data,
            "site": site_config,
            "page_title": page_data.get("title", "Untitled Page"),
        }
        return self.render_template(template, context)

    def render_feed(self, posts: list, site_config: dict[str, Any]) -> str:
        """
        Render RSS feed using feed.xml template.

        Args:
            posts: List of post dictionaries, sorted by date
            site_config: Site-wide configuration data

        Returns:
            Rendered RSS XML string
        """
        context = {
            "posts": posts,
            "site": site_config,
        }
        return self.render_template("feed.xml", context)

    def get_available_templates(self) -> list:
        """
        Get list of available template files.

        Returns:
            List of template filenames in template directory
        """
        return [f.name for f in self.template_dir.iterdir() if f.is_file()]
