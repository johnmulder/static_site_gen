# Release readiness plan

Evaluated on 2026-10-17 against `main` at `62fd788`; completed on 2026-10-17.

This is the historical readiness record for the frozen `0.1.0a1` candidate.
The current development checkout subsequently adds URL-prefix hosting, documented
in [README.md](README.md) and [CHANGELOG.md](CHANGELOG.md). That enhancement is
unreleased and is absent from the prepared candidate's artifacts. The domain-root
requirements and dated evidence below describe that original candidate; its
source, version, tag, and asset hashes remain unchanged.

## Verdict and completion target

The project is ready for its first alpha release. All R1-R8 work is complete,
merged into `main`, and pushed. The real release workflow prepared and verified
an unpublished `0.1.0a1` draft; an independent local download verified the same
assets, hashes, source commit, and successful workflow provenance. The merged
feature branch has been deleted locally and on `origin`.

At initial evaluation, acceptance passed 285 tests with 97.42% coverage, lint,
types, hooks, and isolated installed wheel/sdist checks.
[Baseline CI](https://github.com/johnmulder/static_site_gen/actions/runs/39075968335)
passed on Python 3.12, 3.13, and 3.14. Further isolated checks reproduced the
release blockers documented below. The completion evidence follows the plan.

The target is a first alpha, `0.1.0a1`, distributed through this repository's
GitHub Releases. No repository releases or tags existed at evaluation time.
Use `v0.1.0a1` as the eventual tag, and retain the Alpha classifier. If another
release occupies that version before execution, select the next unused alpha
number automatically before committing the candidate and update every version
reference together. Freeze version, tag, source commit, and hashes in the prepared
bundle; later collision handling must never change them during publication.

Readiness is complete when a clean commit produces a retained, verified release
bundle and delivery automation verifies an unpublished draft and its assets.
Publishing failure paths must also pass dry-run tests. Public publication is a
separate command, not a human approval gate inside this plan. The execution
request authorized implementation, commits, integration, push, and branch
cleanup. The prepared release remains unpublished, as required by R8.

Defaults remove open decisions:

- Support Python 3.12-3.14 on Linux and macOS for the first alpha. Document Windows
  as unverified and remove instructions that imply verified Windows support.
- Support hosting at a domain root. Normalize a trailing slash and reject URL
  prefixes until prefix support has its own tested implementation.
- Preserve Unicode, encoded reserved characters, and legitimate nested slugs.
- Keep locally trusted Markdown and templates as the trust boundary; do not add
  third-party HTML sanitization or a template sandbox to this release.
- Use the existing GitHub repository and automatic workflow token. PyPI account
  ownership and publishing configuration are unverified and are outside the
  required path. No new account, secret, manual browser preview, or sign-off is
  needed to complete readiness.

## Prioritized work

P0 prevents silent output corruption. P1 completes the alpha's correctness and
distribution contract. P2 makes release preparation and delivery repeatable.
Every item below is required for readiness; later enhancements are listed
separately. Each item should be a focused change with a one-line commit message.

### P0 / R1: Prevent route collisions and silent overwrites

Evidence: collision tracking in `generator/core.py` compares raw slugs separately
for posts and pages, while `generator/output.py:get_output_path` normalizes their
filesystem destinations. An isolated successful build lets a page with slug `/`
replace the homepage, `tag` replace the tags index, or `posts/existing` replace a
post. A `static` page disappears during asset copying. Slugs `a/b` and `a//b`
also target the same file.

- [x] Check canonical destinations across posts, pages, tag archives, pagination,
  homepage, feed, sitemap, and static assets before publication. Account for
  file/directory conflicts and the host filesystem's path aliases.
- [x] Reject ambiguous route segments during parsing. Keep supported nested
  routes, Unicode, and percent-encoded reserved characters. Discover files in a
  stable order so existing numeric collision suffixes remain deterministic.
- [x] A conflict between otherwise valid destinations must fail with both source
  names and the destination, preserving the prior site. Do not silently rename
  reserved routes or overwrite another item.

Done when integration regressions cover all reproduced conflicts, pagination and
asset conflicts, ordinary duplicate-slug suffixes, valid nested/Unicode routes,
and unchanged previous output after a failed build.

### P0 / R2: Validate Markdown extension setup before processing content

Evidence: `markdown_extensions: [""]` is accepted, causes every content file to
be skipped, returns success, and replaces a populated site with empty output.
A nonexistent extension module instead escapes the CLI as a traceback.

- [x] Reject empty extension names and initialize/validate configured extensions
  before processing files. Configuration/setup failures must stop the build.
- [x] Return a useful nonzero CLI result without a traceback for invalid or
  unavailable extensions; preserve previous output byte-for-byte.
- [x] Distinguish omitted extensions from an explicit empty list. Omission uses
  the documented defaults; `[]` disables optional extensions.

Done when invalid names/modules cannot produce a successful empty publication,
valid extensions still work, and omitted/empty-list behavior has regression tests.

### P1 / R3: Finish content validation and publication diagnostics

Evidence: string slugs containing dot traversal, backslashes, whitespace-only
values, or NUL, and invalid route tags, pass metadata validation and abort the
whole build later. Normalized duplicate tags duplicate archive entries. Failure
to delete an old backup returns failure after the new site is already published.

- [x] Reject unsafe/unrepresentable slug and tag values as `ParseError` with the
  filename, using the same routing rules as R1. Log and skip that content file
  while valid neighboring content builds, as the existing contract requires.
- [x] Deduplicate normalized tags while preserving order and correct post counts.
- [x] Separate completed publication from backup cleanup. If cleanup fails after
  a successful swap, return success and warn with the retained backup's path.
  Retain rollback and failure status for actual swap failures.

Done when malformed-string tests prove valid neighbors still publish, duplicate
tags count once, cleanup failure reports the actual committed state, and existing
source-protection and rollback regressions continue to pass.

### P1 / R4: Make accepted URLs and CLI behavior reliable

Evidence: `base_url: https://example.com/` creates doubled slashes in RSS.
`https://example.com/blog` is accepted but HTML links/assets point outside `/blog`
while RSS points inside it. `init` targeting an existing file raises outside its
error handler. Scaffolding a Unicode name fails under a non-UTF-8 file locale.
`serve` announces readiness before binding and exposes bind/invalid-port errors.

- [x] Normalize root HTTP/HTTPS URLs to one representation. Reject non-root paths,
  query strings, fragments, and embedded credentials with clear diagnostics.
  Keep generated HTML, RSS, sitemap, and preview URLs consistent.
- [x] Use explicit UTF-8 for all scaffold text writes. Preserve an existing file
  passed to `init` and return a controlled error.
- [x] Validate port range, handle server bind errors, and announce serving only
  after the socket is bound. Preserve normal Ctrl+C shutdown.

Done when root URLs with/without trailing slash are equivalent, unsupported URL
forms fail before publication, Unicode scaffold text builds under a non-UTF-8
text locale, and Unicode names work with the supported platforms' normal UTF-8
filesystem encoding. An unencodable filesystem name must produce a controlled
error. CLI failure cases return nonzero without tracebacks or file changes.
Use bounded local HTTP checks and mocked bind errors; no manual preview is needed.

### P1 / R5: Set a safe, portable dependency and metadata baseline

Evidence: auditing the declared runtime minimums reports advisories for
Markdown 3.7 and Jinja2 3.1.5. The tested environment's Markdown 3.9,
Jinja2 3.1.6, PyYAML 6.0.3, and MarkupSafe 3.0.3 had no reported advisories on
the evaluation date. This is a dependency-policy gap, not evidence that the
project executes untrusted templates. See the
[Markdown fix](https://github.com/Python-Markdown/markdown/releases/tag/3.8.1) and
[Jinja fix](https://jinja.palletsprojects.com/en/stable/changes/#version-3-1-6).

Without system timezone data, even default `UTC` fails because `tzdata` is not a
runtime dependency. Build output also warns about deprecated license metadata.
Version `0.1.0` is duplicated in `pyproject.toml` and both package `__init__.py`
files; author metadata contains `john@example.com`.

- [x] Raise runtime floors to at least Markdown 3.8.1 and Jinja2 3.1.6, retain
  justified upper bounds, and verify both minimum and currently resolved runtime
  dependencies. Add an advisory check of runtime dependencies and their resolved
  transitive dependencies to release validation; retain its machine-readable
  report. Do not silently suppress advisories.
- [x] Declare a maintained `tzdata` fallback and test with `PYTHONTZPATH=""` so
  ordinary installation does not require operating-system timezone setup.
- [x] Migrate to `license = "MIT"` and `license-files = ["LICENSE"]`, remove the
  deprecated license classifier, and require a backend supporting that format.
  The [packaging guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license-and-license-files)
  identifies setuptools 77.0.3 as a supported baseline.
- [x] Use `pyproject.toml` as the canonical version, preserve public version APIs
  without independent literals, and set the selected alpha version. Remove the
  placeholder author email rather than invent contact information.

Done when fresh runtime installs resolve without dependency conflicts or reported
advisories, UTC and a non-UTC zone work without OS timezone files, metadata builds
without the existing license deprecations, and every exposed/artifact version
equals the selected release version.

### P1 / R6: Make the source distribution verifiable

Evidence: a fresh build from a Git archive of `62fd788` produces installable wheel
and sdist artifacts. Both pass installed `init`/`build` checks. The sdist includes
test modules but omits `conftest.py`, fixtures, root templates, Makefile, and check
scripts. Running its three empty-site integration tests fails with missing
`sample_project` fixtures. Current `make check-package` deletes its artifacts.

- [x] Include the source files, test support/data/templates, validation scripts,
  developer targets, license, and release documentation needed to build and test
  the source archive. Exclude caches, virtual environments, generated sites, and
  previous distributions.
- [x] From an extracted sdist outside the checkout, install development
  dependencies, run its test suite and non-Git lint/type checks, and build and
  inspect a wheel. Keep this archive check nonrecursive: it must not invoke the
  outer sdist extraction check again. Git-specific pre-commit hooks remain a
  checkout check.
- [x] Check wheel/sdist metadata with `twine check --strict`, verify template and
  license contents, run `pip check`, and exercise both CLI entry points from
  isolated installed environments.
- [x] Extend installed acceptance to validate XML and local link destinations,
  pagination, drafts, empty sites, Unicode/reserved-character routes, custom
  output, and failed-rebuild preservation. Reuse existing fixtures/regressions
  rather than create a parallel testing framework.

Done when the source archive can reproduce its tests without the original
checkout, both distributions pass installed checks, and the exact checked files
can be retained for the release bundle.

### P2 / R7: Make release preparation one noninteractive gate

Depends on R1-R6. Preserve `make check` and its 95% coverage floor. Add
`make release-check` using small additions to the existing scripts and CI:

- [x] Verify a clean commit and consistent alpha version; run all existing gates
  plus R5/R6 checks. Keep the Linux Python 3.12-3.14 matrix and add a macOS smoke
  job for the supported platform and filesystem behavior.
- [x] Build the release wheel/sdist once, validate those exact files, and retain
  them with SHA-256 checksums, release notes, source commit, resolved runtime
  dependencies, audit results, and acceptance results in a versioned bundle.
  Publishing must consume this bundle without rebuilding it.
- [x] Reuse the package checker with explicit artifact paths for release checks.
  Keep ordinary `make check` temporary-output behavior, but avoid building a
  disposable pair and then independently rebuilding the release pair.
- [x] Add `CHANGELOG.md` for the selected alpha and describe supported platforms,
  root-only hosting, trusted content, failure behavior, and installation from
  GitHub assets. Replace the scaffold's `github.com/example/static-site-gen` link,
  stale configuration comments, and the generic manual release checklist.
- [x] Run the README's installation/scaffold/build/preview sequence automatically
  against installed artifacts. Check the changed Markdown with the repository's
  formatter and hooks.

Done when one command produces a complete verified bundle or a nonzero result
with useful diagnostics. No manual editing, preview, version choice, or waiver
may remain in that command's execution path. All supported CI jobs must pass for
the exact candidate commit.

### P2 / R8: Provide an automated GitHub delivery path

Depends on R7. Implement a release workflow with a default prepare mode, a dry-run
mode, and a separate explicit publish mode, all invocable through `gh workflow run`.
Do not publish during implementation of this readiness plan.

- [x] Dry-run mode performs validation without release or tag writes. Prepare mode checks
  the candidate, retains its bundle, creates or resumes its unpublished GitHub
  prerelease draft, uploads the exact verified assets, and verifies downloaded
  hashes. This exercises the actual workflow token's release/asset permissions
  without public publication. Publish mode validates the frozen candidate,
  passing gates, draft, and hashes, then publishes it automatically. Do not add
  an environment approval gate.
- [x] Use the automatic `GITHUB_TOKEN` with `contents: write` only in the release
  job; ordinary checks retain read permission. Current workflow defaults are read
  only, but no new stored credential is needed for this design. See
  [workflow authentication](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).
- [x] Run required gates in this workflow or depend on verified existing results;
  do not assume a tag created using `GITHUB_TOKEN` starts another workflow.
  GitHub documents that [token-triggered events generally do not start new runs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
- [x] Test dry-run, repeat execution, partial upload, mismatched tag/hash, and
  service-error cases. Resume the same draft only when its commit and asset
  hashes match. Never move an existing release tag or overwrite published assets.
  Use bounded retries for transient failures and preserve verified artifacts on
  failure.

Done when the real prepare workflow verifies an unpublished draft and its assets,
and automated failure-path tests prove that only verified assets can be published.
Repository write/admin access is already present; draft operations must verify the
workflow token's effective permissions using the
[release API](https://docs.github.com/en/rest/releases/releases#create-a-release).
Public publication remains unexercised until explicitly invoked and is not a
readiness requirement.

## Execution order and finish criteria

1. Complete R1 and R2 first, independently; they prevent successful corrupt output.
1. Complete R3/R4 and R5/R6 in parallel where file ownership does not overlap.
1. Complete R7, then R8. Run the full release gate and prepare workflow against
   the final candidate commit, retaining its verified unpublished draft. Resolve
   failures automatically and rerun affected
   gates; record evidence and check off each item only after it passes.
1. Commit major changes with one-line messages. Integrate against current `main`,
   resolve conflicts while preserving repository contracts, and rerun affected
   checks. Mark this plan complete only with the verified bundle and CI links.

Completion requires all R1-R8 criteria, a clean working tree, matching package and
artifact versions, an identified source commit, matching checksums, and passing
CI. Reuse established authorization and credentials; no step asks a person to
choose defaults, inspect a browser, create accounts, enter secrets, or waive a
failed check.

## Completion evidence

The frozen release source is
`31a163201ff24466a497af970c938f30f681dee6`. It was fast-forward merged into `main`
and pushed before draft preparation. This completion record is a subsequent
documentation-only change; the draft remains pinned to the verified source.

- Local `make release-check` passed: 408 tests, 97.67% package coverage, Ruff,
  formatting, mypy, every pre-commit hook, strict package metadata checks, isolated
  wheel/sdist installation, and the extracted source archive's complete suite.
- [Candidate CI](https://github.com/johnmulder/static_site_gen/actions/runs/39077693485)
  and [main CI](https://github.com/johnmulder/static_site_gen/actions/runs/39077828459)
  passed on Linux Python 3.12, 3.13, and 3.14 and macOS Python 3.14.
- [Release prepare workflow](https://github.com/johnmulder/static_site_gen/actions/runs/39077834612)
  passed its supported-platform gates, built and retained the exact distribution
  pair, validated the source archive and installed packages, audited both runtime
  resolutions, and uploaded and downloaded the draft assets with the automatic
  workflow token.
- Both retained dependency audit reports contain no reported vulnerabilities.
  Minimum resolution uses Markdown 3.8.1, Jinja2 3.1.6, PyYAML 6.0.2, and tzdata
  2025.2; current resolution uses Markdown 3.11.1, Jinja2 3.1.6, PyYAML 6.0.3,
  and tzdata 2026.5. Both include MarkupSafe 3.0.4.
- [Unpublished alpha draft](https://github.com/johnmulder/static_site_gen/releases/tag/untagged-2f3387f6a6837dea3029)
  (release ID `416123252`) has `draft: true`, `prerelease: true`, tag `v0.1.0a1`,
  the exact frozen source, and all nine assets uploaded. Public publication was
  not invoked.
- Independent `deliver_release.py --mode fetch --output-dir dist/prepared`
  succeeded, including successful original-workflow verification. A separate
  `release.py verify --bundle dist/prepared/0.1.0a1` also passed. These downloaded
  bytes are retained locally under `dist/prepared/0.1.0a1`; the original local
  candidate bundle remains under `dist/release/0.1.0a1`.
- Dry-run delivery passed. Automated delivery tests cover repeat execution,
  partial upload recovery, conflicting identities and hashes, immutable published
  assets, frozen-bundle fetching, and bounded transient-error retries.
- Major changes were committed separately with one-line messages. The merged
  `codex/alpha-release-readiness` branch was deleted locally and remotely after
  refreshing `origin` and confirming it was an ancestor of `main`.

The workflow bundle's SHA-256 identities are:

| Asset                                      | SHA-256                                                            |
| ------------------------------------------ | ------------------------------------------------------------------ |
| `bundle.json`                              | `836edf15939614c8bb4674d77aa66747c192377f5651c981237b6bdeb7b24c4e` |
| `static_site_gen-0.1.0a1-py3-none-any.whl` | `4c9609187aac8b6cf7b2d3b5a927721832528ddcc5771d74b005cab9ea27da3d` |
| `static_site_gen-0.1.0a1.tar.gz`           | `2bc90a5fc9e50a01cf8cf5d0f6ac6c5f28a23cc2765de1d6eb9c63ae1f753eda` |

`SHA256SUMS` in that bundle records all eight companion-file hashes. All R1-R8
acceptance criteria have passed without a manual waiver, credential setup, or
interactive approval step.

## Deferred beyond the first alpha

URL-prefix hosting is now available in the development checkout, after the frozen
alpha candidate. It does not change that candidate's domain-root contract or
require replacing its retained release assets.

PyPI publication, verified Windows support, third-party HTML sanitization,
themes/plugins, new deployment integrations, performance targets,
bit-for-bit reproducible builds, and recovery from process death between output
renames are separate work. They do not block this alpha contract. Current
publication preserves the previous site on ordinary rendering/write/swap errors;
the release must not claim crash-atomic publication.
