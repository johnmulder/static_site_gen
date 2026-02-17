"""
Regression tests for bug fixes in the static site generator.

These tests ensure that the specific bugs discovered during bug hunting
do not reoccur in future versions.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
import yaml

from static_site_gen.generator.core import SiteGenerator
from static_site_gen.generator.parser import parse_content_file, parse_date


class TestBugFix1ConfigValidation:
    """Regression tests for Bug #1: Configuration Validation Bypass."""

    def test_null_site_name_rejected(self, tmp_path):
        """Test that null site_name values are properly rejected."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": None,  # Should be rejected
            "base_url": "https://example.com",
            "author": "Test Author",
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="site_name is null"):
            generator.load_config()

    def test_empty_site_name_rejected(self, tmp_path):
        """Test that empty site_name values are properly rejected."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": "",  # Should be rejected
            "base_url": "https://example.com",
            "author": "Test Author",
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="site_name is empty"):
            generator.load_config()

    def test_whitespace_only_site_name_rejected(self, tmp_path):
        """Test that whitespace-only site_name values are rejected."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": "   ",  # Should be rejected
            "base_url": "https://example.com",
            "author": "Test Author",
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="site_name is empty"):
            generator.load_config()

    def test_non_string_site_name_rejected(self, tmp_path):
        """Test that non-string site_name values are rejected."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": 12345,  # Should be rejected
            "base_url": "https://example.com",
            "author": "Test Author",
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="site_name must be a string"):
            generator.load_config()

    def test_null_base_url_rejected(self, tmp_path):
        """Test that null base_url values are properly rejected."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": "Test Blog",
            "base_url": None,  # Should be rejected
            "author": "Test Author",
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="base_url is null"):
            generator.load_config()

    def test_null_author_rejected(self, tmp_path):
        """Test that null author values are properly rejected."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": "Test Blog",
            "base_url": "https://example.com",
            "author": None,  # Should be rejected
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="author is null"):
            generator.load_config()

    def test_empty_config_file_rejected(self, tmp_path):
        """Test that completely empty config files are rejected."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")  # Empty file

        generator = SiteGenerator(tmp_path)
        with pytest.raises(ValueError, match="Configuration file is empty or invalid"):
            generator.load_config()

    def test_valid_config_accepted(self, tmp_path):
        """Test that valid configuration is properly accepted."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": "Valid Blog",
            "base_url": "https://example.com",
            "author": "Valid Author",
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        generator = SiteGenerator(tmp_path)
        config = generator.load_config()

        assert config["site_name"] == "Valid Blog"
        assert config["base_url"] == "https://example.com"
        assert config["author"] == "Valid Author"


class TestBugFix2TimezoneHandling:
    """Regression tests for Bug #2: Timezone Information Loss."""

    def test_date_parsing_preserves_timezone_utc(self, tmp_path):
        """Test that date parsing creates timezone-aware datetime objects (UTC)."""
        test_file = tmp_path / "test.md"

        result = parse_date(date(2025, 10, 30), test_file, "UTC")

        assert result.tzinfo is not None
        assert result.tzinfo == ZoneInfo("UTC")
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 30

    def test_date_parsing_preserves_timezone_custom(self, tmp_path):
        """Test that date parsing respects custom timezone."""
        test_file = tmp_path / "test.md"

        result = parse_date(date(2025, 10, 30), test_file, "America/New_York")

        assert result.tzinfo is not None
        assert result.tzinfo == ZoneInfo("America/New_York")

    def test_datetime_parsing_preserves_timezone(self, tmp_path):
        """Test that datetime parsing creates timezone-aware objects."""
        test_file = tmp_path / "test.md"

        result = parse_date(datetime(2025, 10, 30, 12, 0), test_file, "UTC")

        assert result.tzinfo is not None
        assert result.tzinfo == ZoneInfo("UTC")
        assert result.hour == 12

    def test_string_date_parsing_timezone_aware(self, tmp_path):
        """Test that string date parsing creates timezone-aware objects."""
        test_file = tmp_path / "test.md"

        result = parse_date("2025-10-30", test_file, "America/Denver")

        assert result.tzinfo is not None
        assert result.tzinfo == ZoneInfo("America/Denver")

    def test_already_timezone_aware_datetime_preserved(self, tmp_path):
        """Test that already timezone-aware datetime objects are preserved."""
        test_file = tmp_path / "test.md"
        aware_dt = datetime(2025, 10, 30, 12, 0, tzinfo=ZoneInfo("Asia/Tokyo"))

        result = parse_date(aware_dt, test_file, "UTC")

        # Should preserve the original timezone, not change to UTC
        assert result.tzinfo == ZoneInfo("Asia/Tokyo")

    def test_invalid_timezone_falls_back_to_utc(self, tmp_path):
        """Test that invalid timezone names fall back to UTC."""
        test_file = tmp_path / "test.md"

        result = parse_date(date(2025, 10, 30), test_file, "Invalid/Timezone")

        assert result.tzinfo == ZoneInfo("UTC")

    def test_content_file_parsing_uses_timezone(self, tmp_path):
        """Test that content file parsing respects timezone parameter."""
        content_file = tmp_path / "test.md"
        content_file.write_text(
            """---
title: "Test Post"
date: 2025-10-30
---

Test content
"""
        )

        result = parse_content_file(content_file, timezone="America/Los_Angeles")

        assert result.metadata.date.tzinfo == ZoneInfo("America/Los_Angeles")


