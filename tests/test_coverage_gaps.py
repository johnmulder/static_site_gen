"""
Tests targeting uncovered code paths for coverage improvement.

These tests cover guard clauses, error handling, edge cases, and validation
paths that were not reached by existing tests.
"""

# pylint: disable=protected-access,import-outside-toplevel,import-error
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from static_site_gen.cli import cmd_build, main
from static_site_gen.generator.core import SiteGenerator
from static_site_gen.generator.output import (
    clean_output_dir,
    get_output_path,
    paginate_posts,
)
from static_site_gen.generator.parser import (
    ParseError,
    extract_front_matter,
    generate_slug,
    parse_content_file,
)
from static_site_gen.generator.renderer import TemplateRenderer

# ── CLI coverage ──────────────────────────────────────────────────────────


class TestCLICoverage:
    """Cover CLI error-handling paths."""

    def test_build_catches_os_error(self, tmp_path):
        """Build catches OSError and returns exit code 1."""
        args = Mock()
        args.project_dir = str(tmp_path)
        args.drafts = False

        # Create a config.yaml that will cause an OSError during build
        # by making the output directory unwritable
        import yaml

        config = {
            "site_name": "Test",
            "base_url": "https://example.com",
            "author": "Test",
        }
        (tmp_path / "config.yaml").write_text(yaml.dump(config))
        # No templates directory -> build will fail
        exit_code = cmd_build(args)
        assert exit_code == 1

    def test_main_unknown_subcommand(self):
        """main() with unknown subcommand exits with error code."""
        with patch("sys.argv", ["cli.py", "nonexistent"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2


# ── Core guard clauses ────────────────────────────────────────────────────


class TestCoreGuardClauses:
    """Cover RuntimeError guards when config/renderer not initialized."""

    def test_process_content_files_without_config(self, sample_project):
        """_process_content_files raises when config is None."""
        generator = SiteGenerator(sample_project)
        # config not loaded
        with pytest.raises(RuntimeError, match="Configuration must be loaded"):
            generator._process_content_files([], "post")

    def test_process_content_without_config(self, sample_project):
        """process_content raises when config is None."""
        generator = SiteGenerator(sample_project)
        with pytest.raises(RuntimeError, match="Configuration must be loaded"):
            generator.process_content({"posts": [], "pages": []})

    def test_generate_posts_without_renderer(
        self,
        sample_project,
        sample_post_content,  # noqa: ARG002
    ):  # pylint: disable=unused-argument
        """generate_posts raises when renderer is not initialized."""
        generator = SiteGenerator(sample_project)
        generator.load_config()
        # renderer is None
        with pytest.raises(RuntimeError, match="Renderer and config"):
            generator.generate_posts([])

    def test_generate_index_without_renderer(self, sample_project):
        """generate_index raises when renderer is not initialized."""
        generator = SiteGenerator(sample_project)
        generator.load_config()
        with pytest.raises(RuntimeError, match="Renderer and config"):
            generator.generate_index([])

    def test_generate_tag_pages_without_renderer(self, sample_project):
        """generate_tag_pages raises when renderer is not initialized."""
        generator = SiteGenerator(sample_project)
        generator.load_config()
        with pytest.raises(RuntimeError, match="Renderer and config"):
            generator.generate_tag_pages([])

    def test_generate_tag_index_without_renderer(self, sample_project):
        """generate_tag_index raises when renderer is not initialized."""
        generator = SiteGenerator(sample_project)
        generator.load_config()
        with pytest.raises(RuntimeError, match="Renderer and config"):
            generator.generate_tag_index([])

    def test_generate_feed_without_renderer(self, sample_project):
        """generate_feed raises when renderer is not initialized."""
        generator = SiteGenerator(sample_project)
        generator.load_config()
        with pytest.raises(RuntimeError, match="Renderer and config"):
            generator.generate_feed([])

    def test_generate_sitemap_without_renderer(self, sample_project):
        """generate_sitemap raises when renderer is not initialized."""
        generator = SiteGenerator(sample_project)
        generator.load_config()
        with pytest.raises(RuntimeError, match="Renderer and config"):
            generator.generate_sitemap([], [])

    def test_generate_pages_without_renderer(self, sample_project):
        """generate_pages raises when renderer is not initialized."""
        generator = SiteGenerator(sample_project)
        generator.load_config()
        with pytest.raises(RuntimeError, match="Renderer and config"):
            generator.generate_pages([])


class TestCoreConfigValidation:
    """Cover config validation edge cases."""

    def test_invalid_posts_per_page(self, sample_project):
        """posts_per_page must be a positive integer."""
        import yaml

        config = {
            "site_name": "Test",
            "base_url": "https://example.com",
            "author": "Test",
            "posts_per_page": -1,
        }
        (sample_project / "config.yaml").write_text(yaml.dump(config))

        generator = SiteGenerator(sample_project)
        with pytest.raises(ValueError, match="posts_per_page"):
            generator.load_config()

    def test_string_posts_per_page(self, sample_project):
        """posts_per_page rejects string values."""
        import yaml

        config = {
            "site_name": "Test",
            "base_url": "https://example.com",
            "author": "Test",
            "posts_per_page": "ten",
        }
        (sample_project / "config.yaml").write_text(yaml.dump(config))

        generator = SiteGenerator(sample_project)
        with pytest.raises(ValueError, match="posts_per_page"):
            generator.load_config()


# ── Output module coverage ────────────────────────────────────────────────


class TestOutputCoverage:
    """Cover edge cases in output module functions."""

    def test_get_output_path_whitespace_segment(self, tmp_path):
        """Path segments with leading/trailing whitespace are rejected."""
        with pytest.raises(ValueError, match="Invalid path segment"):
            get_output_path(tmp_path, "/ foo /")

    def test_get_output_path_empty_url(self, tmp_path):
        """Empty URL path resolves to base_dir/index.html."""
        result = get_output_path(tmp_path, "/")
        assert result == tmp_path / "index.html"

    def test_clean_output_dir_rejects_root(self):
        """clean_output_dir refuses to clean system directories."""
        with pytest.raises(ValueError, match="dangerous directory"):
            clean_output_dir(Path("/"))

    def test_clean_output_dir_rejects_home_like(self, tmp_path):
        """clean_output_dir refuses to clean directories with user files."""
        # Create a .bashrc to trigger the safety check
        (tmp_path / ".bashrc").write_text("")
        with pytest.raises(ValueError, match="user files"):
            clean_output_dir(tmp_path)

    def test_paginate_posts_rejects_negative(self):
        """paginate_posts raises with non-positive posts_per_page."""
        with pytest.raises(ValueError, match="positive"):
            paginate_posts([], -1)

    def test_paginate_posts_empty_list(self):
        """paginate_posts returns a single empty page for no posts."""
        result = paginate_posts([], 5)
        assert len(result) == 1
        assert result[0]["posts"] == []
        assert result[0]["page_number"] == 1
        assert result[0]["total_pages"] == 1


# ── Parser coverage ──────────────────────────────────────────────────────


class TestParserCoverage:
    """Cover parser edge cases."""

    def test_front_matter_empty_body(self):
        """Content with front matter but empty body parses successfully."""
        content = "---\ntitle: Test\ndate: 2025-01-01\n---\n"
        front_matter, body = extract_front_matter(content, Path("test.md"))
        assert front_matter["title"] == "Test"
        assert body == ""

    def test_extract_front_matter_reraises_parse_error(self):
        """ParseError is re-raised without wrapping."""
        # Content with invalid YAML that triggers a scanner error
        content = "---\ninvalid: [unbalanced\n---\nBody"
        with pytest.raises(ParseError):
            extract_front_matter(content, Path("test.md"))

    def test_slug_generation_all_symbols(self):
        """Titles with only symbols produce a hash-based fallback slug."""
        slug = generate_slug("!@#$%^&*()")
        assert slug.startswith("post-")
        assert len(slug) > 5

    def test_slug_generation_short_ascii_uses_unicode_fallback(self):
        """Short ASCII titles (< 3 chars) fall through to unicode slug path."""
        slug = generate_slug("a")
        assert slug == "a"

    def test_parse_content_file_unicode_error(self, tmp_path):
        """Files with invalid encoding raise ParseError."""
        bad_file = tmp_path / "bad.md"
        bad_file.write_bytes(b"---\ntitle: Test\ndate: 2025-01-01\n---\n\xff\xfe")
        with pytest.raises(ParseError, match="encoding error"):
            parse_content_file(bad_file)


# ── Renderer coverage ────────────────────────────────────────────────────


class TestRendererCoverage:
    """Cover renderer edge cases."""

    def test_get_available_templates(self):
        """get_available_templates lists template files."""
        from tests.conftest import PROJECT_ROOT

        renderer = TemplateRenderer(PROJECT_ROOT / "templates")
        templates = renderer.get_available_templates()
        assert "base.html" in templates
        assert "post.html" in templates
        assert "sitemap.xml" in templates

    def test_render_index_page_with_pagination(self):
        """Index page title includes page number for page > 1."""
        from static_site_gen.generator.core import SiteConfig
        from tests.conftest import PROJECT_ROOT

        renderer = TemplateRenderer(PROJECT_ROOT / "templates")
        config = SiteConfig(
            site_name="Test",
            base_url="https://example.com",
            author="Test",
        )
        pagination = {
            "current_page": 2,
            "total_pages": 3,
            "has_previous": True,
            "has_next": True,
            "previous_url": "/",
            "next_url": "/page/3/",
        }

        html = renderer.render_index_page([], config, pagination)
        assert "Page 2" in html


# ── Core error-handling paths ─────────────────────────────────────────────


class TestCoreErrorHandling:
    """Cover error-logging paths in generate_* methods."""

    def test_generate_posts_logs_render_error(
        self, sample_project, sample_post_content
    ):
        """generate_posts logs error and continues when rendering fails."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.load_config()
        generator.renderer = TemplateRenderer(generator.template_dir)
        generator.output_dir = sample_project / "site"
        generator.output_dir.mkdir(exist_ok=True)

        # Parse real content
        posts = generator._process_content_files(list(posts_dir.glob("*.md")), "post")

        # Patch renderer to raise on render_post
        with patch.object(
            generator.renderer, "render_post", side_effect=ValueError("bad template")
        ):
            # Should not raise -- error is logged, post is skipped
            generator.generate_posts(posts)

    def test_generate_tag_pages_logs_render_error(
        self, sample_project, sample_post_content
    ):
        """generate_tag_pages logs error and continues for individual tags."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.load_config()
        generator.renderer = TemplateRenderer(generator.template_dir)
        generator.output_dir = sample_project / "site"
        generator.output_dir.mkdir(exist_ok=True)

        posts = generator._process_content_files(list(posts_dir.glob("*.md")), "post")

        with patch.object(
            generator.renderer,
            "render_tag_page",
            side_effect=ValueError("bad template"),
        ):
            generator.generate_tag_pages(posts)

    def test_generate_pages_logs_render_error(
        self, sample_project, sample_page_content
    ):
        """generate_pages logs error and continues for individual pages."""
        pages_dir = sample_project / "content" / "pages"
        (pages_dir / "about.md").write_text(sample_page_content)

        generator = SiteGenerator(sample_project)
        generator.load_config()
        generator.renderer = TemplateRenderer(generator.template_dir)
        generator.output_dir = sample_project / "site"
        generator.output_dir.mkdir(exist_ok=True)

        pages = generator._process_content_files(list(pages_dir.glob("*.md")), "page")

        with patch.object(
            generator.renderer, "render_page", side_effect=ValueError("bad template")
        ):
            generator.generate_pages(pages)

    def test_generate_feed_logs_render_error(self, sample_project, sample_post_content):
        """generate_feed logs error when rendering fails."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.load_config()
        generator.renderer = TemplateRenderer(generator.template_dir)
        generator.output_dir = sample_project / "site"
        generator.output_dir.mkdir(exist_ok=True)

        posts = generator._process_content_files(list(posts_dir.glob("*.md")), "post")

        with patch.object(
            generator.renderer, "render_feed", side_effect=ValueError("bad template")
        ):
            # Should not raise -- error is logged
            generator.generate_feed(posts)

    def test_generate_tag_index_logs_render_error(
        self, sample_project, sample_post_content
    ):
        """generate_tag_index logs error when rendering fails."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.load_config()
        generator.renderer = TemplateRenderer(generator.template_dir)
        generator.output_dir = sample_project / "site"
        generator.output_dir.mkdir(exist_ok=True)

        posts = generator._process_content_files(list(posts_dir.glob("*.md")), "post")

        with patch.object(
            generator.renderer,
            "render_tag_index",
            side_effect=ValueError("bad template"),
        ):
            generator.generate_tag_index(posts)

    def test_generate_sitemap_logs_render_error(
        self, sample_project, sample_post_content
    ):
        """generate_sitemap logs error when rendering fails."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.load_config()
        generator.renderer = TemplateRenderer(generator.template_dir)
        generator.output_dir = sample_project / "site"
        generator.output_dir.mkdir(exist_ok=True)

        posts = generator._process_content_files(list(posts_dir.glob("*.md")), "post")

        with patch.object(
            generator.renderer,
            "render_sitemap",
            side_effect=ValueError("bad template"),
        ):
            generator.generate_sitemap(posts, [])

    def test_generate_index_logs_render_error(
        self, sample_project, sample_post_content
    ):
        """generate_index logs error when rendering fails."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.load_config()
        generator.renderer = TemplateRenderer(generator.template_dir)
        generator.output_dir = sample_project / "site"
        generator.output_dir.mkdir(exist_ok=True)

        posts = generator._process_content_files(list(posts_dir.glob("*.md")), "post")

        with patch.object(
            generator.renderer,
            "render_index_page",
            side_effect=ValueError("bad template"),
        ):
            with pytest.raises(ValueError, match="bad template"):
                generator.generate_index(posts)

    def test_generate_index_pagination(self, sample_project):
        """generate_index creates paginated pages when post count exceeds limit."""
        import yaml

        # Set posts_per_page to 1 so we get multiple pages
        config = {
            "site_name": "Test",
            "base_url": "https://example.com",
            "author": "Test",
            "posts_per_page": 1,
        }
        (sample_project / "config.yaml").write_text(yaml.dump(config))

        posts_dir = sample_project / "content" / "posts"
        for i in range(3):
            content = (
                f"---\ntitle: Post {i}\ndate: 2025-01-0{i+1}\n---\n\nContent {i}\n"
            )
            (posts_dir / f"2025-01-0{i+1}-post-{i}.md").write_text(content)

        generator = SiteGenerator(sample_project)
        generator.build()

        site_dir = sample_project / "site"
        assert (site_dir / "index.html").exists()
        assert (site_dir / "page" / "2" / "index.html").exists()
        assert (site_dir / "page" / "3" / "index.html").exists()
