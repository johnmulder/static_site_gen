# Static Site Generator

A small Python static blog generator for locally authored Markdown with YAML front matter. It provides Jinja2 templates, clean URLs, tags, pagination, RSS, a sitemap, and copied static assets.

The first alpha is `0.1.0a1`, for Python 3.12-3.14 on Linux and macOS. Windows is unverified. This alpha supports hosting at a domain root; URL prefixes such as `/blog/` are unsupported.

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

Before deployment, edit `config.yaml` to set your site name, author, and public root URL. Preview serves the configured output directory on localhost. Use `--port 0` to choose an available port; the command prints the bound URL after startup.

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

`base_url` must be an absolute HTTP/HTTPS domain-root URL. A trailing slash is normalized away. Paths other than `/`, query strings, fragments, and embedded credentials are rejected. GitHub Pages project URLs such as `https://user.github.io/repository/` are unsupported; use a domain-root deployment or a custom domain.

Use an IANA timezone such as `America/Denver`; the package includes a timezone-data fallback. `posts_per_page` must be a positive integer. Omitted Markdown extensions use the defaults shown above; `markdown_extensions: []` disables optional extensions. `keywords` can hold metadata for custom templates; bundled templates do not emit a keywords element.

Edit `templates/base.html` for shared layout, `index.html` for listings, `post.html` and `page.html` for content, and `tag.html` and `tag_index.html` for archives. RSS and sitemap templates are also editable. Files under `static/` are copied to the output's `static/` directory.

Markdown and templates must be locally trusted. Converted Markdown bodies allow HTML. Script-tag removal provides limited protection and is not a full HTML sanitizer; templates are not sandboxed. Metadata is escaped by Jinja2.

## Build output and deployment

The default output is `site/`. `output_dir` must select a dedicated directory inside the project, outside content, templates, assets, configuration, Git metadata, and package source. Resolved symlink targets are checked. Cleanup guards also reject output containing shell configuration files or `Desktop`/`Documents` directories.

A build renders into a sibling temporary directory, then replaces the previous output after generation succeeds. Ordinary configuration, rendering, and write failures preserve the previous site. Swap failures attempt restoration and report a retained backup if restoration fails. Failure to remove an old backup after a successful publication produces a warning. This is not a guarantee of recovery without intervention after process or machine failure during publication.

Deploy the generated directory's contents to the root of a static host. Configure the host's publishing directory explicitly; pushing a `site/` directory alone does not configure hosting. The preview server is for local development.

## Develop and validate

```bash
git clone https://github.com/johnmulder/static_site_gen.git
cd static_site_gen
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make check
```

`make check` runs lint, formatting, types, tests with at least 95% coverage, pre-commit hooks, and isolated wheel/sdist installation checks. CI covers Python 3.12, 3.13, and 3.14 on Linux, with a macOS smoke check. Network access is needed to install dependencies and initialize hooks.

`make release-check` additionally verifies the clean release candidate and retains the checked wheel, source archive, checksums, notes, dependency audit, and acceptance evidence in `dist/release/0.1.0a1/`. Readiness validates an unpublished GitHub prerelease draft. It does not publish publicly.

```bash
# Validate without release writes.
gh workflow run release.yml -f mode=dry-run

# Prepare and verify the unpublished draft and its assets.
gh workflow run release.yml -f mode=prepare

# Separate public publication of the already verified candidate.
gh workflow run release.yml -f mode=publish
```

See [DEVELOPMENT.md](DEVELOPMENT.md), [CHANGELOG.md](CHANGELOG.md), and [RELEASE_PLAN.md](RELEASE_PLAN.md) for development, alpha notes, and acceptance details.
