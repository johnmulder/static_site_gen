"""
Tests for the content parser module.

These tests validate the parsing of Markdown files with YAML front matter,
covering various scenarios including edge cases and error conditions.
"""

from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pytest
from static_site_gen.generator.parser import (
    ContentMetadata,
    ParsedContent,
    ParseError,
    extract_front_matter,
    generate_slug,
    parse_content_file,
    parse_date,
    validate_front_matter,
)


class TestExtractFrontMatter:
    """Test YAML front matter extraction."""

    def test_valid_front_matter(self, tmp_path):
        """Test extraction of valid front matter."""
        content = dedent(
            """
            ---
            title: "Test Post"
            date: 2025-10-17
            tags: [python, testing]
            ---
            
            # Test Content
            
            This is test content.
        """
        ).strip()

        filepath = tmp_path / "test.md"
        front_matter, body = extract_front_matter(content, filepath)

        assert front_matter["title"] == "Test Post"
        # YAML automatically converts date strings to date objects
        import datetime as dt

        assert front_matter["date"] == dt.date(2025, 10, 17)
        assert front_matter["tags"] == ["python", "testing"]
        assert "# Test Content" in body
        assert "This is test content." in body

    def test_empty_front_matter(self, tmp_path):
        """Test handling of empty front matter."""
        content = dedent(
            """
            ---
            ---
            
            # Content Only
        """
        ).strip()

        filepath = tmp_path / "test.md"
        front_matter, body = extract_front_matter(content, filepath)

        assert front_matter == {}
        assert "# Content Only" in body

    def test_missing_front_matter(self, tmp_path):
        """Test error when front matter is missing."""
        content = "# Just Content"
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Missing YAML front matter"):
            extract_front_matter(content, filepath)

    def test_malformed_front_matter_missing_end(self, tmp_path):
        """Test error when front matter end delimiter is missing."""
        content = dedent(
            """
            ---
            title: "Test"
            # No ending dashes
            Content here
        """
        ).strip()

        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Malformed YAML front matter"):
            extract_front_matter(content, filepath)

    def test_invalid_yaml_syntax(self, tmp_path):
        """Test error when YAML syntax is invalid."""
        content = dedent(
            """
            ---
            title: "Test"
            invalid_yaml: [unclosed list
            ---
            
            Content
        """
        ).strip()

        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Invalid YAML syntax"):
            extract_front_matter(content, filepath)


class TestValidateFrontMatter:
    """Test front matter validation."""

    def test_valid_front_matter(self, tmp_path):
        """Test validation of complete front matter."""
        front_matter = {"title": "Test Post", "date": "2025-10-17"}
        filepath = tmp_path / "test.md"

        # Should not raise exception
        validate_front_matter(front_matter, filepath)

    def test_missing_title(self, tmp_path):
        """Test error when title is missing."""
        front_matter = {"date": "2025-10-17"}
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Missing required field 'title'"):
            validate_front_matter(front_matter, filepath)

    def test_missing_date(self, tmp_path):
        """Test error when date is missing."""
        front_matter = {"title": "Test Post"}
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Missing required field 'date'"):
            validate_front_matter(front_matter, filepath)

    def test_empty_title(self, tmp_path):
        """Test error when title is empty."""
        front_matter = {"title": "", "date": "2025-10-17"}
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="must be a non-empty string"):
            validate_front_matter(front_matter, filepath)

    def test_invalid_title_type(self, tmp_path):
        """Test error when title is not a string."""
        front_matter = {"title": 123, "date": "2025-10-17"}
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="must be a non-empty string"):
            validate_front_matter(front_matter, filepath)

    def test_invalid_date_type(self, tmp_path):
        """Test error when date is invalid type."""
        front_matter = {"title": "Test", "date": 123}
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="must be a string.*or datetime"):
            validate_front_matter(front_matter, filepath)


