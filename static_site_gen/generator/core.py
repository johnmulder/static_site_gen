"""
Core build engine for the static site generator.

This module contains the main build orchestration logic that coordinates
the entire content -> template -> output pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .parser import parse_content_file
from .renderer import TemplateRenderer
from .utils import (
    clean_output_dir,
    collect_posts_by_tag,
    copy_static_files,
    generate_page_url,
    generate_pagination_url,
    generate_post_url,
    generate_tag_url,
    get_output_path,
    paginate_posts,
    sort_posts_by_date,
    write_file,
)


class SiteGenerator:
    """
    Main site generation orchestrator.

    Coordinates parsing, rendering, and file generation for the entire site.
    Manages the build process from configuration loading to output generation.
    """

    def __init__(self, project_root: Path):
        """
        Initialize generator with project root directory.

        Args:
            project_root: Path to project root containing config.yaml
        """
        self.project_root = project_root
        self.config_file = project_root / "config.yaml"
        self.content_dir = project_root / "content"
        self.template_dir = project_root / "templates"
        self.static_dir = project_root / "static"
        self.output_dir = project_root / "site"

        self.config: Optional[Dict[str, Any]] = None
        self.renderer: Optional[TemplateRenderer] = None

    def _resolve_slug_collision(self, slug: str, existing_slugs: set) -> str:
        """
        Resolve slug collisions by appending numbers.

        Args:
            slug: Original slug
            existing_slugs: Set of already used slugs

        Returns:
            Unique slug (original or with numeric suffix)
        """
        if slug not in existing_slugs:
            return slug

        counter = 2
        while True:
            candidate = f"{slug}-{counter}"
            if candidate not in existing_slugs:
                return candidate
            counter += 1

    def load_config(self) -> Dict[str, Any]:
        """
        Load and validate site configuration.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config.yaml doesn't exist
            ValueError: If required configuration fields are missing
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

        with open(self.config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            raise ValueError("Configuration file is empty or invalid")

        required_fields = ["site_name", "base_url", "author"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required config fields: {missing_fields}")

        # Validate that required fields are not null or empty
        invalid_fields = []
        for field in required_fields:
            value = config[field]
            if value is None:
                invalid_fields.append(f"{field} is null")
            elif isinstance(value, str) and not value.strip():
                invalid_fields.append(f"{field} is empty")
            elif not isinstance(value, str):
                invalid_fields.append(
                    f"{field} must be a string, got {type(value).__name__}"
                )

        if invalid_fields:
            raise ValueError(
                f"Invalid required config fields: {', '.join(invalid_fields)}"
            )

        config.setdefault("timezone", "UTC")
        config.setdefault("output_dir", "site")

        posts_per_page = config.get("posts_per_page", 10)
        if not isinstance(posts_per_page, int) or posts_per_page <= 0:
            raise ValueError(
                f"posts_per_page must be a positive integer, got: {posts_per_page}"
            )

        self.config = config
        return config

    def discover_content(self) -> Dict[str, List[Path]]:
        """
        Discover all content files in content directory.

        Returns:
            Dictionary with 'posts' and 'pages' lists of file paths
        """
        posts_dir = self.content_dir / "posts"
        pages_dir = self.content_dir / "pages"

        content_files = {
            "posts": list(posts_dir.glob("*.md")) if posts_dir.exists() else [],
            "pages": list(pages_dir.glob("*.md")) if pages_dir.exists() else [],
        }

        return content_files

    def process_content(self, content_files: Dict[str, List[Path]]) -> Dict[str, List]:
        """
        Parse and process all content files.

        Args:
            content_files: Dictionary with 'posts' and 'pages' file lists

        Returns:
            Dictionary with parsed 'posts' and 'pages' data
        """
        assert (
            self.config is not None
        ), "Configuration must be loaded before processing content"

        processed_content = {"posts": [], "pages": []}

        markdown_extensions = self.config.get(
            "markdown_extensions", ["extra", "codehilite", "toc"]
        )
        timezone = self.config.get("timezone", "UTC")

        post_slugs = set()
        for post_file in content_files["posts"]:
            try:
                post_data = parse_content_file(post_file, markdown_extensions, timezone)

                original_slug = post_data.metadata.slug
                final_slug = self._resolve_slug_collision(original_slug, post_slugs)

                if final_slug != original_slug:
                    print(
                        f"Warning: Slug collision resolved for '{post_data.metadata.title}': '{original_slug}' -> '{final_slug}'"
                    )
                    from dataclasses import replace

                    # Preserve all original metadata, only changing the slug
                    post_data.metadata = replace(post_data.metadata, slug=final_slug)

                post_slugs.add(final_slug)
                processed_content["posts"].append(post_data)
            except Exception as e:
                print(f"Error processing post {post_file}: {e}")
                continue

        page_slugs = set()
        for page_file in content_files["pages"]:
            try:
                page_data = parse_content_file(page_file, markdown_extensions, timezone)

                original_slug = page_data.metadata.slug
                final_slug = self._resolve_slug_collision(original_slug, page_slugs)

                if final_slug != original_slug:
                    print(
                        f"Warning: Page slug collision resolved for '{page_data.metadata.title}': '{original_slug}' -> '{final_slug}'"
                    )
                    from dataclasses import replace

                    # Preserve all original metadata, only changing the slug
                    page_data.metadata = replace(page_data.metadata, slug=final_slug)

                page_slugs.add(final_slug)
                processed_content["pages"].append(page_data)
            except Exception as e:
                print(f"Error processing page {page_file}: {e}")
                continue

        return processed_content

    def generate_posts(self, posts: List[Any]) -> None:
        """
        Generate individual post pages.

        Args:
            posts: List of ParsedContent objects
        """
        assert (
            self.renderer is not None
        ), "Renderer must be initialized before generating posts"
        assert (
            self.config is not None
        ), "Configuration must be loaded before generating posts"

        for post in posts:
            try:
                post_dict = {
                    "title": post.metadata.title,
                    "date": post.metadata.date,
                    "slug": post.metadata.slug,
                    "tags": post.metadata.tags,
                    "draft": post.metadata.draft,
                    "description": post.metadata.description,
                    "content": post.content,
                }

                html_content = self.renderer.render_post(post_dict, self.config)
                url_path = generate_post_url(post.metadata.slug)
                output_path = get_output_path(self.output_dir, url_path)
                write_file(output_path, html_content)
            except Exception as e:
                print(
                    f"Error generating post '{post.metadata.title}' ({post.metadata.slug}): {e}"
                )
                continue

    def generate_index(self, posts: List) -> None:
        """
        Generate homepage with chronologically sorted posts, including pagination.

        Args:
            posts: List of ParsedContent objects (will be sorted by date)
        """
        assert (
            self.renderer is not None
        ), "Renderer must be initialized before generating index"
        assert (
            self.config is not None
        ), "Configuration must be loaded before generating index"

        try:
            posts_dict = []
            for post in posts:
                posts_dict.append(
                    {
                        "title": post.metadata.title,
                        "date": post.metadata.date,
                        "slug": post.metadata.slug,
                        "tags": post.metadata.tags,
                        "draft": post.metadata.draft,
                        "description": post.metadata.description,
                        "content": post.content,
                    }
                )

            sorted_posts = sort_posts_by_date(posts_dict)

            posts_per_page = self.config.get("posts_per_page", 10)

            pages = paginate_posts(sorted_posts, posts_per_page)

            for page_info in pages:
                if page_info["page_number"] == 1:
                    output_path = self.output_dir / "index.html"
                else:
                    page_dir = self.output_dir / "page" / str(page_info["page_number"])
                    page_dir.mkdir(parents=True, exist_ok=True)
                    output_path = page_dir / "index.html"

                posts = page_info["posts"]
                pagination = {
                    "current_page": page_info["page_number"],
                    "total_pages": page_info["total_pages"],
                    "has_prev": page_info["has_previous"],
                    "has_next": page_info["has_next"],
                    "prev_url": page_info["previous_url"],
                    "next_url": page_info["next_url"],
                }

                html_content = self.renderer.render_index_page(
                    posts, self.config, pagination
                )
                write_file(output_path, html_content)

        except Exception as e:
            print(f"Error generating index pages: {e}")
            raise

    def generate_tag_pages(self, posts: List[Any]) -> None:
        """
        Generate tag archive pages.

        Args:
            posts: List of ParsedContent objects
        """
        assert (
            self.renderer is not None
        ), "Renderer must be initialized before generating tag pages"
        assert (
            self.config is not None
        ), "Configuration must be loaded before generating tag pages"

        posts_dict = []
        for post in posts:
            posts_dict.append(
                {
                    "title": post.metadata.title,
                    "date": post.metadata.date,
                    "slug": post.metadata.slug,
                    "tags": post.metadata.tags,
                    "draft": post.metadata.draft,
                    "description": post.metadata.description,
                    "content": post.content,
                }
            )

        posts_by_tag = collect_posts_by_tag(posts_dict)

        for tag, tag_posts in posts_by_tag.items():
            try:
                sorted_posts = sort_posts_by_date(tag_posts)

                html_content = self.renderer.render_tag_page(
                    tag, sorted_posts, self.config
                )

                url_path = generate_tag_url(tag)
                output_path = get_output_path(self.output_dir, url_path)

                write_file(output_path, html_content)
            except Exception as e:
                print(f"Error generating tag page for '{tag}': {e}")
                continue

    def generate_pages(self, pages: List[Any]) -> None:
        """
        Generate static pages.

        Args:
            pages: List of ParsedContent objects
        """
        assert (
            self.renderer is not None
        ), "Renderer must be initialized before generating pages"
        assert (
            self.config is not None
        ), "Configuration must be loaded before generating pages"

        for page in pages:
            try:
                page_dict = {
                    "title": page.metadata.title,
                    "date": page.metadata.date,
                    "slug": page.metadata.slug,
                    "tags": page.metadata.tags,
                    "draft": page.metadata.draft,
                    "description": page.metadata.description,
                    "content": page.content,
                }

                html_content = self.renderer.render_page(page_dict, self.config)

                url_path = generate_page_url(page.metadata.slug)
                output_path = get_output_path(self.output_dir, url_path)

                write_file(output_path, html_content)
            except Exception as e:
                print(
                    f"Error generating page '{page.metadata.title}' ({page.metadata.slug}): {e}"
                )
                continue

    def copy_assets(self) -> None:
        """
        Copy static assets to output directory.
        """
        if self.static_dir.exists():
            dest_static_dir = self.output_dir / "static"
            copy_static_files(self.static_dir, dest_static_dir)

    def build(self) -> None:
        """
        Execute complete site build process.

        Raises:
            FileNotFoundError: If required directories or files are missing
            ValueError: If configuration is invalid
        """
        print("Starting site build...")

        print("Loading configuration...")
        self.load_config()
        assert self.config is not None, "Configuration should be loaded"

        self.output_dir = self.project_root / self.config["output_dir"]

        print("Initializing template renderer...")
        self.renderer = TemplateRenderer(self.template_dir)

        print("Cleaning output directory...")
        clean_output_dir(self.output_dir)
        print("Discovering content files...")
        content_files = self.discover_content()
        print(
            f"Found {len(content_files['posts'])} posts and {len(content_files['pages'])} pages"
        )

        # Process content
        print("Processing content...")
        processed_content = self.process_content(content_files)

        # Filter published posts
        posts = [post for post in processed_content["posts"] if not post.metadata.draft]
        pages = processed_content["pages"]

        print(f"Processing {len(posts)} published posts and {len(pages)} pages")

        # Generate content
        if posts:
            print("Generating post pages...")
            self.generate_posts(posts)

            print("Generating index page...")
            self.generate_index(posts)

            print("Generating tag pages...")
            self.generate_tag_pages(posts)

        if pages:
            print("Generating static pages...")
            self.generate_pages(pages)

        # Copy static assets
        print("Copying static assets...")
        self.copy_assets()

        print(f"Site build complete! Generated site in: {self.output_dir}")
