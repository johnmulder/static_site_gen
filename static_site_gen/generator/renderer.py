"""
Template rendering engine for static site generation.

This module handles template loading, rendering, and inheritance using Jinja2.
Provides clean separation between content and presentation layers.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .output import generate_page_url, generate_post_url, generate_tag_url


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
        self.env.filters.update(
            page_url=generate_page_url,
            post_url=generate_post_url,
            tag_url=generate_tag_url,
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