class TestParseDate:
    """Test date parsing functionality."""

    def test_datetime_object(self, tmp_path):
        """Test parsing when date is already a datetime object."""
        from zoneinfo import ZoneInfo

        date_obj = datetime(2025, 10, 17)
        filepath = tmp_path / "test.md"

        result = parse_date(date_obj, filepath, timezone="UTC")
        # Should now be timezone-aware (UTC by default)
        expected = datetime(2025, 10, 17, tzinfo=ZoneInfo("UTC"))
        assert result == expected

    def test_date_string_basic(self, tmp_path):
        """Test parsing basic date string."""
        from zoneinfo import ZoneInfo

        filepath = tmp_path / "test.md"

        result = parse_date("2025-10-17", filepath, timezone="UTC")
        # Should now be timezone-aware (UTC by default)
        expected = datetime(2025, 10, 17, tzinfo=ZoneInfo("UTC"))
        assert result == expected

    def test_date_string_with_time(self, tmp_path):
        """Test parsing date string with time."""
        from zoneinfo import ZoneInfo

        filepath = tmp_path / "test.md"

        result = parse_date("2025-10-17 14:30:00", filepath, timezone="UTC")
        # Should now be timezone-aware (UTC by default)
        expected = datetime(2025, 10, 17, 14, 30, 0, tzinfo=ZoneInfo("UTC"))
        assert result == expected

    def test_date_string_with_time_no_seconds(self, tmp_path):
        """Test parsing date string with time (no seconds)."""
        from zoneinfo import ZoneInfo

        filepath = tmp_path / "test.md"

        result = parse_date("2025-10-17 14:30", filepath, timezone="UTC")
        # Should now be timezone-aware (UTC by default)
        expected = datetime(2025, 10, 17, 14, 30, tzinfo=ZoneInfo("UTC"))
        assert result == expected

    def test_invalid_date_format(self, tmp_path):
        """Test error with invalid date format."""
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Invalid date format"):
            parse_date("17-10-2025", filepath, timezone="UTC")

    def test_invalid_date_type(self, tmp_path):
        """Test error with invalid date type."""
        filepath = tmp_path / "test.md"

        with pytest.raises(ParseError, match="Date must be string.*datetime.*or date"):
            parse_date(123, filepath, timezone="UTC")


class TestGenerateSlug:
    """Test slug generation functionality."""

    def test_simple_title(self):
        """Test slug generation from simple title."""
        result = generate_slug("My First Post")
        assert result == "my-first-post"

    def test_title_with_special_chars(self):
        """Test slug generation with special characters."""
        result = generate_slug("Hello, World! How Are You?")
        assert result == "hello-world-how-are-you"

    def test_title_with_unicode(self):
        """Test slug generation with Unicode characters."""
        result = generate_slug("Café & Naïve")
        assert result == "cafe-naive"

    def test_title_with_numbers(self):
        """Test slug generation with numbers."""
        result = generate_slug("Python 3.11 Features")
        assert result == "python-311-features"

    def test_title_with_multiple_spaces(self):
        """Test slug generation with multiple spaces."""
        result = generate_slug("Multiple    Spaces   Here")
        assert result == "multiple-spaces-here"

    def test_title_with_leading_trailing_spaces(self):
        """Test slug generation with leading/trailing spaces."""
        result = generate_slug("  Trimmed Title  ")
        assert result == "trimmed-title"

    def test_empty_title(self):
        """Test slug generation from empty title."""
        result = generate_slug("")
        assert result == "untitled"

    def test_title_only_special_chars(self):
        """Test slug generation from title with only special characters."""
        result = generate_slug("!@#$%^&*()")
        # Should generate a unique hash-based slug to prevent collisions
        assert result.startswith("post-")
        assert result != "untitled"

        # Should be deterministic - same title produces same slug
        result2 = generate_slug("!@#$%^&*()")
        assert result == result2


class TestContentMetadata:
    """Test ContentMetadata dataclass."""

    def test_basic_metadata(self):
        """Test basic metadata creation."""
        metadata = ContentMetadata(
            title="Test Post", date=datetime(2025, 10, 17), slug="test-post"
        )

        assert metadata.title == "Test Post"
        assert metadata.date == datetime(2025, 10, 17)
        assert metadata.slug == "test-post"
        assert metadata.tags == []
        assert metadata.draft is False
        assert metadata.description is None

    def test_metadata_with_tags(self):
        """Test metadata with tags normalization."""
        metadata = ContentMetadata(
            title="Test Post",
            date=datetime(2025, 10, 17),
            slug="test-post",
            tags=["Python", " TESTING ", "blog"],
        )

        # Tags should be normalized to lowercase and stripped
        assert metadata.tags == ["python", "testing", "blog"]

    def test_metadata_with_empty_tags(self):
        """Test metadata with empty/whitespace tags."""
        metadata = ContentMetadata(
            title="Test Post",
            date=datetime(2025, 10, 17),
            slug="test-post",
            tags=["python", "", "   ", "testing"],
        )

        # Empty and whitespace-only tags should be filtered out
        assert metadata.tags == ["python", "testing"]


