"""
Core build engine for the static site generator.

This module contains the main build orchestration logic that coordinates
the entire content -> template -> output pipeline.
"""

import logging
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import markdown
import yaml

from .output import (
    collect_posts_by_tag,
    copy_static_files,
    generate_page_url,
    generate_post_url,
    generate_tag_url,
    get_output_path,
    paginate_posts,
    publish_output,
    sort_posts_by_date,
    validate_output_dir,
    validate_output_routes,
    write_file,
)
from .parser import ParsedContent, ParseError, parse_content_file
from .renderer import TemplateRenderer

logger = logging.getLogger(__name__)


def _normalize_url_prefix(path: str) -> str:
    """Canonicalize an optional URL prefix without changing segment boundaries."""
    if path in {"", "/"}:
        return ""
    segments = path.removesuffix("/").split("/")[1:]
    encoded = []
    for segment in segments:
        if re.search(r"%(?![0-9a-fA-F]{2})", segment):
            raise ValueError(
                "base_url has an invalid percent escape in its path prefix"
            )
        try:
            decoded = unquote(segment, errors="strict")
            canonical = quote(decoded, safe="")
        except (UnicodeError, ValueError) as exc:
            raise ValueError("base_url path prefix must be valid UTF-8") from exc
        if (
            not decoded
            or decoded in {".", ".."}
            or decoded != decoded.strip()
            or any(character in decoded for character in "/\\;")
            or any(
                ord(character) < 32 or ord(character) == 127 for character in decoded
            )
        ):
            raise ValueError("base_url has an ambiguous or unsafe path prefix")
        encoded.append(canonical)
    return "/" + "/".join(encoded)


