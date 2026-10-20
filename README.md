# Static Site Generator

A small Python static blog generator for locally authored Markdown with YAML front matter. It provides Jinja2 templates, clean URLs, tags, pagination, RSS, a sitemap, and copied static assets.

The prepared first alpha is `0.1.0a1`, for Python 3.12-3.14 on Linux and macOS. Windows is unverified. Its frozen artifacts support hosting at a domain root.

The current development checkout also supports URL prefixes such as `/blog/`. This enhancement is unreleased and is absent from the prepared `0.1.0a1` artifacts. Use the [source installation](#develop-and-validate) below for prefix support.

## Install the alpha

Release readiness creates an unpublished draft. The download below becomes available after `v0.1.0a1` is published. It requires the [GitHub CLI](https://cli.github.com/).

```bash
python -m venv .venv
source .venv/bin/activate

gh release download v0.1.0a1 --repo johnmulder/static_site_gen --pattern '*.whl'
python -m pip install ./static_site_gen-0.1.0a1-py3-none-any.whl
```

For a locally prepared candidate, install the same wheel from the retained bundle instead:

```bash
python -m pip install ./dist/release/0.1.0a1/static_site_gen-0.1.0a1-py3-none-any.whl
```

## Create, build, and preview

```bash
static-site-gen init my-blog
cd my-blog
static-site-gen build
static-site-gen serve --port 8000
# Open http://localhost:8000/; press Ctrl+C to stop.
```

`python -m static_site_gen` accepts the same commands. Scaffolding creates configuration, packaged templates, a Hello World post, an About page, and CSS. It accepts a new or empty directory and preserves existing files in occupied destinations.

Before deployment, edit `config.yaml` to set your site name, author, and public URL. Preview serves the configured output directory on localhost at the path from `base_url`. For `https://example.com/blog/`, it announces `http://localhost:8000/blog/`; requests outside `/blog/` return 404. Use `--port 0` to choose an available port; the command prints the bound URL after startup.

## Write content

Posts belong in `content/posts/*.md`; standalone pages belong in `content/pages/*.md`. Both require a nonempty title and a valid date. Dates are required in front matter; filenames do not supply a fallback.

```markdown
---
title: "My First Post"
date: 2026-10-17
tags: [python, welcome]
description: "An introduction to my blog"
slug: my-first-post
draft: false
---

# Welcome

Write your content in Markdown.
```

`tags`, `description`, `slug`, and `draft` are optional. Tags are normalized and deduplicated. A missing slug is generated from the title; Unicode and valid nested slugs are supported. Ordinary duplicate slugs receive numeric suffixes. Conflicting output routes stop publication instead of overwriting another destination.

Published posts use `/posts/<slug>/`, pages `/<slug>/`, and tag archives `/tag/<tag>/`, each backed by `index.html`. The homepage lists newest posts first, with further pages under `/page/2/`. `/tag/` lists tags; `/feed.xml` and `/sitemap.xml` provide discovery. Draft posts are excluded unless you run:

```bash
static-site-gen build --drafts
```

These routes are relative to the configured site root. With a `/blog` prefix, a post is published at `/blog/posts/<slug>/`; its output file remains `site/posts/<slug>/index.html`.

Malformed content is logged and skipped while valid files continue to build. Invalid configuration, unavailable Markdown extensions, and template setup or rendering failures return a nonzero status.

## Configuration and templates

```yaml
# Required settings
site_name: "My Blog"
base_url: "https://example.com"
author: "Author Name"

# Optional settings
timezone: "UTC"
posts_per_page: 10
output_dir: "site"
description: "My personal blog"
markdown_extensions: [codehilite, tables, toc]
```

`base_url` must be an absolute HTTP/HTTPS URL with an optional validated path prefix. A trailing slash is normalized away: `https://example.com/blog/` becomes `https://example.com/blog`. Query strings, fragments, embedded credentials, and unsafe prefix paths are rejected. A GitHub Pages project URL such as `https://user.github.io/repository/` can use the repository path as its prefix.

Nested and Unicode prefixes are supported. Prefix segments are decoded once and encoded as UTF-8 URL paths. Invalid percent escapes, empty or dot segments, encoded separators, semicolons, control characters, and surrounding segment whitespace are rejected.

```yaml
# Publish this site's contents under /blog/.
base_url: "https://example.com/blog/"
```

Use an IANA timezone such as `America/Denver`; the package includes a timezone-data fallback. `posts_per_page` must be a positive integer. Omitted Markdown extensions use the defaults shown above; `markdown_extensions: []` disables optional extensions. `keywords` can hold metadata for custom templates; bundled templates do not emit a keywords element.

Edit `templates/base.html` for shared layout, `index.html` for listings, `post.html` and `page.html` for content, and `tag.html` and `tag_index.html` for archives. RSS and sitemap templates are also editable. Files under `static/` are copied to the output's `static/` directory.

Bundled HTML templates apply the prefix to internal links and assets. In custom templates, the `site_url` filter converts an unprefixed root-relative internal path to its public path:

```jinja
<a href="{{ '/' | site_url }}">Home</a>
<a href="{{ '/posts/hello-world/' | site_url }}">Hello World</a>
```

For `/blog`, these links become `/blog/` and `/blog/posts/hello-world/`. The existing `post_url`, `page_url`, and `tag_url` filters still return unprefixed routes; apply `site_url` once to their results when rendering HTML links. RSS and sitemap templates combine `base_url` with those routes to produce absolute URLs.

Authored Markdown links, raw HTML, CSS URLs, and custom templates are not automatically rewritten. Use URLs with the correct prefix or relative URLs that resolve from each published page. Update existing custom templates to use `site_url` where needed.

Markdown and templates must be locally trusted. Converted Markdown bodies allow HTML. Script-tag removal provides limited protection and is not a full HTML sanitizer; templates are not sandboxed. Metadata is escaped by Jinja2.

## Build output and deployment

The default output is `site/`. `output_dir` must select a dedicated directory inside the project, outside content, templates, assets, configuration, Git metadata, and package source. Resolved symlink targets are checked. Cleanup guards also reject output containing shell configuration files or `Desktop`/`Documents` directories.

A build renders into a sibling temporary directory, then replaces the previous output after generation succeeds. Ordinary configuration, rendering, and write failures preserve the previous site. Swap failures attempt restoration and report a retained backup if restoration fails. Failure to remove an old backup after a successful publication produces a warning. This is not a guarantee of recovery without intervention after process or machine failure during publication.

Deploy the generated directory's contents at the configured public path. For `https://example.com/blog`, the host must mount those contents at `/blog/`; the generator writes `site/index.html` and `site/posts/`, without adding a `site/blog/` directory. Domain-root deployments mount the same contents at `/`. Configure the host's publishing directory and path explicitly; pushing a `site/` directory alone does not configure hosting. The preview server is for local development.

## Develop and validate

```bash
git clone https://github.com/johnmulder/static_site_gen.git
cd static_site_gen
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make check
```

`make check` runs lint, formatting, types, tests with at least 95% coverage, pre-commit hooks, and isolated wheel/sdist installation checks. Each artifact builds sites at the domain root and under simple, nested, and Unicode prefixes. Checks resolve local HTML/RSS/sitemap links and request generated pages, assets, XML URLs, and redirects through the actual preview server. CI covers Python 3.12, 3.13, and 3.14 on Linux, with a macOS smoke check. Network access is needed to install dependencies and initialize hooks.

`make release-check` additionally verifies the clean release candidate and retains the checked wheel, source archive, checksums, notes, dependency audit, and acceptance evidence in `dist/release/0.1.0a1/`. Readiness validates an unpublished GitHub prerelease draft. It does not publish publicly.

The existing `0.1.0a1` bundle remains frozen at its verified source commit. Development prefix support leaves that bundle, its tag, and its draft assets unchanged. Delivery commands below address the prepared candidate; later development requires a separate release candidate.

```bash
# Validate without release writes.
gh workflow run release.yml -f mode=dry-run

# Prepare and verify the unpublished draft and its assets.
gh workflow run release.yml -f mode=prepare

# Separate public publication of the already verified candidate.
gh workflow run release.yml -f mode=publish
```

See [DEVELOPMENT.md](DEVELOPMENT.md), [CHANGELOG.md](CHANGELOG.md), and [RELEASE_PLAN.md](RELEASE_PLAN.md) for development, alpha notes, and acceptance details.
