# Improvement Plan

All 10 quality issues identified and implemented. 147 tests passing, 93% coverage.

______________________________________________________________________

## Completed

1. **Fix documentation drift** -- Updated DEVELOPMENT.md (`utils.py` -> `output.py`),
   README.md (init command no longer "Coming soon"), cli.py comment.
1. **Extract shared content-processing loop** -- Extracted `_process_content_files()` helper,
   moved `dataclasses.replace` to top-level import.
1. **Fix parameter shadowing** -- Renamed `posts` to `page_posts` in `generate_index()`.
1. **Remove redundant import** -- Deleted inner `from .output import sort_posts_by_date`
   in `generate_feed()`.
1. **Remove unused `render_index`** -- Deleted dead method from `renderer.py`.
1. **Fix RSS XML escaping** -- Added explicit `| e` filters in `feed.xml`.
1. **Consistent URL encoding** -- Added `urllib.parse.quote()` to `generate_post_url()`
   and `generate_page_url()`.
1. **Stop ignoring `.github/workflows`** -- Removed entry from `.gitignore`.
1. **Fix dangling comment** -- Moved misplaced comment in `parser.py`.
1. **Cover `__main__.py`** -- Added `tests/test_main.py` (100% coverage).
