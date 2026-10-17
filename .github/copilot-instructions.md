# Copilot Instructions - Static Site Generator

This Python 3.12+ project converts locally authored Markdown with YAML front
matter into a static blog using Markdown, PyYAML, and Jinja2. Preserve the
existing architecture and prefer the smallest maintainable change.

## Repository contracts

- Front matter requires a nonempty `title` and a valid `date`. Optional fields
  are `tags` (list), `draft` (boolean), `description` (string), and `slug`.
  Preserve timezone-aware dates, Unicode slug support, and collision handling.
- Configuration requires nonempty `site_name`, `base_url`, and `author` strings.
  Keep absolute HTTP/HTTPS URL, IANA timezone, and positive `posts_per_page`
  validation.
- Posts use `/posts/<slug>/`, pages `/<slug>/`, and tags `/tag/<tag>/`, each
  backed by `index.html`. Preserve URL encoding, newest-first post ordering,
  pagination, tag index, RSS, sitemap, and static asset copying.
- Draft posts are excluded unless `build --drafts` is requested. Invalid content
  files are logged and skipped; configuration and template setup failures stop
  the build. Do not invent a filename-date fallback.
- The CLI is `python -m static_site_gen` or `static-site-gen`, with `build`,
  `init`, and `serve` commands. Preserve command arguments and exit behavior.

## Trust and output boundaries

- Keep YAML safe loading and Jinja2 autoescaping for metadata. Templates mark
  converted Markdown bodies as safe; `sanitize_html` removes script tags but
  is not a full sanitizer. Do not treat this pipeline as safe for third-party
  or user-submitted HTML without revisiting that trust boundary.
- Preserve decoded URL traversal and separator checks, resolved-path containment
  within the selected output directory, and output cleanup guards.
- Builds generate in a temporary sibling directory and replace the configured
  output directory (default `site/`) only after all rendering and writes succeed.
  Use temporary project/output directories in tests and avoid deleting content,
  templates, or user files during verification.

## Development and verification

Implementation lives in `static_site_gen/generator/`; the CLI is
`static_site_gen/cli.py`. Use [README.md](../README.md) for supported usage,
[DEVELOPMENT.md](../DEVELOPMENT.md) for orientation, and
[pyproject.toml](../pyproject.toml) for dependency and tool configuration.
Consult relevant source and tests when prose disagrees with implemented behavior.

Keep changes focused, avoid speculative abstractions or dependencies, and test
behavior rather than implementation details. Prefer ASCII in code, comments,
and documentation when practical; retain supported Unicode content and slugs.

With the development environment activated, the existing checks are:

```bash
make lint
make test
make check
```

`make lint` runs Ruff and its format check across the repository, and mypy on
the package, tests, and scripts. `make test` runs pytest with a 95% coverage floor.
`make check` also runs pre-commit and isolated wheel/sdist scaffold/build checks.
The [CI workflow](workflows/ci.yml) runs the same complete gate on Python 3.12,
3.13, and 3.14. Development extras include all required tools; the complete gate
requires no manual preview or approval.

For behavior changes, preserve relevant parser, renderer, URL/security, and
temporary-directory integration regressions. For prose-only changes, check the
changed Markdown with `mdformat --check` and use `git diff --check`. Setup,
formatting, site generation, and serving are separate from check-only validation.
