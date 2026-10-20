# Development Guide

## Development checkout and prepared alpha

The prepared first alpha is `0.1.0a1`, for Python 3.12-3.14 on Linux and macOS. Its frozen artifacts support domain-root hosting. The current development checkout adds URL-prefix hosting; this unreleased enhancement does not alter the prepared candidate, tag, or assets. Windows support and PyPI publication remain deferred. Runtime content and templates are locally trusted; Markdown HTML is not fully sanitized and templates are not sandboxed.

The public CLI is `static-site-gen` or `python -m static_site_gen`, with `init`, `build`, and `serve`. Public package version APIs and distribution metadata use the version in `pyproject.toml`.

## Architecture

- `static_site_gen/generator/core.py`: configuration, discovery, route planning, and build orchestration.
- `static_site_gen/generator/parser.py`: YAML front matter, metadata validation, dates, slugs, and Markdown conversion.
- `static_site_gen/generator/renderer.py`: Jinja2 rendering and shared route filters.
- `static_site_gen/generator/output.py`: paths, publication, asset copying, sorting, and pagination.
- `static_site_gen/cli.py`: command arguments, scaffolding from packaged templates, build diagnostics, and localhost preview.
- `static_site_gen/resources/templates/`: templates included in installed distributions.
- `templates/`: templates used by the repository's sample site.
- `scripts/`: package and release verification.

A build validates configuration and extension setup, discovers content in stable order, parses metadata, filters draft posts, checks output destinations, renders content and indexes, generates XML, and copies static assets. Generation uses a sibling staging directory. Publication replaces the configured output after generation succeeds.

## Setup

```bash
git clone https://github.com/johnmulder/static_site_gen.git
cd static_site_gen
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Development dependency installation, initial pre-commit environments, isolated package installations, and dependency audits need network access. Tests and preview checks use temporary projects and bounded localhost requests; no manual browser inspection is required.

## Acceptance gates

```bash
# Complete checkout gate.
make check

# Individual checks when investigating a failure.
make lint
make test
make check-package

# Prepare and retain a verified release bundle from a clean commit.
make release-check
```

`make check` runs Ruff lint and formatting checks, mypy, pytest with a 95% coverage floor, pre-commit hooks, and fresh installed wheel/source-archive checks. Ordinary package checks use temporary output. Source-archive verification runs outside the checkout with its own included test fixtures and templates; its non-Git checks do not recursively invoke archive verification.

`make release-check` validates the exact candidate artifacts and retains them under `dist/release/0.1.0a1/`, together with SHA-256 hashes, source commit, release notes, resolved runtime dependencies, advisory results, and acceptance evidence. Publication consumes those checked files without rebuilding them. A failed gate remains a failure; no manual waiver or browser approval is part of readiness.

CI runs the checkout gates on Linux with Python 3.12, 3.13, and 3.14 and includes a macOS smoke job. Release validation covers the runtime dependency floors and current resolution, source archive completeness, strict distribution metadata, isolated installed commands, and operation without system timezone data.

Useful targeted commands include:

```bash
pytest tests/test_parser.py
ruff check .
ruff format --check .
mypy static_site_gen tests scripts
mdformat --check README.md DEVELOPMENT.md CHANGELOG.md RELEASE_PLAN.md
```

Keep the packaged and sample templates consistent. Preserve meaningful parser, routing/security, publication rollback, CLI, and installed-artifact regressions. Do not run destructive builds against content or user-owned output directories during verification.

## Content and configuration

Posts and pages require a nonempty `title` and a valid `date`. Optional metadata includes string tags, boolean `draft`, string `description`, and a string `slug`. Slugs can be generated from titles and support Unicode and valid nested routes. Normalized tags are unique within a post. Invalid content is logged with its filename and skipped; no filename-date fallback exists.

Configuration requires nonempty `site_name`, `base_url`, and `author`. Supported base URLs are absolute HTTP/HTTPS URLs with an optional validated path prefix. A trailing slash is normalized away, so `https://example.com/blog/` becomes `https://example.com/blog`. Query strings, fragments, credentials, malformed hosts, and unsafe prefix paths are rejected. IANA timezone names are validated and timezone-aware dates are preserved. `posts_per_page` is a positive integer, excluding booleans.

```yaml
site_name: "My Blog"
base_url: "https://example.com"
author: "Author Name"
timezone: "UTC"
posts_per_page: 10
output_dir: "site"
description: "Site description"
markdown_extensions: [codehilite, tables, toc]
```

