"""
End-to-end integration tests for the static site generator.

Tests the complete build pipeline from content files to generated output,
covering multi-post ordering, draft filtering, tag pages, RSS feed,
static assets, and empty-site edge cases.
"""

from pathlib import Path

from static_site_gen.generator.core import SiteGenerator


def _write_post(posts_dir: Path, filename: str, content: str) -> None:
    """Write a Markdown post file to the given directory."""
    (posts_dir / filename).write_text(content)


def _write_page(pages_dir: Path, filename: str, content: str) -> None:
    """Write a Markdown page file to the given directory."""
    (pages_dir / filename).write_text(content)


def _build(project_root: Path) -> Path:
    """Run a full build and return the site output directory."""
    generator = SiteGenerator(project_root)
    generator.build()
    return project_root / "site"


class TestCompleteBuildPipeline:
    """Tests for the full build pipeline with typical content."""

    def test_basic_post_and_page(self, sample_project):
        """Test that a single post and page are generated correctly."""
        posts_dir = sample_project / "content" / "posts"
        pages_dir = sample_project / "content" / "pages"

        _write_post(
            posts_dir,
            "2025-10-17-hello.md",
            "---\n"
            'title: "Hello World"\n'
            "date: 2025-10-17\n"
            "tags: [intro]\n"
            'description: "First post"\n'
            "---\n\n"
            "Hello content.\n",
        )
        _write_page(
            pages_dir,
            "about.md",
            '---\ntitle: "About"\ndate: 2025-10-17\n---\n\nAbout page content.\n',
        )

        site = _build(sample_project)

        # Index exists and references the post
        index_html = (site / "index.html").read_text()
        assert "Hello World" in index_html

        # Post page exists with correct content
        post_html = (site / "posts" / "hello-world" / "index.html").read_text()
        assert "Hello content." in post_html

        # Page exists
        page_html = (site / "about" / "index.html").read_text()
        assert "About page content." in page_html

        # Tag page exists
        assert (site / "tag" / "intro" / "index.html").exists()

        # Static assets copied
        assert (site / "static" / "style.css").exists()

    def test_rss_feed_generated(self, sample_project):
        """Test that RSS feed.xml is generated with post data."""
        posts_dir = sample_project / "content" / "posts"
        _write_post(
            posts_dir,
            "2025-10-17-rss-test.md",
            "---\n"
            'title: "RSS Test Post"\n'
            "date: 2025-10-17\n"
            "tags: [rss]\n"
            'description: "Testing RSS"\n'
            "---\n\n"
            "RSS body.\n",
        )

        site = _build(sample_project)

        feed_path = site / "feed.xml"
        assert feed_path.exists()
        feed_xml = feed_path.read_text()
        assert "RSS Test Post" in feed_xml
        assert "rss-test-post" in feed_xml
        assert "<rss" in feed_xml


class TestMultiPostOrdering:
    """Tests that multiple posts are listed in correct chronological order."""

    def test_index_lists_posts_newest_first(self, sample_project):
        """Posts on the index page appear newest-first."""
        posts_dir = sample_project / "content" / "posts"

        _write_post(
            posts_dir,
            "2025-01-01-older.md",
            '---\ntitle: "Older Post"\ndate: 2025-01-01\n---\n\nOlder.\n',
        )
        _write_post(
            posts_dir,
            "2025-06-15-middle.md",
            '---\ntitle: "Middle Post"\ndate: 2025-06-15\n---\n\nMiddle.\n',
        )
        _write_post(
            posts_dir,
            "2025-12-31-newest.md",
            '---\ntitle: "Newest Post"\ndate: 2025-12-31\n---\n\nNewest.\n',
        )

        site = _build(sample_project)
        index_html = (site / "index.html").read_text()

        newest_pos = index_html.index("Newest Post")
        middle_pos = index_html.index("Middle Post")
        older_pos = index_html.index("Older Post")

        assert newest_pos < middle_pos < older_pos


