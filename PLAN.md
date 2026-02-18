# Improvement Plan

Issues identified from alignment analysis of code against stated project goals.
Organized by priority and grouped by theme.

______________________________________________________________________

## 1. Fix Malformed Content Files -- DONE

Restored proper YAML front matter delimiters in all three content files.
Build and all 108 tests pass.

______________________________________________________________________

## 6. Implement RSS Feed Generation -- DONE

Added `templates/feed.xml` (RSS 2.0 with Atom self-link), `render_feed()` to
`TemplateRenderer`, `generate_feed()` to `SiteGenerator`, and RSS `<link>` to
`base.html`. Feed is generated at `site/feed.xml` during build. Updated
`get_available_templates()` to include non-HTML template files. All 108 tests pass.

______________________________________________________________________

## 3. Extract Repeated Dict Conversion to Helper -- DONE

Added `to_dict()` method to `ParsedContent` dataclass in `parser.py`.
Replaced four inline dict-building blocks in `core.py` with calls to it.
Updated mock objects in `test_core_edge_cases.py` to provide `to_dict()`.
All 108 tests pass.

______________________________________________________________________

## 4. Rename `utils.py` to Express Intent -- DONE

Renamed `static_site_gen/generator/utils.py` to `output.py`. Updated module
docstring to describe output-side responsibilities. Updated all imports in
`core.py`, `test_utils.py`, and `test_security.py`. All 108 tests pass.

______________________________________________________________________

## 7. Replace Config Dict with Dataclass -- DONE

Created `SiteConfig` dataclass in `core.py` with typed fields and a
`from_yaml()` classmethod that encapsulates all validation. Simplified
`load_config()` to a one-liner delegation. Updated `core.py` to use attribute
access instead of dict `.get()` and bracket notation. Updated `renderer.py`
type hints to `Any` and replaced `.get()` calls with `getattr()`. Fixed one
test that used dict subscript access. All 108 tests pass.

______________________________________________________________________

## 5. Enrich Index Template -- DONE

Added date (`<time>` element), tag links, and description paragraph to each
post item in `templates/index.html`. All 108 tests pass and generated output
confirms the enriched listing.

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

## 2. Protect Content Files from mdformat -- DONE

Added `mdformat-frontmatter` to pre-commit hook additional_dependencies and
`pyproject.toml` dev dependencies. Added `exclude: "^content/"` to the mdformat
hook as a safety net. Pre-commit hook now passes without corrupting front matter.

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