@dataclass
class SiteConfig:
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

    @property
    def url_prefix(self) -> str:
        """Return the encoded mount path, without a trailing slash."""
        return urlparse(self.base_url).path.removesuffix("/")

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
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a YAML mapping")

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
        if (
            not isinstance(posts_per_page, int)
            or isinstance(posts_per_page, bool)
            or posts_per_page <= 0
        ):
            raise ValueError(
                f"posts_per_page must be a positive integer, got: {posts_per_page}"
            )

        base_url = raw["base_url"]
        try:
            parsed_url = urlparse(base_url)
            hostname = parsed_url.hostname
            parsed_url.port
        except ValueError as exc:
            raise ValueError(
                "base_url must be a valid absolute HTTP/HTTPS URL"
            ) from exc
        if (
            parsed_url.scheme not in {"http", "https"}
            or not hostname
            or any(
                character.isspace() or ord(character) < 32 or ord(character) == 127
                for character in base_url
            )
            or "\\" in base_url
            or "%" in parsed_url.netloc
        ):
            raise ValueError(
                f"base_url must be a valid absolute HTTP/HTTPS URL, got: {raw['base_url']}"
            )
        if parsed_url.username is not None or parsed_url.password is not None:
            raise ValueError("base_url must not contain credentials")
        if parsed_url.params:
            raise ValueError("base_url has an ambiguous or unsafe path prefix")
        if "?" in base_url or "#" in base_url:
            raise ValueError("base_url must not contain a query string or fragment")
        url_prefix = _normalize_url_prefix(parsed_url.path)
        base_url = parsed_url._replace(
            netloc=parsed_url.netloc.lower(), path=url_prefix
        ).geturl()

        timezone = raw.get("timezone", "UTC")
        if not isinstance(timezone, str) or not timezone.strip():
            raise ValueError(f"Invalid timezone setting: {timezone}")
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Invalid timezone setting: {timezone}") from exc

        output_dir = raw.get("output_dir", "site")
        if not isinstance(output_dir, str) or not output_dir.strip():
            raise ValueError("output_dir must be a nonempty relative directory name")
        if Path(output_dir).is_absolute():
            raise ValueError("output_dir must be relative to the project root")

        markdown_extensions = raw.get(
            "markdown_extensions", ["codehilite", "tables", "toc"]
        )
        if not isinstance(markdown_extensions, list) or not all(
            isinstance(extension, str) and extension.strip()
            for extension in markdown_extensions
        ):
            raise ValueError(
                "markdown_extensions must be a list of strings with nonempty names"
            )

        return cls(
            site_name=raw["site_name"],
            base_url=base_url,
            author=raw["author"],
            timezone=timezone,
            output_dir=output_dir,
            posts_per_page=posts_per_page,
            description=raw.get("description", ""),
            keywords=raw.get("keywords", []),
            markdown_extensions=markdown_extensions,
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
            "posts": sorted(posts_dir.glob("*.md")) if posts_dir.exists() else [],
            "pages": sorted(pages_dir.glob("*.md")) if pages_dir.exists() else [],
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

        for filepath in sorted(files):
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
                post_data = post.to_dict()
                html_content = self.renderer.render_template(
                    "post.html",
                    {
                        "post": post_data,
                        "site": self.config,
                        "page_title": post_data.get("title", "Untitled Post"),
                    },
                )
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
                raise

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

                page_title = self.config.site_name
                if pagination["current_page"] > 1:
                    page_title += f" - Page {pagination['current_page']}"
                html_content = self.renderer.render_template(
                    "index.html",
                    {
                        "posts": page_posts,
                        "site": self.config,
                        "pagination": pagination,
                        "page_title": page_title,
                    },
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

                html_content = self.renderer.render_template(
                    "tag.html",
                    {
                        "tag": tag,
                        "posts": sorted_posts,
                        "site": self.config,
                        "page_title": f"Posts tagged '{tag}'",
                    },
                )

                url_path = generate_tag_url(tag)
                output_path = get_output_path(self.output_dir, url_path)

                write_file(output_path, html_content)
            except (OSError, ValueError) as e:
                logger.error("Error generating tag page for '%s': %s", tag, e)
                raise

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
            html_content = self.renderer.render_template(
                "tag_index.html",
                {
                    "tags": tags_with_counts,
                    "site": self.config,
                    "page_title": "Tags",
                },
            )
            output_path = self.output_dir / "tag" / "index.html"
            write_file(output_path, html_content)
        except (OSError, ValueError) as e:
            logger.error("Error generating tag index: %s", e)
            raise

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

            xml_content = self.renderer.render_template(
                "feed.xml", {"posts": sorted_posts, "site": self.config}
            )
            feed_path = self.output_dir / "feed.xml"
            write_file(feed_path, xml_content)
        except (OSError, ValueError) as e:
            logger.error("Error generating RSS feed: %s", e)
            raise

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

            xml_content = self.renderer.render_template(
                "sitemap.xml",
                {
                    "posts": posts_dict,
                    "pages": pages_dict,
                    "tags": sorted(all_tags),
                    "site": self.config,
                },
            )
            sitemap_path = self.output_dir / "sitemap.xml"
            write_file(sitemap_path, xml_content)
        except (OSError, ValueError) as e:
            logger.error("Error generating sitemap: %s", e)
            raise

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
                page_data = page.to_dict()
                html_content = self.renderer.render_template(
                    "page.html",
                    {
                        "page": page_data,
                        "site": self.config,
                        "page_title": page_data.get("title", "Untitled Page"),
                    },
                )

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
                raise

    def copy_assets(self) -> None:
        """
        Copy static assets to output directory.
        """
        if self.static_dir.exists():
            dest_static_dir = self.output_dir / "static"
            copy_static_files(self.static_dir, dest_static_dir)

    def _validate_routes(
        self, posts: list[ParsedContent], pages: list[ParsedContent]
    ) -> None:
        """Reserve all generated destinations before rendering or copying assets."""
        if self.config is None:
            raise RuntimeError("Configuration must be loaded before validating routes")
        routes = [
            (
                self.output_dir / "index.html",
                f"homepage ({self.template_dir / 'index.html'})",
            ),
            (
                self.output_dir / "feed.xml",
                f"RSS feed ({self.template_dir / 'feed.xml'})",
            ),
            (
                self.output_dir / "sitemap.xml",
                f"sitemap ({self.template_dir / 'sitemap.xml'})",
            ),
            (
                self.output_dir / "tag/index.html",
                f"tag index ({self.template_dir / 'tag_index.html'})",
            ),
        ]
        for post in posts:
            routes.append(
                (
                    get_output_path(
                        self.output_dir, generate_post_url(post.metadata.slug)
                    ),
                    f"post {post.filepath}",
                )
            )
        for page in pages:
            routes.append(
                (
                    get_output_path(
                        self.output_dir, generate_page_url(page.metadata.slug)
                    ),
                    f"page {page.filepath}",
                )
            )
        tag_sources: dict[str, list[str]] = {}
        for post in posts:
            for tag in post.metadata.tags or []:
                tag_sources.setdefault(tag, []).append(str(post.filepath))
        for tag, sources in sorted(tag_sources.items()):
            routes.append(
                (
                    get_output_path(self.output_dir, generate_tag_url(tag)),
                    f"tag {tag!r} from {', '.join(sources)}",
                )
            )
        for pagination in paginate_posts(
            [post.to_dict() for post in posts], self.config.posts_per_page
        )[1:]:
            number = pagination["page_number"]
            routes.append(
                (
                    self.output_dir / "page" / str(number) / "index.html",
                    f"pagination page {number} ({self.config_file})",
                )
            )
        reserved = []
        if self.static_dir.exists():
            reserved.append(
                (self.output_dir / "static", f"static assets {self.static_dir}")
            )
        validate_output_routes(routes, reserved)

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

        try:
            markdown.Markdown(extensions=self.config.markdown_extensions)
        except Exception as exc:
            raise ValueError(f"Invalid Markdown extension setup: {exc}") from exc

        output = validate_output_dir(
            self.project_root / self.config.output_dir, self.project_root
        )

        logger.info("Initializing template renderer...")
        self.renderer = TemplateRenderer(self.template_dir)

        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(
                prefix=f".{output.name}-build-", dir=output.parent
            ) as staging:
                self.output_dir = Path(staging) / "site"
                self.output_dir.mkdir()
                self._generate_site(include_drafts)
                validate_output_dir(output, self.project_root)
                publish_output(self.output_dir, output)
        finally:
            self.output_dir = output
        logger.info("Site build complete! Generated site in: %s", self.output_dir)

    def _generate_site(self, include_drafts: bool) -> None:
        """Generate the complete site in the staging directory."""
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

        self._validate_routes(posts, pages)

        # Generate content
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
