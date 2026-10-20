"""
Template rendering engine for static site generation.

This module handles template loading, rendering, and inheritance using Jinja2.
Provides clean separation between content and presentation layers.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, pass_context
from jinja2.runtime import Context

from .output import generate_page_url, generate_post_url, generate_tag_url


@pass_context
def _site_url(context: Context, path: str) -> str:
    """Mount a root-relative route at the configured site prefix."""
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("site_url requires a root-relative URL path")
    return str(context["site"].url_prefix) + path


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
            site_url=_site_url,
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
