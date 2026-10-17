# Merge completion plan

This branch replaces stale agent guidance, protects source files during builds,
and packages the templates needed by installed projects. No previous plan file
was present. Completion is determined by automated checks, with no manual
preview, review sign-off, credential setup, release, or deployment required.

## Acceptance and execution

- [x] Inspect the branch against `main`, repository contracts, and existing tests.
- [x] Preserve existing output cleanup guards and usable publication permissions.
- [x] Reject malformed metadata with diagnostics while continuing valid content.
- [x] Make the CLI preview the configured output directory and safely scaffold names.
- [x] Validate configuration types with actionable errors.
- [ ] Use canonical encoded URLs in generated links, feeds, and sitemaps.
- [ ] Generate the homepage, tags index, and empty feed without published posts.
- [ ] Correct development guidance and provide one noninteractive acceptance gate.
- [ ] Run `make check`: Ruff, formatting, mypy, pytest with at least 95% coverage,
  pre-commit, and isolated wheel and sdist scaffold/build checks. CI runs this
  same gate on Python 3.12, 3.13, and 3.14.
- [ ] Commit each major completed change with a one-line message.
- [ ] Refresh `origin/main`, integrate any changes, and repeat affected checks.
- [ ] Merge into `main`, push `main`, and delete the merged feature branch locally
  and on `origin`. Verify that the working tree is clean and branches agree.

Use temporary projects for build verification. Failed checks require a fix and
another affected check, rather than a human waiver. Git operations must stop on
conflicts or rejected pushes rather than overwrite unrelated work. Publishing a
release and deploying a site are outside this merge plan.

## Evaluation

The initial branch passed 216 tests with 95.85% coverage, Ruff, mypy, and
pre-commit. Review identified an output cleanup guard regression, restrictive
published-directory permissions, malformed metadata escaping the skip contract,
CLI preview ignoring custom output paths, malformed configuration escaping
validation, unencoded template URLs, and missing root pages for empty sites.
The work above resolves those
concrete gaps without adding speculative features.
