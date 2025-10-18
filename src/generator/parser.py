"""
Content parsing and validation module.

This module handles the parsing of Markdown files with YAML front matter,
extracting and validating metadata, and preparing content for rendering.
Core responsibilities:

- YAML front matter extraction and parsing
- Markdown body separation and processing
- Content metadata validation (required/optional fields)
- Slug generation from titles (kebab-case conversion)
- Date parsing and timezone handling
- Tag processing and normalization

Supported front matter schema:
- Required: title, date
- Optional: tags (list), draft (boolean), description, slug

The parser handles various edge cases:
- Missing slugs (auto-generated from title)
- Invalid dates (graceful error handling)
- Malformed YAML (clear error messages)
- Unicode characters in titles and content
- Empty or missing front matter sections

Design principles:
- Validate early, fail with clear messages
- Handle encoding issues gracefully
- Preserve original content when possible
- Generate helpful error context (file paths, line numbers)
"""

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import markdown
import yaml


class ParseError(Exception):
    """Raised when content parsing fails."""

    def __init__(
        self,
        message: str,
        filepath: Optional[Path] = None,
        line_number: Optional[int] = None,
    ):
        self.filepath = filepath
        self.line_number = line_number

        error_msg = message
        if filepath:
            error_msg = f"Error in {filepath}: {message}"
        if line_number:
            error_msg += f" (line {line_number})"

        super().__init__(error_msg)


@dataclass
class ContentMetadata:
    """Container for parsed content metadata."""

    title: str
    date: datetime
    slug: str
    tags: List[str] = None
    draft: bool = False
    description: Optional[str] = None

    def __post_init__(self):
        """Normalize data after initialization."""
        if self.tags is None:
            self.tags = []
        # Normalize tags to lowercase
        self.tags = [tag.strip().lower() for tag in self.tags if tag.strip()]


@dataclass
class ParsedContent:
    """Container for fully parsed content."""

    metadata: ContentMetadata
    content: str
    raw_content: str
    filepath: Path


def extract_front_matter(content: str, filepath: Path) -> tuple[Dict[str, Any], str]:
    """
    Extract YAML front matter from content string.

    Args:
        content: Raw file content
        filepath: Path to file (for error reporting)

    Returns:
        Tuple of (front_matter_dict, markdown_body)

    Raises:
        ParseError: If front matter is malformed or missing
    """
    # Check for front matter delimiters
    if not content.startswith("---"):
        raise ParseError(
            "Missing YAML front matter (content must start with '---')", filepath
        )

    # Find the end of front matter
    try:
        # Split on second occurrence of ---
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise ParseError(
                "Malformed YAML front matter (missing closing '---')", filepath
            )

        # Check if we have both opening and closing delimiters
        if parts[1].strip() == "" and len(parts) == 3:
            # Handle case where content is just "---\n---"
            pass
        elif not parts[2]:
            # No content after second ---
            pass

        _, front_matter_raw, markdown_body = parts

        # Parse YAML
        try:
            front_matter = yaml.safe_load(front_matter_raw.strip())
            if front_matter is None:
                front_matter = {}
        except yaml.YAMLError as e:
            raise ParseError(f"Invalid YAML syntax: {e}", filepath) from e

        return front_matter, markdown_body.strip()

    except Exception as e:
        if isinstance(e, ParseError):
            raise
        raise ParseError(f"Failed to parse front matter: {e}", filepath) from e


def validate_front_matter(front_matter: Dict[str, Any], filepath: Path) -> None:
    """
    Validate required fields in front matter.

    Args:
        front_matter: Parsed front matter dictionary
        filepath: Path to file (for error reporting)

    Raises:
        ParseError: If required fields are missing or invalid
    """
    # Check required fields
    if "title" not in front_matter:
        raise ParseError("Missing required field 'title'", filepath)
    if "date" not in front_matter:
        raise ParseError("Missing required field 'date'", filepath)

    # Validate title is non-empty string
    title = front_matter["title"]
    if not isinstance(title, str) or not title.strip():
        raise ParseError("Field 'title' must be a non-empty string", filepath)

    # Validate date format
    date_value = front_matter["date"]
    if not isinstance(date_value, (str, datetime, dt.date)):
        raise ParseError(
            "Field 'date' must be a string (YYYY-MM-DD) or datetime", filepath
        )


