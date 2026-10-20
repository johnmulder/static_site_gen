# Changelog

## Unreleased

These changes follow the frozen, prepared `0.1.0a1` candidate and are absent from its artifacts.

- Accept a validated path prefix in `base_url`, including project-site URLs such as `https://user.github.io/repository/`, and normalize the trailing slash away.
- Prefix bundled HTML links and assets, preserve absolute feed and sitemap URLs, and serve local previews at the configured path. Requests outside the preview prefix return 404.
- Add the Jinja2 `site_url` filter for root-relative internal paths while preserving the unprefixed `post_url`, `page_url`, and `tag_url` route helpers and existing output layout.
- Keep authored Markdown, raw HTML, CSS URLs, and custom templates unchanged; authors must use correctly prefixed or working relative URLs. No CLI option or runtime dependency is added.

## 0.1.0a1

First alpha candidate for Python 3.12-3.14 on Linux and macOS. Windows is unverified. Release preparation retains a verified unpublished GitHub prerelease draft; public publication is a separate command.

- Build locally authored Markdown with YAML front matter into posts, pages, tags, paginated indexes, RSS, a sitemap, and static assets.
- Include editable Jinja2 templates in installed wheels and source archives, with a buildable sample site from `static-site-gen init`.
- Preserve Unicode and valid nested routes, encode reserved URL characters, check destination collisions, and reject unsafe content metadata while valid neighboring content builds.
- Validate extension setup and domain-root HTTP/HTTPS URLs before publication. URL-prefix hosting is unsupported.
- Stage generation before replacing previous output, attempt rollback after swap errors, and report retained backups accurately. Recovery from process or machine failure during publication is outside this alpha's guarantee.
- Write UTF-8 scaffolding and provide controlled initialization, port, bind, and shutdown diagnostics for localhost preview.
- Verify isolated installed artifacts, source-archive checks, dependency advisories, timezone-data fallback, and a retained release bundle with exact artifact hashes.

Markdown HTML and templates must be locally trusted. Script-tag removal is not full sanitization, and templates are not sandboxed. PyPI publishing, verified Windows support, URL prefixes, themes/plugins, and third-party HTML processing are deferred.
