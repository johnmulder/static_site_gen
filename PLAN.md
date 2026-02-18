# Improvement Plan

Issues identified from alignment analysis of code against stated project goals.
Organized by priority and grouped by theme.

______________________________________________________________________

## 1. Fix Malformed Content Files -- DONE

Restored proper YAML front matter delimiters in all three content files.
Build and all 108 tests pass.

______________________________________________________________________

## 2. Implement RSS Feed Generation

**Problem:** The build process spec lists "Build RSS feed (`feed.xml`)" as step 8.
`config.yaml` has a commented-out `# rss_feed: true` placeholder. No code exists.

**Work:**

- Add `generate_feed()` method to `SiteGenerator` in `core.py`
- Create `templates/feed.xml` Jinja2 template (with autoescape disabled for XML)
- Output to `site/feed.xml`
- Add `<link rel="alternate" type="application/rss+xml">` to `base.html`
- Add tests for feed generation (valid XML, correct post entries, proper dates)

______________________________________________________________________

## 3. Extract Repeated Dict Conversion to Helper

**Problem:** The `ParsedContent` -> `dict` conversion is copy-pasted four times
in `core.py` (`generate_posts`, `generate_index`, `generate_tag_pages`,
`generate_pages`).

**Work:**

- Add a `to_dict()` method on `ParsedContent` (or a standalone function in parser)
- Replace the four inline conversions with calls to it

______________________________________________________________________

## 4. Rename `utils.py` to Express Intent

**Problem:** The coding standards say to avoid "util" or "helper" suffixes and
instead express intent. The module contains file operations, URL generation,
sorting, filtering, and pagination.

**Options:**

- Rename to `files.py` + `urls.py` (split by concern)
- Rename to `output.py` (most functions relate to output generation)
- Keep as-is if the cost of renaming outweighs the benefit at this stage

**Recommendation:** Rename to `output.py` since the dominant operations are
URL generation, path resolution, file writing, pagination, and directory
management -- all output-side concerns. Update all imports in `core.py` and tests.

______________________________________________________________________

## 5. Replace Config Dict with Dataclass

**Problem:** The copilot instructions specify "use dataclass with type hints for
configuration structure." Config is currently `dict[str, Any]` throughout.

**Work:**

- Create `SiteConfig` dataclass with typed fields in a new module or in `core.py`
- Move validation logic from `load_config()` into `SiteConfig.__post_init__`
  or a classmethod constructor
- Update `TemplateRenderer` methods to accept `SiteConfig` instead of `dict`
- Update tests accordingly

______________________________________________________________________

## 6. Enrich Index Template

**Problem:** `templates/index.html` only renders post titles. The content model
includes `date`, `description`, and `tags` -- none of which appear on the homepage.

**Work:**

- Add date display to each post item
- Add description excerpt when available
- Add tag links per post
- Keep it minimal but informative

______________________________________________________________________

## 7. Strengthen Testing Strategy

### 7a. Create `tests/fixtures/` directory

The copilot instructions specify test data in `tests/fixtures/`. Currently all
fixtures are created inline with `tmp_path`.

- Add sample Markdown files (valid, missing fields, draft, unicode, etc.)
- Add a sample `config.yaml`
- Add a sample template set

### 7b. Add `conftest.py` with shared fixtures

Reduce duplication across test files:

- `sample_config` fixture (creates valid config dict/file)
- `sample_project` fixture (creates minimal project structure)
- `sample_post_content` fixture (returns front matter + markdown string)

### 7c. Use `@pytest.mark.parametrize`

Convert manual for-loops in `test_security.py` and elsewhere to parametrized
tests for better failure diagnostics.

### 7d. Expand integration tests

Current coverage: 1 test. Add tests for:

- Multiple posts with correct chronological ordering
- Draft posts excluded from build output
- Pagination output (page 2+ directories created)
- Tag page content verification
- Static asset copying preserves directory structure
- Build with no posts (empty site)
- Build with no pages

### 7e. Add test for `discover_content()`

This method currently has zero dedicated test coverage.

### 7f. Split multi-assertion tests

`test_config_loading_edge_cases` in `test_core_edge_cases.py` tests three
unrelated scenarios in one function. Split into individual tests.

______________________________________________________________________

## 8. Harden HTML Sanitization

**Problem:** `sanitize_html()` in `parser.py` only strips `<script>` tags via
regex. It ignores `<iframe>`, event handler attributes (`onclick`, `onerror`),
and `javascript:` URLs.

**Options:**

- Replace with a proper allowlist-based sanitizer (e.g., `bleach` or
  `nh3` library)
- Expand the regex approach to cover more vectors (fragile, not recommended)
- Document that content is trusted (author-controlled) and accept the risk

**Recommendation:** Since content comes from local Markdown files written by the
site author, document the trust boundary explicitly. If third-party content is
ever supported, add `nh3` as a dependency for proper sanitization.

______________________________________________________________________

## 9. Implement `init` Command

**Problem:** `cli.py` has a stub that prints "not implemented" and returns 1.
README advertises it as "Coming soon."

**Work:**

- Create project scaffold: `content/posts/`, `content/pages/`, `templates/`,
  `static/`, `config.yaml`
- Copy default templates and sample content
- Add tests for the init command

______________________________________________________________________

## 10. Protect Content Files from mdformat

**Problem:** The root cause of issue 1. `mdformat` does not understand YAML
front matter by default and rewrites the `---` delimiters.

**Options:**

- Install `mdformat-frontmatter` plugin and add to dev dependencies
- Add content files to an exclude pattern in the mdformat config
- Add a note to `DEVELOPMENT.md` warning about this

**Recommendation:** Add `mdformat-frontmatter` to dev dependencies in
`pyproject.toml` and document it. Also add a glob exclude for `content/` in
any formatting CI step as a safety net.

______________________________________________________________________

## Priority Order

| Priority | Issue                              | Effort | Impact                        |
| -------- | ---------------------------------- | ------ | ----------------------------- |
| 1        | Fix malformed content files        | Small  | Critical -- content is broken |
| 2        | Protect content from mdformat      | Small  | Prevents recurrence of #1     |
| 3        | Extract dict conversion helper     | Small  | Code quality                  |
| 4        | Rename `utils.py`                  | Small  | Standards alignment           |
| 5        | Enrich index template              | Small  | User-facing quality           |
| 6        | Implement RSS feed                 | Medium | Feature completeness          |
| 7        | Replace config dict with dataclass | Medium | Type safety, standards        |
| 8        | Strengthen testing strategy        | Medium | Long-term reliability         |
| 9        | Harden HTML sanitization           | Small  | Security posture              |
| 10       | Implement `init` command           | Medium | Feature completeness          |
