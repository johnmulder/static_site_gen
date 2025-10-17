"""
Utility functions for static site generation.

This module provides helper functions for file operations, URL generation,
and other common tasks used throughout the site generation process.
"""

import shutil
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
    return f"/tag/{tag}/"


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
    """
    # Remove leading slash and add index.html
    relative_path = url_path.strip("/")
    if not relative_path:
        # Root path
        return base_dir / "index.html"
    else:
        return base_dir / relative_path / "index.html"


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
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
