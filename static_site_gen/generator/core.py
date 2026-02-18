"""
Core build engine for the static site generator.

This module contains the main build orchestration logic that coordinates
the entire content -> template -> output pipeline.
"""

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
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
from .parser import ParsedContent, ParseError, parse_content_file
from .renderer import TemplateRenderer

logger = logging.getLogger(__name__)


@dataclass
class SiteConfig:  # pylint: disable=too-many-instance-attributes
    """
    Validated site configuration.

    All required fields are guaranteed present after construction.
    Optional fields carry sensible defaults.

    Attributes are kept flat for simplicity -- the config surface is small
    enough that nested dataclasses would add indirection without clarity.
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
        self.output_dir = project_root / "site"

        self.config: SiteConfig | None = None
        self.renderer: TemplateRenderer | None = None

    @property
    def config_file(self) -> Path:
        """Path to the site configuration file."""
        return self.project_root / "config.yaml"

    @property
    def content_dir(self) -> Path:
        """Path to content source directory."""
        return self.project_root / "content"

    @property
    def template_dir(self) -> Path:
        """Path to Jinja2 template directory."""
        return self.project_root / "templates"

    @property
    def static_dir(self) -> Path:
        """Path to static asset directory."""
        return self.project_root / "static"

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

    def _process_content_files(
        self, files: list[Path], label: str
    ) -> list[ParsedContent]:
        """
        Parse content files with slug collision resolution.

        Args:
            files: List of Markdown file paths to process
            label: Human-readable label for error messages (e.g. 'post', 'page')

        Returns:
            List of ParsedContent objects
        """
        if self.config is None:
            raise RuntimeError("Configuration must be loaded before processing content")

        extensions = self.config.markdown_extensions
        timezone = self.config.timezone
        slugs: set[str] = set()
        results: list[ParsedContent] = []

        for filepath in files:
            try:
                parsed = parse_content_file(filepath, extensions, timezone)

                original_slug = parsed.metadata.slug
                final_slug = self._resolve_slug_collision(original_slug, slugs)

                if final_slug != original_slug:
                    logger.warning(
                        "%s slug collision resolved for '%s': '%s' -> '%s'",
                        label.capitalize(),
                        parsed.metadata.title,
                        original_slug,
                        final_slug,
                    )
                    parsed.metadata = replace(parsed.metadata, slug=final_slug)

                slugs.add(final_slug)
                results.append(parsed)
            except (ParseError, OSError, ValueError) as e:
                logger.error("Error processing %s %s: %s", label, filepath, e)
                continue

        return results

    def process_content(
        self, content_files: dict[str, list[Path]]
    ) -> dict[str, list[ParsedContent]]:
        """
        Parse and process all content files.

        Args:
            content_files: Dictionary with 'posts' and 'pages' file lists

        Returns:
            Dictionary with parsed 'posts' and 'pages' data
        """
        if self.config is None:
            raise RuntimeError("Configuration must be loaded before processing content")

        return {
            "posts": self._process_content_files(content_files["posts"], "post"),
            "pages": self._process_content_files(content_files["pages"], "page"),
        }

    def generate_posts(self, posts: list[ParsedContent]) -> None:
        """
        Generate individual post pages.

        Args:
            posts: List of ParsedContent objects
        """
        if self.renderer is None or self.config is None:
            raise RuntimeError(
                "Renderer and config must be initialized before generating posts"
            )

        for post in posts:
            try:
                html_content = self.renderer.render_post(post.to_dict(), self.config)
                url_path = generate_post_url(post.metadata.slug)
                output_path = get_output_path(self.output_dir, url_path)
                write_file(output_path, html_content)
            except (OSError, ValueError) as e:
                logger.error(
                    "Error generating post '%s' (%s): %s",
                    post.metadata.title,
                    post.metadata.slug,
                    e,
                )
                continue

    def generate_index(self, posts: list[ParsedContent]) -> None:
        """
        Generate homepage with chronologically sorted posts, including pagination.

        Args:
            posts: List of ParsedContent objects (will be sorted by date)
        """
        if self.renderer is None or self.config is None:
            raise RuntimeError(
                "Renderer and config must be initialized before generating index"
            )

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
            logger.error("Error generating index pages: %s", e)
            raise

    def generate_tag_pages(self, posts: list[ParsedContent]) -> None:
        """
        Generate tag archive pages.

        Args:
            posts: List of ParsedContent objects
        """
        if self.renderer is None or self.config is None:
            raise RuntimeError(
                "Renderer and config must be initialized before generating tag pages"
            )

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
                logger.error("Error generating tag page for '%s': %s", tag, e)
                continue

    def generate_tag_index(self, posts: list[ParsedContent]) -> None:
        """
        Generate tag index page listing all tags with post counts.

        Args:
            posts: List of published ParsedContent objects
        """
        if self.renderer is None or self.config is None:
            raise RuntimeError(
                "Renderer and config must be initialized before generating tag index"
            )

        posts_dict = [post.to_dict() for post in posts]
        posts_by_tag = collect_posts_by_tag(posts_dict)

        tags_with_counts = sorted(
            [(tag, len(tag_posts)) for tag, tag_posts in posts_by_tag.items()]
        )

        try:
            html_content = self.renderer.render_tag_index(tags_with_counts, self.config)
            output_path = self.output_dir / "tag" / "index.html"
            write_file(output_path, html_content)
        except (OSError, ValueError) as e:
            logger.error("Error generating tag index: %s", e)

    def generate_feed(self, posts: list[ParsedContent]) -> None:
        """
        Generate RSS feed from published posts.

        Args:
            posts: List of ParsedContent objects (will be sorted by date)
        """
        if self.renderer is None or self.config is None:
            raise RuntimeError(
                "Renderer and config must be initialized before generating feed"
            )

        try:
            posts_dict = [post.to_dict() for post in posts]
            sorted_posts = sort_posts_by_date(posts_dict)

            xml_content = self.renderer.render_feed(sorted_posts, self.config)
            feed_path = self.output_dir / "feed.xml"
            write_file(feed_path, xml_content)
        except (OSError, ValueError) as e:
            logger.error("Error generating RSS feed: %s", e)

    def generate_sitemap(
        self,
        posts: list[ParsedContent],
        pages: list[ParsedContent],
    ) -> None:
        """
        Generate sitemap.xml listing all site URLs.

        Args:
            posts: Published posts
            pages: Static pages
        """
        if self.renderer is None or self.config is None:
            raise RuntimeError(
                "Renderer and config must be initialized before generating sitemap"
            )

        try:
            posts_dict = sort_posts_by_date([post.to_dict() for post in posts])
            pages_dict = [page.to_dict() for page in pages]
            all_tags = list(collect_posts_by_tag(posts_dict).keys())

            xml_content = self.renderer.render_sitemap(
                posts_dict, pages_dict, all_tags, self.config
            )
            sitemap_path = self.output_dir / "sitemap.xml"
            write_file(sitemap_path, xml_content)
        except (OSError, ValueError) as e:
            logger.error("Error generating sitemap: %s", e)

    def generate_pages(self, pages: list[ParsedContent]) -> None:
        """
        Generate static pages.

        Args:
            pages: List of ParsedContent objects
        """
        if self.renderer is None or self.config is None:
            raise RuntimeError(
                "Renderer and config must be initialized before generating pages"
            )

        for page in pages:
            try:
                html_content = self.renderer.render_page(page.to_dict(), self.config)

                url_path = generate_page_url(page.metadata.slug)
                output_path = get_output_path(self.output_dir, url_path)

                write_file(output_path, html_content)
            except (OSError, ValueError) as e:
                logger.error(
                    "Error generating page '%s' (%s): %s",
                    page.metadata.title,
                    page.metadata.slug,
                    e,
                )
                continue

    def copy_assets(self) -> None:
        """
        Copy static assets to output directory.
        """
        if self.static_dir.exists():
            dest_static_dir = self.output_dir / "static"
            copy_static_files(self.static_dir, dest_static_dir)

    def build(self, include_drafts: bool = False) -> None:
        """
        Execute complete site build process.

        Args:
            include_drafts: When True, include draft posts in the output.

        Raises:
            FileNotFoundError: If required directories or files are missing
            ValueError: If configuration is invalid
        """
        logger.info("Starting site build...")

        logger.info("Loading configuration...")
        self.load_config()
        if self.config is None:
            raise RuntimeError("Configuration failed to load")

        self.output_dir = self.project_root / self.config.output_dir

        logger.info("Initializing template renderer...")
        self.renderer = TemplateRenderer(self.template_dir)

        logger.info("Cleaning output directory...")
        clean_output_dir(self.output_dir)
        logger.info("Discovering content files...")
        content_files = self.discover_content()
        logger.info(
            "Found %d posts and %d pages",
            len(content_files["posts"]),
            len(content_files["pages"]),
        )

        # Process content
        logger.info("Processing content...")
        processed_content = self.process_content(content_files)

        # Filter published posts (unless --drafts is set)
        if include_drafts:
            posts = processed_content["posts"]
            logger.info("Including draft posts in build")
        else:
            posts = [
                post for post in processed_content["posts"] if not post.metadata.draft
            ]
        pages = processed_content["pages"]

        logger.info(
            "Processing %d published posts and %d pages", len(posts), len(pages)
        )

        # Generate content
        if posts:
            logger.info("Generating post pages...")
            self.generate_posts(posts)

            logger.info("Generating index page...")
            self.generate_index(posts)

            logger.info("Generating tag pages...")
            self.generate_tag_pages(posts)

            logger.info("Generating tag index...")
            self.generate_tag_index(posts)

            logger.info("Generating RSS feed...")
            self.generate_feed(posts)

        if pages:
            logger.info("Generating static pages...")
            self.generate_pages(pages)

        # Sitemap covers posts, pages, and tags
        logger.info("Generating sitemap...")
        self.generate_sitemap(posts, pages)

        # Copy static assets
        logger.info("Copying static assets...")
        self.copy_assets()

        logger.info("Site build complete! Generated site in: %s", self.output_dir)
