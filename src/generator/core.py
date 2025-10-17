"""
Core build engine for the static site generator.

This module contains the main build orchestration logic that coordinates
the entire content -> template -> output pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from .parser import parse_content_file
from .renderer import TemplateRenderer
from .utils import (
    clean_output_dir,
    collect_posts_by_tag,
    copy_static_files,
    filter_published_posts,
    generate_page_url,
    generate_post_url,
    generate_tag_url,
    get_output_path,
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

        self.config = None
        self.renderer = None

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

        # Validate required fields
        required_fields = ["site_name", "base_url", "author"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required config fields: {missing_fields}")

        # Set defaults for optional fields
        config.setdefault("timezone", "UTC")
        config.setdefault("output_dir", "site")

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

    def process_content(
        self, content_files: Dict[str, List[Path]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Parse all content files into structured data.

        Args:
            content_files: Dictionary of content file paths by type

        Returns:
            Dictionary with parsed 'posts' and 'pages' data
        """
        processed_content = {"posts": [], "pages": []}

        # Process posts
        for post_file in content_files["posts"]:
            try:
                post_data = parse_content_file(post_file)
                processed_content["posts"].append(post_data)
            except Exception as e:
                print(f"Error processing post {post_file}: {e}")
                continue

        # Process pages
        for page_file in content_files["pages"]:
            try:
                page_data = parse_content_file(page_file)
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
        for post in posts:
            # Convert ParsedContent to dict for template
            post_dict = {
                "title": post.metadata.title,
                "date": post.metadata.date,
                "slug": post.metadata.slug,
                "tags": post.metadata.tags,
                "draft": post.metadata.draft,
                "description": post.metadata.description,
                "content": post.content,
            }

            # Render post HTML
            html_content = self.renderer.render_post(post_dict, self.config)

            # Generate output path
            url_path = generate_post_url(post.metadata.slug)
            output_path = get_output_path(self.output_dir, url_path)

            # Write file
            write_file(output_path, html_content)

    def generate_index(self, posts: List[Any]) -> None:
        """
        Generate homepage with post listing.

        Args:
            posts: List of ParsedContent objects (will be sorted by date)
        """
        # Convert to dict format and sort posts by date (newest first)
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

        # Render index HTML
        html_content = self.renderer.render_index(sorted_posts, self.config)

        # Write to root index.html
        output_path = self.output_dir / "index.html"
        write_file(output_path, html_content)

    def generate_tag_pages(self, posts: List[Any]) -> None:
        """
        Generate tag archive pages.

        Args:
            posts: List of ParsedContent objects
        """
        # Convert to dict format
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
            # Sort posts by date
            sorted_posts = sort_posts_by_date(tag_posts)

            # Render tag page HTML
            html_content = self.renderer.render_tag_page(tag, sorted_posts, self.config)

            # Generate output path
            url_path = generate_tag_url(tag)
            output_path = get_output_path(self.output_dir, url_path)

            # Write file
            write_file(output_path, html_content)

    def generate_pages(self, pages: List[Any]) -> None:
        """
        Generate static pages.

        Args:
            pages: List of ParsedContent objects
        """
        for page in pages:
            # Convert ParsedContent to dict for template
            page_dict = {
                "title": page.metadata.title,
                "date": page.metadata.date,
                "slug": page.metadata.slug,
                "tags": page.metadata.tags,
                "draft": page.metadata.draft,
                "description": page.metadata.description,
                "content": page.content,
            }

            # Render page HTML
            html_content = self.renderer.render_page(page_dict, self.config)

            # Generate output path
            url_path = generate_page_url(page.metadata.slug)
            output_path = get_output_path(self.output_dir, url_path)

            # Write file
            write_file(output_path, html_content)

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

        # Load configuration
        print("Loading configuration...")
        self.load_config()

        # Initialize renderer
        print("Initializing template renderer...")
        self.renderer = TemplateRenderer(self.template_dir)

        # Clean output directory
        print("Cleaning output directory...")
        clean_output_dir(self.output_dir)

        # Discover content files
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
