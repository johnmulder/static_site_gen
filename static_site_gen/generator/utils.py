"""
Utility functions for static site generation.

This module provides helper functions for file operations, URL generation,
and other common tasks used throughout the site generation process.
"""

import shutil
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def ensure_dir(path: Path) -> None:
    """
    Create directory and any necessary parent directories.

    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)


def copy_static_files(source_dir: Path, dest_dir: Path) -> None:
    """
    Copy all files from source directory to destination directory.

    Args:
        source_dir: Source directory containing static files
        dest_dir: Destination directory for copied files

    Raises:
        FileNotFoundError: If source directory doesn't exist
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"Static source directory not found: {source_dir}")

    # Remove existing destination directory if it exists
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    # Copy entire directory tree
    shutil.copytree(source_dir, dest_dir)


def generate_post_url(slug: str) -> str:
    """
    Generate clean URL path for a blog post.

    Args:
        slug: Post slug identifier

    Returns:
        URL path in format: /posts/<slug>/
    """
    return f"/posts/{slug}/"


def generate_tag_url(tag: str) -> str:
    """
    Generate clean URL path for a tag archive page.

    Args:
        tag: Tag name

    Returns:
        URL path in format: /tag/<tag>/
    """
    # URL-encode tag name to handle special characters and spaces
    encoded_tag = urllib.parse.quote(tag, safe="")
    return f"/tag/{encoded_tag}/"


def generate_page_url(slug: str) -> str:
    """
    Generate clean URL path for a static page.

    Args:
        slug: Page slug identifier

    Returns:
        URL path in format: /<slug>/
    """
    return f"/{slug}/"


def get_output_path(base_dir: Path, url_path: str) -> Path:
    """
    Convert URL path to filesystem path for output.

    Args:
        base_dir: Base output directory
        url_path: URL path (e.g., "/posts/my-post/")

    Returns:
        Filesystem path with index.html (e.g., "site/posts/my-post/index.html")

    Raises:
        ValueError: If url_path contains path traversal attempts or invalid characters
    """
    # Security: Sanitize URL path to prevent directory traversal attacks
    # First decode any URL-encoded characters to catch encoded traversal attempts
    import urllib.parse

    decoded_path = urllib.parse.unquote(url_path)

    if ".." in url_path or ".." in decoded_path:
        raise ValueError(f"Path traversal attempt detected in URL path: {url_path}")

    # Remove leading slash and normalize path separators
    relative_path = url_path.strip("/")

    # Additional security: reject paths with backslashes (Windows-style traversal)
    if "\\" in relative_path:
        raise ValueError(f"Invalid path separator in URL path: {url_path}")

    if not relative_path:
        # Root path
        return base_dir / "index.html"
    else:
        # Construct path and verify it stays within base_dir
        output_path = base_dir / relative_path / "index.html"

        # Security: Resolve paths and ensure result is within base_dir
        try:
            resolved_base = base_dir.resolve()
            resolved_output = output_path.resolve()

            # Check if the resolved output path starts with the base directory
            if not str(resolved_output).startswith(str(resolved_base)):
                raise ValueError(
                    f"Path traversal attempt: {url_path} would write outside base directory"
                )

        except (OSError, ValueError):
            # If path resolution fails or traversal detected, reject
            raise ValueError(f"Invalid or dangerous path: {url_path}")

        return output_path


def write_file(path: Path, content: str) -> None:
    """
    Write content to file, creating directories as needed.

    Args:
        path: File path to write to
        content: Content to write
    """
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def collect_posts_by_tag(
    posts: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group posts by their tags.

    Args:
        posts: List of post dictionaries with 'tags' field

    Returns:
        Dictionary mapping tag names to lists of posts
    """
    posts_by_tag = defaultdict(list)

    for post in posts:
        tags = post.get("tags", [])
        for tag in tags:
            posts_by_tag[tag].append(post)

    return dict(posts_by_tag)


def sort_posts_by_date(
    posts: List[Dict[str, Any]], reverse: bool = True
) -> List[Dict[str, Any]]:
    """
    Sort posts by their publication date.

    Args:
        posts: List of post dictionaries with 'date' field
        reverse: If True, sort newest first (default)

    Returns:
        Sorted list of posts
    """
    return sorted(posts, key=lambda p: p["date"], reverse=reverse)


def filter_published_posts(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out draft posts.

    Args:
        posts: List of post dictionaries

    Returns:
        List of published posts (draft=False or missing draft field)
    """
    return [post for post in posts if not post.get("draft", False)]


def clean_output_dir(output_dir: Path) -> None:
    """
    Remove and recreate output directory.

    Args:
        output_dir: Directory to clean and recreate

    Raises:
        ValueError: If output directory path appears unsafe
    """
    # Safety checks to prevent accidental deletion of important directories
    resolved_output = output_dir.resolve()

    # Don't allow cleaning root directory or parent directories
    if str(resolved_output) in ["/", "/Users", "/home", "/System", "/Applications"]:
        raise ValueError(
            f"Refusing to clean potentially dangerous directory: {resolved_output}"
        )

    # Don't allow cleaning directories that contain critical system files
    critical_files = [".bash_profile", ".bashrc", ".zshrc", "Desktop", "Documents"]
    if any(
        (resolved_output / critical_file).exists() for critical_file in critical_files
    ):
        raise ValueError(
            f"Directory appears to contain user files, refusing to clean: {resolved_output}"
        )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)


def paginate_posts(
    posts: List[Dict[str, Any]], posts_per_page: int
) -> List[Dict[str, Any]]:
    """
    Split posts into pages for pagination.

    Args:
        posts: List of post dictionaries sorted by date
        posts_per_page: Number of posts per page

    Returns:
        List of page dictionaries with pagination info
    """
    if posts_per_page <= 0:
        raise ValueError("posts_per_page must be positive")

    if not posts:
        return [
            {
                "posts": [],
                "page_number": 1,
                "total_pages": 1,
                "has_previous": False,
                "has_next": False,
                "previous_url": None,
                "next_url": None,
            }
        ]

    total_posts = len(posts)
    total_pages = (total_posts + posts_per_page - 1) // posts_per_page
    pages = []

    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * posts_per_page
        end_idx = start_idx + posts_per_page
        page_posts = posts[start_idx:end_idx]

        # Generate pagination URLs
        previous_url = None
        next_url = None

        if page_num > 1:
            previous_url = "/" if page_num == 2 else f"/page/{page_num - 1}/"

        if page_num < total_pages:
            next_url = f"/page/{page_num + 1}/"

        pages.append(
            {
                "posts": page_posts,
                "page_number": page_num,
                "total_pages": total_pages,
                "has_previous": page_num > 1,
                "has_next": page_num < total_pages,
                "previous_url": previous_url,
                "next_url": next_url,
            }
        )

    return pages


def generate_pagination_url(page_number: int) -> str:
    """
    Generate URL for a pagination page.

    Args:
        page_number: Page number (1-based)

    Returns:
        URL path for the page
    """
    if page_number <= 1:
        return "/"
    return f"/page/{page_number}/"