class TestParseContentFile:
    """Test complete file parsing functionality."""

    def test_complete_valid_file(self, tmp_path):
        """Test parsing a complete valid file."""
        content = dedent(
            """
            ---
            title: "My Test Post"
            date: 2025-10-17
            tags: [python, testing, blog]
            draft: false
            description: "A test post for validation"
            slug: custom-slug
            ---
            
            # My Test Post
            
            This is the content of my test post.
            
            ## Subsection
            
            More content here.
        """
        ).strip()

        filepath = tmp_path / "test-post.md"
        filepath.write_text(content, encoding="utf-8")

        result = parse_content_file(filepath, timezone="UTC")

        assert isinstance(result, ParsedContent)
        assert result.metadata.title == "My Test Post"
        from zoneinfo import ZoneInfo

        expected_date = datetime(2025, 10, 17, tzinfo=ZoneInfo("UTC"))
        assert result.metadata.date == expected_date
        assert result.metadata.slug == "custom-slug"
        assert result.metadata.tags == ["python", "testing", "blog"]
        assert result.metadata.draft is False
        assert result.metadata.description == "A test post for validation"
        # Check that Markdown has been converted to HTML
        assert '<h1 id="my-test-post">My Test Post</h1>' in result.content
        assert "<p>This is the content of my test post.</p>" in result.content
        assert '<h2 id="subsection">Subsection</h2>' in result.content
        assert result.filepath == filepath
        assert result.raw_content == content

    def test_minimal_valid_file(self, tmp_path):
        """Test parsing file with only required fields."""
        content = dedent(
            """
            ---
            title: "Minimal Post"
            date: 2025-10-17
            ---
            
            Just the basics.
        """
        ).strip()

        filepath = tmp_path / "minimal.md"
        filepath.write_text(content, encoding="utf-8")

        result = parse_content_file(filepath, timezone="UTC")

        assert result.metadata.title == "Minimal Post"
        from zoneinfo import ZoneInfo

        expected_date = datetime(2025, 10, 17, tzinfo=ZoneInfo("UTC"))
        assert result.metadata.date == expected_date
        assert result.metadata.slug == "minimal-post"  # Auto-generated
        assert result.metadata.tags == []
        assert result.metadata.draft is False
        assert result.metadata.description is None

    def test_invalid_tags_type(self, tmp_path):
        """Test error when tags is not a list."""
        content = dedent(
            """
            ---
            title: "Test"
            date: 2025-10-17
            tags: "not a list"
            ---
            
            Content
        """
        ).strip()

        filepath = tmp_path / "invalid.md"
        filepath.write_text(content, encoding="utf-8")

        with pytest.raises(ParseError, match="must be a list"):
            parse_content_file(filepath, timezone="UTC")

    def test_invalid_draft_type(self, tmp_path):
        """Test error when draft is not a boolean."""
        content = dedent(
            """
            ---
            title: "Test"
            date: 2025-10-17
            draft: "yes"
            ---
            
            Content
        """
        ).strip()

        filepath = tmp_path / "invalid.md"
        filepath.write_text(content, encoding="utf-8")

        with pytest.raises(ParseError, match="must be a boolean"):
            parse_content_file(filepath, timezone="UTC")

    def test_invalid_description_type(self, tmp_path):
        """Test error when description is not a string."""
        content = dedent(
            """
            ---
            title: "Test"
            date: 2025-10-17
            description: 123
            ---
            
            Content
        """
        ).strip()

        filepath = tmp_path / "invalid.md"
        filepath.write_text(content, encoding="utf-8")

        with pytest.raises(ParseError, match="must be a string"):
            parse_content_file(filepath, timezone="UTC")

    def test_file_not_found(self, tmp_path):
        """Test error when file does not exist."""
        filepath = tmp_path / "nonexistent.md"

        with pytest.raises(FileNotFoundError):
            parse_content_file(filepath, timezone="UTC")

    def test_encoding_error(self, tmp_path):
        """Test handling of encoding errors."""
        # Create file with invalid UTF-8 bytes
        filepath = tmp_path / "invalid_encoding.md"
        with open(filepath, "wb") as f:
            f.write(
                b'---\ntitle: "Test"\ndate: 2025-10-17\n---\n\n\xff\xfe invalid bytes'
            )

        with pytest.raises(ParseError, match="File encoding error"):
            parse_content_file(filepath, timezone="UTC")


class TestParseError:
    """Test ParseError exception formatting."""

    def test_basic_error(self):
        """Test basic error message."""
        error = ParseError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_error_with_filepath(self, tmp_path):
        """Test error message with file path."""
        filepath = tmp_path / "test.md"
        error = ParseError("Something went wrong", filepath)
        assert str(error) == f"Error in {filepath}: Something went wrong"

    def test_error_with_line_number(self, tmp_path):
        """Test error message with line number."""
        filepath = tmp_path / "test.md"
        error = ParseError("Something went wrong", filepath, 42)
        assert str(error) == f"Error in {filepath}: Something went wrong (line 42)"

    def test_error_with_line_number_no_path(self):
        """Test error message with line number but no path."""
        error = ParseError("Something went wrong", line_number=42)
        assert str(error) == "Something went wrong (line 42)"