def parse_date(date_value: Union[str, datetime, dt.date], filepath: Path) -> datetime:
    """
    Parse date from various formats.

    Args:
        date_value: Date as string, datetime, or date object
        filepath: Path to file (for error reporting)

    Returns:
        Parsed datetime object

    Raises:
        ParseError: If date format is invalid
    """
    if isinstance(date_value, datetime):
        return date_value

    if isinstance(date_value, dt.date):
        # Convert date to datetime (midnight)
        return datetime.combine(date_value, datetime.min.time())

    if isinstance(date_value, str):
        # Try common date formats
        formats = [
            "%Y-%m-%d",  # 2025-10-17
            "%Y-%m-%d %H:%M:%S",  # 2025-10-17 10:30:00
            "%Y-%m-%d %H:%M",  # 2025-10-17 10:30
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_value.strip(), fmt)
            except ValueError:
                continue

        raise ParseError(
            f"Invalid date format '{date_value}'. Use YYYY-MM-DD format", filepath
        )

    raise ParseError(
        f"Date must be string, datetime, or date, got {type(date_value)}", filepath
    )


def generate_slug(title: str) -> str:
    """
    Generate URL-safe slug from title.

    Args:
        title: Post title

    Returns:
        URL-safe slug in kebab-case
    """
    # Normalize unicode characters
    normalized = unicodedata.normalize("NFKD", title)

    # Convert to ASCII, removing accents
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r"[^\w\s-]", "", ascii_title.lower())
    slug = re.sub(r"[-\s]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Ensure non-empty slug
    if not slug:
        slug = "untitled"

    return slug


def parse_content_file(
    filepath: Path, markdown_extensions: Optional[List[str]] = None
) -> ParsedContent:
    """
    Parse a Markdown file with YAML front matter.

    Args:
        filepath: Path to the content file
        markdown_extensions: List of markdown extensions to use (defaults to ["extra", "codehilite", "toc"])

    Returns:
        ParsedContent object with metadata and content

    Raises:
        ParseError: If file cannot be parsed
        FileNotFoundError: If file does not exist
    """
    try:
        # Read file content
        raw_content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Re-raise FileNotFoundError as-is for proper test handling
        raise
    except UnicodeDecodeError as e:
        raise ParseError(f"File encoding error: {e}", filepath) from e
    except Exception as e:
        raise ParseError(
            f"Failed to read file: {e}", filepath
        ) from e  # Extract front matter and markdown body
    front_matter, markdown_body = extract_front_matter(raw_content, filepath)

    # Validate required fields
    validate_front_matter(front_matter, filepath)

    # Parse and validate date
    parsed_date = parse_date(front_matter["date"], filepath)

    # Generate slug if not provided
    slug = front_matter.get("slug")
    if not slug:
        slug = generate_slug(front_matter["title"])

    # Extract optional fields with defaults
    tags = front_matter.get("tags", [])
    if not isinstance(tags, list):
        raise ParseError("Field 'tags' must be a list", filepath)

    draft = front_matter.get("draft", False)
    if not isinstance(draft, bool):
        raise ParseError("Field 'draft' must be a boolean", filepath)

    description = front_matter.get("description")
    if description is not None and not isinstance(description, str):
        raise ParseError("Field 'description' must be a string", filepath)

    # Convert Markdown to HTML using configured extensions
    extensions = markdown_extensions or ["extra", "codehilite", "toc"]
    md = markdown.Markdown(extensions=extensions)
    html_content = md.convert(markdown_body)

    # Create metadata object
    metadata = ContentMetadata(
        title=front_matter["title"].strip(),
        date=parsed_date,
        slug=slug,
        tags=tags,
        draft=draft,
        description=description.strip() if description else None,
    )

    return ParsedContent(
        metadata=metadata,
        content=html_content,
        raw_content=raw_content,
        filepath=filepath,
    )
