"""
End-to-end integration tests for the static site generator.

Tests the complete build pipeline from content files to generated output.
"""

import shutil
import tempfile
from pathlib import Path

from generator.core import SiteGenerator


def test_complete_build_pipeline():
    """Test complete site generation from content to output."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test project structure
        content_dir = temp_path / "content"
        posts_dir = content_dir / "posts"
        pages_dir = content_dir / "pages"
        template_dir = temp_path / "templates"
        static_dir = temp_path / "static"

        posts_dir.mkdir(parents=True)
        pages_dir.mkdir(parents=True)
        template_dir.mkdir()
        static_dir.mkdir()

        # Create test config
        config_content = """
site_name: "Test Blog"
base_url: "https://test.com"
author: "Test Author"
description: "A test blog"
"""
        (temp_path / "config.yaml").write_text(config_content)

        # Create test content
        post_content = """---
title: "Test Post"
date: 2025-10-17
tags: [test, blog]
description: "A test post"
---

# Test Post

This is a test post.
"""
        (posts_dir / "test-post.md").write_text(post_content)

        page_content = """---
title: "Test Page"
date: 2025-10-17
description: "A test page"
---

# Test Page

This is a test page.
"""
        (pages_dir / "test-page.md").write_text(page_content)

        # Create test templates (copy from main project)
        main_project = Path(__file__).parent.parent
        template_files = [
            "base.html",
            "index.html",
            "post.html",
            "tag.html",
            "page.html",
        ]

        for template_file in template_files:
            src = main_project / "templates" / template_file
            if src.exists():
                shutil.copy(src, template_dir / template_file)

        # Create test static file
        (static_dir / "test.css").write_text("body { margin: 0; }")

        # Run build
        generator = SiteGenerator(temp_path)
        generator.build()

        # Verify outputs
        site_dir = temp_path / "site"
        assert site_dir.exists()

        # Check index page
        index_file = site_dir / "index.html"
        assert index_file.exists()
        index_content = index_file.read_text()
        assert "Test Post" in index_content

        # Check post page
        post_file = site_dir / "posts" / "test-post" / "index.html"
        assert post_file.exists()
        post_html = post_file.read_text()
        assert "Test Post" in post_html
        assert "This is a test post" in post_html

        # Check page
        page_file = site_dir / "test-page" / "index.html"
        assert page_file.exists()
        page_html = page_file.read_text()
        assert "Test Page" in page_html

        # Check tag page
        tag_file = site_dir / "tag" / "test" / "index.html"
        assert tag_file.exists()

        # Check static assets
        static_file = site_dir / "static" / "test.css"
        assert static_file.exists()


if __name__ == "__main__":
    test_complete_build_pipeline()
    print("All tests passed!")