class TestDraftFiltering:
    """Tests that draft posts are excluded from generated output."""

    def test_draft_post_excluded_from_site(self, sample_project):
        """Draft posts should not appear in any generated output."""
        posts_dir = sample_project / "content" / "posts"

        _write_post(
            posts_dir,
            "2025-10-17-published.md",
            '---\ntitle: "Published Post"\ndate: 2025-10-17\ntags: [visible]\n---\n\nPublished.\n',
        )
        _write_post(
            posts_dir,
            "2025-10-16-secret.md",
            "---\n"
            'title: "Secret Draft"\n'
            "date: 2025-10-16\n"
            "tags: [visible]\n"
            "draft: true\n"
            "---\n\n"
            "Secret.\n",
        )

        site = _build(sample_project)

        # Draft post directory should not exist
        assert not (site / "posts" / "secret-draft" / "index.html").exists()

        # Draft should not appear in index
        index_html = (site / "index.html").read_text()
        assert "Secret Draft" not in index_html
        assert "Published Post" in index_html

    def test_draft_excluded_from_tag_pages(self, sample_project):
        """Draft posts should not appear on tag pages."""
        posts_dir = sample_project / "content" / "posts"

        _write_post(
            posts_dir,
            "2025-10-17-public.md",
            '---\ntitle: "Public"\ndate: 2025-10-17\ntags: [shared-tag]\n---\n\nPublic.\n',
        )
        _write_post(
            posts_dir,
            "2025-10-16-hidden.md",
            "---\n"
            'title: "Hidden Draft"\n'
            "date: 2025-10-16\n"
            "tags: [shared-tag]\n"
            "draft: true\n"
            "---\n\n"
            "Hidden.\n",
        )

        site = _build(sample_project)
        tag_html = (site / "tag" / "shared-tag" / "index.html").read_text()

        assert "Public" in tag_html
        assert "Hidden Draft" not in tag_html

    def test_draft_excluded_from_rss(self, sample_project):
        """Draft posts should not appear in the RSS feed."""
        posts_dir = sample_project / "content" / "posts"

        _write_post(
            posts_dir,
            "2025-10-17-visible.md",
            '---\ntitle: "Visible Post"\ndate: 2025-10-17\n---\n\nVisible.\n',
        )
        _write_post(
            posts_dir,
            "2025-10-16-draft.md",
            '---\ntitle: "Draft Post"\ndate: 2025-10-16\ndraft: true\n---\n\nDraft.\n',
        )

        site = _build(sample_project)
        feed_xml = (site / "feed.xml").read_text()

        assert "Visible Post" in feed_xml
        assert "Draft Post" not in feed_xml


class TestTagPages:
    """Tests for tag archive page generation."""

    def test_separate_tag_pages_created(self, sample_project):
        """Each unique tag gets its own archive page."""
        posts_dir = sample_project / "content" / "posts"

        _write_post(
            posts_dir,
            "2025-10-17-a.md",
            '---\ntitle: "Post A"\ndate: 2025-10-17\ntags: [alpha, beta]\n---\n\nA.\n',
        )
        _write_post(
            posts_dir,
            "2025-10-16-b.md",
            '---\ntitle: "Post B"\ndate: 2025-10-16\ntags: [beta, gamma]\n---\n\nB.\n',
        )

        site = _build(sample_project)

        assert (site / "tag" / "alpha" / "index.html").exists()
        assert (site / "tag" / "beta" / "index.html").exists()
        assert (site / "tag" / "gamma" / "index.html").exists()

    def test_tag_page_lists_correct_posts(self, sample_project):
        """Tag page only lists posts with that tag."""
        posts_dir = sample_project / "content" / "posts"

        _write_post(
            posts_dir,
            "2025-10-17-x.md",
            '---\ntitle: "Tagged X"\ndate: 2025-10-17\ntags: [target-tag]\n---\n\nX.\n',
        )
        _write_post(
            posts_dir,
            "2025-10-16-y.md",
            '---\ntitle: "Untagged Y"\ndate: 2025-10-16\ntags: [other]\n---\n\nY.\n',
        )

        site = _build(sample_project)
        tag_html = (site / "tag" / "target-tag" / "index.html").read_text()

        assert "Tagged X" in tag_html
        assert "Untagged Y" not in tag_html


class TestStaticAssets:
    """Tests for static asset copying."""

    def test_static_directory_structure_preserved(self, sample_project):
        """Nested static files should be copied with their directory structure."""
        static_dir = sample_project / "static"
        sub_dir = static_dir / "images"
        sub_dir.mkdir()
        (sub_dir / "logo.png").write_bytes(b"\x89PNG")

        # Need at least one post for a build to run fully
        _write_post(
            sample_project / "content" / "posts",
            "2025-10-17-stub.md",
            '---\ntitle: "Stub"\ndate: 2025-10-17\n---\n\nStub.\n',
        )

        site = _build(sample_project)
        assert (site / "static" / "style.css").exists()
        assert (site / "static" / "images" / "logo.png").exists()


class TestEmptyBuilds:
    """Tests for edge cases with no content."""

    def test_build_with_no_posts(self, sample_project):
        """Build succeeds with pages but no posts."""
        pages_dir = sample_project / "content" / "pages"
        _write_page(
            pages_dir,
            "about.md",
            '---\ntitle: "About"\ndate: 2025-10-17\n---\n\nAbout text.\n',
        )

        site = _build(sample_project)

        # Index should exist (even if empty of posts)
        assert (site / "about" / "index.html").exists()

    def test_build_with_no_content(self, sample_project):
        """Build succeeds with completely empty content directories."""
        site = _build(sample_project)
        # Should not crash
        assert (site / "static" / "style.css").exists()

    def test_build_with_only_drafts(self, sample_project):
        """Build succeeds when all posts are drafts (no published output)."""
        posts_dir = sample_project / "content" / "posts"
        _write_post(
            posts_dir,
            "2025-10-17-draft.md",
            '---\ntitle: "Only Draft"\ndate: 2025-10-17\ndraft: true\n---\n\nDraft.\n',
        )

        site = _build(sample_project)
        assert not (site / "posts" / "only-draft" / "index.html").exists()
        # Static assets still copied
        assert (site / "static" / "style.css").exists()
