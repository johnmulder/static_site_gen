# Changelog

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
