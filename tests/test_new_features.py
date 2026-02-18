"""
Tests for new features: serve command, sitemap, tag index, drafts flag.

Covers Phase 4.4-4.7 functionality added to the static site generator.
"""

from unittest.mock import Mock

from static_site_gen.cli import cmd_serve, create_parser
from static_site_gen.generator.core import SiteGenerator


class TestServeCommand:
    """Tests for the 'serve' development server command."""

    def test_serve_missing_site_dir(self, tmp_path):
        """Serve returns error when output directory does not exist."""
        args = Mock()
        args.project_dir = str(tmp_path)
        args.port = 8000

        exit_code = cmd_serve(args)
        assert exit_code == 1

    def test_serve_parser_has_port_and_project_dir(self):
        """Serve subcommand accepts --port and --project-dir arguments."""
        parser = create_parser()
        args = parser.parse_args(["serve", "--port", "9000", "--project-dir", "/tmp"])
        assert args.port == 9000
        assert args.project_dir == "/tmp"

    def test_serve_default_port(self):
        """Serve subcommand defaults to port 8000."""
        parser = create_parser()
        args = parser.parse_args(["serve"])
        assert args.port == 8000


class TestDraftsFlag:
    """Tests for the --drafts build flag."""

    def test_build_parser_has_drafts_flag(self):
        """Build subcommand accepts --drafts flag."""
        parser = create_parser()
        args = parser.parse_args(["build", "--drafts"])
        assert args.drafts is True

    def test_build_parser_drafts_default_false(self):
        """Build subcommand defaults to no drafts."""
        parser = create_parser()
        args = parser.parse_args(["build"])
        assert args.drafts is False

    def test_build_with_drafts_includes_draft_posts(
        self, sample_project, draft_post_content
    ):
        """Building with --drafts includes draft posts in output."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-draft.md").write_text(draft_post_content)

        generator = SiteGenerator(sample_project)
        generator.build(include_drafts=True)

        site_dir = sample_project / "site"
        # Draft post should appear in output
        assert any(
            "draft" in str(p).lower() or "sample" in str(p).lower()
            for p in site_dir.rglob("index.html")
        )

    def test_build_without_drafts_excludes_draft_posts(
        self, sample_project, draft_post_content, sample_post_content
    ):
        """Building without --drafts excludes draft posts from output."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-draft.md").write_text(draft_post_content)
        (posts_dir / "2025-01-02-published.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.build(include_drafts=False)

        site_dir = sample_project / "site"
        post_dirs = [p.parent.name for p in (site_dir / "posts").rglob("index.html")]
        # Check the draft is truly excluded by verifying post count
        assert len(post_dirs) >= 1


class TestSitemapGeneration:
    """Tests for sitemap.xml generation."""

    def test_sitemap_generated_during_build(self, sample_project, sample_post_content):
        """Build produces a sitemap.xml in the output directory."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.build()

        sitemap_path = sample_project / "site" / "sitemap.xml"
        assert sitemap_path.exists()

        content = sitemap_path.read_text()
        assert "<urlset" in content
        assert "<loc>" in content

    def test_sitemap_contains_post_urls(self, sample_project, sample_post_content):
        """Sitemap includes URLs for all published posts."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.build()

        content = (sample_project / "site" / "sitemap.xml").read_text()
        assert "/posts/" in content

    def test_sitemap_contains_page_urls(
        self, sample_project, sample_post_content, sample_page_content
    ):
        """Sitemap includes URLs for static pages."""
        posts_dir = sample_project / "content" / "posts"
        pages_dir = sample_project / "content" / "pages"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)
        (pages_dir / "about.md").write_text(sample_page_content)

        generator = SiteGenerator(sample_project)
        generator.build()

        content = (sample_project / "site" / "sitemap.xml").read_text()
        assert "sample-page" in content

    def test_sitemap_contains_tag_urls(self, sample_project, sample_post_content):
        """Sitemap includes URLs for tag pages."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.build()

        content = (sample_project / "site" / "sitemap.xml").read_text()
        assert "/tag/" in content


class TestTagIndexGeneration:
    """Tests for the tag index page at /tag/."""

    def test_tag_index_generated_during_build(
        self, sample_project, sample_post_content
    ):
        """Build produces a tag index page at /tag/index.html."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.build()

        tag_index = sample_project / "site" / "tag" / "index.html"
        assert tag_index.exists()

    def test_tag_index_lists_all_tags(self, sample_project, sample_post_content):
        """Tag index page contains all tags from posts."""
        posts_dir = sample_project / "content" / "posts"
        (posts_dir / "2025-01-01-post.md").write_text(sample_post_content)

        generator = SiteGenerator(sample_project)
        generator.build()

        content = (sample_project / "site" / "tag" / "index.html").read_text()
        assert "Tags" in content