An omitted `markdown_extensions` setting uses the defaults shown above. An explicit empty list disables optional extensions. Invalid or unavailable extensions stop setup before any output is published. `keywords` is available to custom templates; bundled templates do not emit it.

Routes are `/posts/<slug>/`, `/<slug>/`, `/tag/<tag>/`, and `/page/<number>/`, backed by `index.html`. The homepage, tag index, RSS, sitemap, and static assets have reserved destinations. Ordinary duplicate content slugs receive deterministic suffixes; conflicts with other planned destinations fail before publication with source diagnostics.

Prefix hosting changes public URLs, not these output routes or directory layouts. A site with `base_url: https://example.com/blog` still writes `site/index.html`, `site/posts/`, and `site/static/`; its host mounts the output contents at `/blog/`.

The Jinja2 `site_url` filter adds the configured prefix to an unprefixed root-relative internal path. `post_url`, `page_url`, and `tag_url` retain their existing unprefixed route behavior. Chain each route through `site_url` once for HTML links; combine `base_url` and the unprefixed route for absolute feed and sitemap URLs. Keep packaged and sample templates consistent.

The generator does not rewrite authored Markdown links, raw HTML, CSS URLs, or custom templates. Authors must supply correctly prefixed URLs or relative URLs that work at the destination page. Prefix support adds no CLI option or runtime dependency.

Routing changes must preserve domain-root behavior and cover prefixed HTML links, assets, feeds, sitemaps, and installed scaffolding. Preview checks must use the configured prefix and verify that requests outside it return 404.

Installed wheel and source-archive checks build domain-root, simple-prefix, nested-prefix, and Unicode-prefix sites. They check local HTML links and absolute RSS/sitemap URLs against the configured mount, then request the generated targets through preview, including redirects and assets. Authored links are checked but never rewritten.

## Trust and failure behavior

YAML uses safe loading and Jinja2 escapes metadata. Converted Markdown bodies are marked safe in templates. Removing script tags is not a complete sanitizer and does not make third-party HTML trusted. Build only locally trusted Markdown and templates.

Output must remain inside the project and outside its input directories, configuration, Git metadata, and package source. Routing checks decoded segments and resolved path containment; publication uses the same cleanup guards as ordinary builds.

Configuration, template, rendering, and write errors return nonzero statuses. Generation failures preserve previous output. Swap failures attempt rollback; if rollback cannot complete, diagnostics identify the retained previous-site backup. Backup cleanup failure after a completed swap warns and leaves publication successful. Process death between directory renames can require recovery; publication is not crash-atomic.

`init` preserves occupied destinations, writes UTF-8, and reports filesystem failures. `serve` validates configuration and port range, binds only localhost, prints the actual bound URL including the configured prefix after startup, and handles bind errors and Ctrl+C. It mounts the output directory at that prefix and returns 404 outside it. Port zero chooses an available port.

## Alpha release workflow

[RELEASE_PLAN.md](RELEASE_PLAN.md) defines the complete noninteractive readiness criteria. The selected version is `0.1.0a1` and its tag is `v0.1.0a1`. The workflow uses the repository's automatic token; no additional publishing account or stored credential is required for GitHub Releases.

That prepared candidate is frozen at `31a163201ff24466a497af970c938f30f681dee6`. URL-prefix hosting belongs to subsequent development and is absent from its artifacts. Use `make check` for the current checkout; retain the existing bundle, tag, asset hashes, and historical acceptance evidence. A later release must use a separate candidate rather than replace the frozen `0.1.0a1` bundle.

```bash
# Read-only delivery validation; no release writes.
gh workflow run release.yml -f mode=dry-run

# Validate, retain the bundle, create/resume the unpublished prerelease draft,
# upload the exact checked assets, and verify their downloaded hashes.
gh workflow run release.yml -f mode=prepare

# Explicit public publication after validation of the frozen candidate.
gh workflow run release.yml -f mode=publish
```

Prepare is the default mode. Readiness completes with passing gates and a verified unpublished draft; implementation and readiness checks must not run publish mode. Publish validates the frozen version, source commit, tag, asset hashes, and required gates, then publishes the prepared candidate. It must not move existing tags or overwrite published assets. Repeat preparation may resume only a matching candidate; mismatches and service failures remain visible failures with retained artifacts.

Changes to runtime behavior require appropriate regression tests. Commit each major change with a one-line message, run the affected checks, then run the full gate on the clean candidate. Update [CHANGELOG.md](CHANGELOG.md) and readiness evidence before delivery; no manual version editing or human approval belongs inside an executing release gate.