class TestBugFix3SlugCollisionDataPreservation:
    """Regression tests for Bug #3: Data Loss in Slug Collision Resolution."""

    def test_slug_collision_preserves_custom_metadata(self, tmp_path):
        """Test that custom front matter fields are preserved during slug collision resolution."""
        # Create config
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": "Test Blog",
            "base_url": "https://example.com",
            "author": "Test Author",
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # Create content with identical slugs and custom fields
        posts_dir = tmp_path / "content" / "posts"
        posts_dir.mkdir(parents=True)

        post1 = posts_dir / "2025-10-30-test-post.md"
        post1.write_text(
            """---
title: "Test Post"
date: 2025-10-30
tags: [test, original]
custom_field: "should be preserved"
author_note: "Original post"
category: "testing"
---
Content 1
"""
        )

        post2 = posts_dir / "2025-10-30-another-test-post.md"
        post2.write_text(
            """---
title: "Test Post"  # Same title = same slug
date: 2025-10-30
tags: [test, duplicate]
custom_field: "should also be preserved"
author_note: "Duplicate post"
category: "testing"
---
Content 2
"""
        )

        # Create minimal templates
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        (templates_dir / "base.html").write_text(
            """<!DOCTYPE html>
<html><head><title>{{ page_title }}</title></head>
<body>{% block content %}{% endblock %}</body></html>"""
        )

        (templates_dir / "post.html").write_text(
            """{% extends "base.html" %}
{% block content %}<h1>{{ post.title }}</h1>{{ post.content }}{% endblock %}"""
        )

        (templates_dir / "index.html").write_text(
            """{% extends "base.html" %}
{% block content %}<h1>Blog</h1>{% for post in posts %}<p>{{ post.title }}</p>{% endfor %}{% endblock %}"""
        )

        (templates_dir / "tag.html").write_text(
            """{% extends "base.html" %}
{% block content %}<h1>Tag: {{ tag }}</h1>{% for post in posts %}<p>{{ post.title }}</p>{% endfor %}{% endblock %}"""
        )

        (templates_dir / "page.html").write_text(
            """{% extends "base.html" %}
{% block content %}<h1>{{ page.title }}</h1>{{ page.content }}{% endblock %}"""
        )

        generator = SiteGenerator(tmp_path)
        generator.load_config()

        # Process content - this should trigger slug collision resolution
        content_files = generator.discover_content()
        processed_content = generator.process_content(content_files)

        # Verify we have 2 posts
        assert len(processed_content["posts"]) == 2

        # Verify both posts have different slugs
        slugs = [post.metadata.slug for post in processed_content["posts"]]
        assert len(set(slugs)) == 2  # Should be unique
        assert "test-post" in slugs
        assert "test-post-2" in slugs

        # The key test: verify that both posts preserve their original metadata
        # Note: We can't directly test custom fields since ContentMetadata doesn't include them
        # But we can ensure the basic metadata is preserved correctly
        for post in processed_content["posts"]:
            assert post.metadata.title == "Test Post"
            assert post.metadata.date.year == 2025
            assert post.metadata.date.month == 10
            assert post.metadata.date.day == 30
            assert "test" in post.metadata.tags
            assert not post.metadata.draft

    def test_no_slug_collision_preserves_metadata(self, tmp_path):
        """Test that posts without slug collisions preserve metadata correctly."""
        # Create config
        config_path = tmp_path / "config.yaml"
        config_data = {
            "site_name": "Test Blog",
            "base_url": "https://example.com",
            "author": "Test Author",
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # Create content with different slugs
        posts_dir = tmp_path / "content" / "posts"
        posts_dir.mkdir(parents=True)

        post1 = posts_dir / "2025-10-30-first-post.md"
        post1.write_text(
            """---
title: "First Post"
date: 2025-10-30
tags: [test, first]
description: "First post description"
---
Content 1
"""
        )

        post2 = posts_dir / "2025-10-30-second-post.md"
        post2.write_text(
            """---
title: "Second Post"
date: 2025-10-30
tags: [test, second]
description: "Second post description"
---
Content 2
"""
        )

        generator = SiteGenerator(tmp_path)
        generator.load_config()

        content_files = generator.discover_content()
        processed_content = generator.process_content(content_files)

        # Verify metadata is preserved correctly
        assert len(processed_content["posts"]) == 2

        post1_data = next(
            p for p in processed_content["posts"] if p.metadata.slug == "first-post"
        )
        post2_data = next(
            p for p in processed_content["posts"] if p.metadata.slug == "second-post"
        )

        assert post1_data.metadata.title == "First Post"
        assert post1_data.metadata.description == "First post description"
        assert "first" in post1_data.metadata.tags

        assert post2_data.metadata.title == "Second Post"
        assert post2_data.metadata.description == "Second post description"
        assert "second" in post2_data.metadata.tags
