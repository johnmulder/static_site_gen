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

## 7. Strengthen Testing Strategy -- DONE

Created `tests/fixtures/` with sample content files and `tests/conftest.py` with
shared fixtures (`sample_config`, `sample_project`, content fixtures). Converted
`test_security.py` from manual for-loops to `@pytest.mark.parametrize` (6 tests
-> 25 individual parametrized tests). Expanded integration tests from 1 to 12,
covering multi-post ordering, draft filtering (output, tags, RSS), tag page
content, static asset directory preservation, empty builds, and RSS feed
generation. Added 4 dedicated `discover_content()` tests. Split
`test_config_loading_edge_cases` into 3 focused tests. Total test count: 144
(up from 108).

______________________________________________________________________

## 8. Harden HTML Sanitization -- DONE

Documented the trust boundary in `sanitize_html()` docstring: content is
author-controlled local Markdown, so the basic script-tag removal serves as
defense-in-depth. Docstring now explicitly notes the limitation and recommends
`nh3` if third-party content is ever supported.

______________________________________________________________________

## 9. Implement `init` Command -- DONE

Replaced the stub with a working `cmd_init` that scaffolds a new project
directory with `config.yaml`, `content/posts/` (sample hello-world post),
`content/pages/` (about page), `templates/` (copies real templates from the
package), and `static/style.css`. Refuses to overwrite non-empty directories.
Added 4 tests for the init command (structure, refusal, config content, main
integration). Updated 2 old "not implemented" tests. All 145 tests pass.

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
