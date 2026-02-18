"""
Core build engine for the static site generator.

This module contains the main build orchestration logic that coordinates
the entire content -> template -> output pipeline.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from .output import (
    clean_output_dir,
    collect_posts_by_tag,
    copy_static_files,
    generate_page_url,
    generate_post_url,
    generate_tag_url,
    get_output_path,
    paginate_posts,
    sort_posts_by_date,
    write_file,
)
from .parser import ParseError, parse_content_file
from .renderer import TemplateRenderer


@dataclass
class SiteConfig:
    """
    Validated site configuration.

    All required fields are guaranteed present after construction.
    Optional fields carry sensible defaults.
    """

    site_name: str
    base_url: str
    author: str
    timezone: str = "UTC"
    output_dir: str = "site"
    posts_per_page: int = 10
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    markdown_extensions: list[str] = field(
        default_factory=lambda: ["codehilite", "tables", "toc"]
    )

    @classmethod
    def from_yaml(cls, filepath: Path) -> "SiteConfig":
        """
        Load and validate configuration from a YAML file.

        Args:
            filepath: Path to config.yaml

        Returns:
            Validated SiteConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If required fields are missing or invalid
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        with open(filepath, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if raw is None:
            raise ValueError("Configuration file is empty or invalid")

        required_fields = ["site_name", "base_url", "author"]
        missing = [f for f in required_fields if f not in raw]
        if missing:
            raise ValueError(f"Missing required config fields: {missing}")

        invalid = []
        for name in required_fields:
            value = raw[name]
            if value is None:
                invalid.append(f"{name} is null")
            elif isinstance(value, str) and not value.strip():
                invalid.append(f"{name} is empty")
            elif not isinstance(value, str):
                invalid.append(f"{name} must be a string, got {type(value).__name__}")
        if invalid:
            raise ValueError(f"Invalid required config fields: {', '.join(invalid)}")

        posts_per_page = raw.get("posts_per_page", 10)
        if not isinstance(posts_per_page, int) or posts_per_page <= 0:
            raise ValueError(
                f"posts_per_page must be a positive integer, got: {posts_per_page}"
            )

        parsed_url = urlparse(raw["base_url"])
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(
                f"base_url must be a valid absolute HTTP/HTTPS URL, got: {raw['base_url']}"
            )

        timezone = raw.get("timezone", "UTC")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Invalid timezone setting: {timezone}") from exc

        return cls(
            site_name=raw["site_name"],
            base_url=raw["base_url"],
            author=raw["author"],
            timezone=timezone,
            output_dir=raw.get("output_dir", "site"),
            posts_per_page=posts_per_page,
            description=raw.get("description", ""),
            keywords=raw.get("keywords", []),
            markdown_extensions=raw.get(
                "markdown_extensions", ["codehilite", "tables", "toc"]
            ),
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

        self.config: SiteConfig | None = None
        self.renderer: TemplateRenderer | None = None

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

    def load_config(self) -> SiteConfig:
        """
        Load and validate site configuration.

        Returns:
            Validated SiteConfig instance

        Raises:
            FileNotFoundError: If config.yaml doesn't exist
            ValueError: If required configuration fields are missing or invalid
        """
        config = SiteConfig.from_yaml(self.config_file)
        self.config = config
        return config

    def discover_content(self) -> dict[str, list[Path]]:
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

    def _process_content_files(self, files: list[Path], label: str) -> list[Any]:
        """
        Parse content files with slug collision resolution.

        Args:
            files: List of Markdown file paths to process
            label: Human-readable label for error messages (e.g. 'post', 'page')

        Returns:
            List of ParsedContent objects
        """
        assert self.config is not None

        extensions = self.config.markdown_extensions
        timezone = self.config.timezone
        slugs: set[str] = set()
        results: list[Any] = []

        for filepath in files:
            try:
                parsed = parse_content_file(filepath, extensions, timezone)

                original_slug = parsed.metadata.slug
                final_slug = self._resolve_slug_collision(original_slug, slugs)

                if final_slug != original_slug:
                    print(
                        f"Warning: {label.capitalize()} slug collision resolved "
                        f"for '{parsed.metadata.title}': '{original_slug}' -> '{final_slug}'"
                    )
                    parsed.metadata = replace(parsed.metadata, slug=final_slug)

                slugs.add(final_slug)
                results.append(parsed)
            except (ParseError, OSError, ValueError) as e:
                print(f"Error processing {label} {filepath}: {e}")
                continue

        return results

    def process_content(self, content_files: dict[str, list[Path]]) -> dict[str, list]:
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

        return {
            "posts": self._process_content_files(content_files["posts"], "post"),
            "pages": self._process_content_files(content_files["pages"], "page"),
        }

    def generate_posts(self, posts: list[Any]) -> None:
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
                html_content = self.renderer.render_post(post.to_dict(), self.config)
                url_path = generate_post_url(post.metadata.slug)
                output_path = get_output_path(self.output_dir, url_path)
                write_file(output_path, html_content)
            except (OSError, ValueError) as e:
                print(
                    f"Error generating post '{post.metadata.title}' ({post.metadata.slug}): {e}"
                )
                continue

    def generate_index(self, posts: list) -> None:
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
            posts_dict = [post.to_dict() for post in posts]

            sorted_posts = sort_posts_by_date(posts_dict)

            posts_per_page = self.config.posts_per_page

            pages = paginate_posts(sorted_posts, posts_per_page)

            for page_info in pages:
                if page_info["page_number"] == 1:
                    output_path = self.output_dir / "index.html"
                else:
                    page_dir = self.output_dir / "page" / str(page_info["page_number"])
                    page_dir.mkdir(parents=True, exist_ok=True)
                    output_path = page_dir / "index.html"

                page_posts = page_info["posts"]
                pagination = {
                    "current_page": page_info["page_number"],
                    "total_pages": page_info["total_pages"],
                    "has_prev": page_info["has_previous"],
                    "has_next": page_info["has_next"],
                    "prev_url": page_info["previous_url"],
                    "next_url": page_info["next_url"],
                }

                html_content = self.renderer.render_index_page(
                    page_posts, self.config, pagination
                )
                write_file(output_path, html_content)

        except (OSError, ValueError) as e:
            print(f"Error generating index pages: {e}")
            raise

    def generate_tag_pages(self, posts: list[Any]) -> None:
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

        posts_dict = [post.to_dict() for post in posts]

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
            except (OSError, ValueError) as e:
                print(f"Error generating tag page for '{tag}': {e}")
                continue

    def generate_feed(self, posts: list[Any]) -> None:
        """
        Generate RSS feed from published posts.

        Args:
            posts: List of ParsedContent objects (will be sorted by date)
        """
        assert (
            self.renderer is not None
        ), "Renderer must be initialized before generating feed"
        assert (
            self.config is not None
        ), "Configuration must be loaded before generating feed"

        try:
            posts_dict = [post.to_dict() for post in posts]
            sorted_posts = sort_posts_by_date(posts_dict)

            xml_content = self.renderer.render_feed(sorted_posts, self.config)
            feed_path = self.output_dir / "feed.xml"
            write_file(feed_path, xml_content)
        except (OSError, ValueError) as e:
            print(f"Error generating RSS feed: {e}")

    def generate_pages(self, pages: list[Any]) -> None:
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
                html_content = self.renderer.render_page(page.to_dict(), self.config)

                url_path = generate_page_url(page.metadata.slug)
                output_path = get_output_path(self.output_dir, url_path)

                write_file(output_path, html_content)
            except (OSError, ValueError) as e:
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

        self.output_dir = self.project_root / self.config.output_dir

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

            print("Generating RSS feed...")
            self.generate_feed(posts)

        if pages:
            print("Generating static pages...")
            self.generate_pages(pages)

        # Copy static assets
        print("Copying static assets...")
        self.copy_assets()

        print(f"Site build complete! Generated site in: {self.output_dir}")
