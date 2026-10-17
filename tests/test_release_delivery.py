"""Verify frozen release identity and observable, resumable delivery behavior."""

import copy
import hashlib
import json
import subprocess
import sys
from unittest.mock import Mock
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from scripts import deliver_release as delivery
from scripts import release

COMMIT = "1" * 40
VERSION = "0.1.0a1"
TAG = f"v{VERSION}"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_bundle(directory, manifest):
    """Freeze synthetic evidence using the same documented on-disk format."""
    manifest["files"] = {
        path.name: digest(path)
        for path in sorted(directory.iterdir())
        if path.name not in {"bundle.json", "SHA256SUMS"}
    }
    (directory / "bundle.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    sums = dict(manifest["files"])
    sums["bundle.json"] = digest(directory / "bundle.json")
    (directory / "SHA256SUMS").write_text(
        "".join(f"{value}  {name}\n" for name, value in sorted(sums.items())),
        encoding="utf-8",
    )


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    """A self-contained candidate needs no Git checkout, build, or network."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        f'[project]\nversion = "{VERSION}"\n', encoding="utf-8"
    )
    directory = tmp_path / "release" / VERSION
    directory.mkdir(parents=True)
    (directory / f"static_site_gen-{VERSION}-py3-none-any.whl").write_bytes(
        b"Synthetic checked wheel\n"
    )
    (directory / f"static_site_gen-{VERSION}.tar.gz").write_bytes(
        b"Synthetic checked source archive\n"
    )
    (directory / "release-notes.md").write_text(
        "# First alpha\n\nVerified candidate.\n", encoding="utf-8"
    )
    dependencies = [
        ("Markdown", "3.8.1"),
        ("Jinja2", "3.1.6"),
        ("MarkupSafe", "3.0.3"),
        ("PyYAML", "6.0.3"),
        ("tzdata", "2025.2"),
    ]
    for label in ("current", "minimum"):
        (directory / f"runtime-{label}.txt").write_text(
            "".join(f"{name}=={version}\n" for name, version in dependencies),
            encoding="utf-8",
        )
        (directory / f"audit-{label}.json").write_text(
            json.dumps(
                {
                    "dependencies": [
                        {"name": name, "version": version, "vulns": []}
                        for name, version in dependencies
                    ],
                    "fixes": [],
                }
            ),
            encoding="utf-8",
        )
    manifest = {
        "schema": 1,
        "version": VERSION,
        "tag": TAG,
        "commit": COMMIT,
        "repository": "johnmulder/static_site_gen",
        "python": "3.14.8",
        "ci_run": "https://github.com/johnmulder/static_site_gen/actions/runs/123",
        "checks": {
            name: "passed"
            for name in (
                "lint",
                "types",
                "tests_coverage_95",
                "hooks",
                "metadata",
                "wheel_install",
                "sdist_install",
                "sdist_source_tests",
                "runtime_current",
                "runtime_minimum",
            )
        },
    }
    refresh_bundle(directory, manifest)

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return COMMIT
        if args == ("status", "--porcelain"):
            return ""
        raise AssertionError(f"Unexpected Git operation: {args}")

    monkeypatch.setattr(delivery, "ROOT", source)
    monkeypatch.setattr(delivery, "git", git)
    monkeypatch.setattr(release, "ROOT", source)
    monkeypatch.setattr(release, "git", git)
    return directory, manifest, source


class FakeGitHub(delivery.GitHub):
    """An in-memory service records remote writes and preserves asset identity."""

    def __init__(self):
        self.tags = {}
        self.releases = []
        self.assets = {}
        self.contents = {}
        self.mutations = []
        self.upload_attempts = []
        self.fail_upload = None
        self.workflow_runs = {
            "123": {
                "name": "Release",
                "conclusion": "success",
                "head_sha": COMMIT,
                "path": ".github/workflows/release.yml",
                "event": "workflow_dispatch",
                "status": "completed",
            }
        }

    def request(self, method, path, payload=None):
        parsed = urlsplit(path)
        endpoint = parsed.path.removeprefix(f"repos/{release.REPOSITORY}/")
        if method == "GET" and endpoint.startswith("actions/runs/"):
            identity = endpoint.removeprefix("actions/runs/")
            if identity not in self.workflow_runs:
                raise delivery.GitHubError("Not Found", 404)
            return copy.deepcopy(self.workflow_runs[identity])
        if method == "GET" and endpoint.startswith("git/ref/tags/"):
            tag = unquote(endpoint.removeprefix("git/ref/tags/"))
            if tag not in self.tags:
                raise delivery.GitHubError("Not Found", 404)
            return {"object": {"type": "commit", "sha": self.tags[tag]}}
        if method == "GET" and endpoint == "releases":
            page = int(parse_qs(parsed.query).get("page", ["1"])[0])
            return copy.deepcopy(self.releases[(page - 1) * 100 : page * 100])
        if method == "POST" and endpoint == "releases":
            created = {
                **payload,
                "id": len(self.releases) + 1,
                "upload_url": "https://uploads.invalid/assets{?name,label}",
            }
            self.releases.append(created)
            self.assets[created["id"]] = []
            self.mutations.append(("create", copy.deepcopy(payload)))
            return copy.deepcopy(created)
        if endpoint.startswith("releases/"):
            segments = endpoint.split("/")
            identity = int(segments[1])
            item = next(item for item in self.releases if item["id"] == identity)
            if method == "GET" and segments[2:] == ["assets"]:
                return copy.deepcopy(self.assets[identity])
            if method == "PATCH" and len(segments) == 2:
                item.update(payload)
                if not item["draft"]:
                    self.tags[item["tag_name"]] = item["target_commitish"]
                self.mutations.append(("update", copy.deepcopy(payload)))
                return copy.deepcopy(item)
        raise AssertionError(f"Unexpected remote operation: {method} {path}")

    def upload(self, item, path):
        self.upload_attempts.append(path.name)
        if path.name == self.fail_upload:
            self.fail_upload = None
            raise delivery.GitHubError("Temporary upload service failure", 503)
        assert item["draft"], "Published assets must never be overwritten"
        existing_names = {asset["name"] for asset in self.assets[item["id"]]}
        assert path.name not in existing_names, "An existing asset cannot be replaced"
        asset = {
            "id": len(self.contents) + 1,
            "name": path.name,
            "state": "uploaded",
        }
        self.assets[item["id"]].append(asset)
        self.contents[asset["id"]] = path.read_bytes()
        self.mutations.append(("upload", path.name))
        return copy.deepcopy(asset)

    def download(self, asset):
        return self.contents[asset["id"]]


def test_dry_run_validates_without_constructing_a_network_client(
    candidate, monkeypatch
):
    directory, _, _ = candidate
    constructor = Mock(side_effect=AssertionError("Dry-run must not access GitHub"))
    monkeypatch.setattr(delivery, "GitHub", constructor)

    result = delivery.deliver_bundle(directory, "dry-run")

    assert result == {"mode": "dry-run", "tag": TAG, "commit": COMMIT}
    constructor.assert_not_called()


def test_prepare_and_repeat_preserve_draft_and_exact_asset_bytes(candidate):
    directory, _, _ = candidate
    client = FakeGitHub()

    first = delivery.deliver_bundle(directory, "prepare", client)
    before = copy.deepcopy(client.mutations)
    asset_ids = [asset["id"] for asset in client.assets[first["id"]]]
    repeated = delivery.deliver_bundle(directory, "prepare", client)

    assert first == repeated
    assert first["draft"] is True
    assert first["prerelease"] is True
    assert first["target_commitish"] == COMMIT
    assert client.mutations == before
    assert client.tags == {}
    assert [asset["id"] for asset in client.assets[first["id"]]] == asset_ids
    assert {asset["name"] for asset in client.assets[first["id"]]} == {
        path.name for path in directory.iterdir()
    }
    for asset in client.assets[first["id"]]:
        assert client.download(asset) == (directory / asset["name"]).read_bytes()


def test_partial_upload_resumes_without_replacing_identical_assets(candidate):
    directory, _, _ = candidate
    client = FakeGitHub()
    names = sorted(path.name for path in directory.iterdir())
    client.fail_upload = names[2]

    with pytest.raises(delivery.GitHubError, match="Temporary upload"):
        delivery.deliver_bundle(directory, "prepare", client)
    retained = copy.deepcopy(client.assets[1])
    assert len(retained) == 2

    delivery.deliver_bundle(directory, "prepare", client)

    assert len(client.releases) == 1
    assert client.releases[0]["draft"] is True
    assert client.assets[1][:2] == retained
    assert all(client.upload_attempts.count(asset["name"]) == 1 for asset in retained)
    assert {asset["name"] for asset in client.assets[1]} == set(names)


@pytest.mark.parametrize("mismatch", ["tag", "manifest", "source"])
def test_existing_candidate_mismatch_refuses_all_remote_mutations(candidate, mismatch):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    if mismatch == "tag":
        client.tags[TAG] = "2" * 40
    elif mismatch == "manifest":
        client.releases[0]["body"] = "A different frozen bundle\n"
    else:
        client.releases[0]["target_commitish"] = "2" * 40
    before = copy.deepcopy(client.mutations)

    with pytest.raises(ValueError, match="different"):
        delivery.deliver_bundle(directory, "prepare", client)

    assert client.mutations == before
    assert client.releases[0]["draft"] is True


@pytest.mark.parametrize("mismatch", ["hash", "unexpected", "duplicate", "state"])
def test_bad_remote_assets_cannot_be_replaced_or_published(candidate, mismatch):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    asset = client.assets[1][0]
    if mismatch == "hash":
        client.contents[asset["id"]] = b"Corrupted remote bytes"
    elif mismatch == "unexpected":
        asset["name"] = "unrelated.txt"
    elif mismatch == "duplicate":
        client.assets[1].append(dict(asset))
    else:
        asset["state"] = "starter"
    before = copy.deepcopy(client.mutations)

    with pytest.raises(ValueError):
        delivery.deliver_bundle(directory, "publish", client)

    assert client.mutations == before
    assert client.releases[0]["draft"] is True


def test_publish_requires_a_complete_verified_draft(candidate):
    directory, _, _ = candidate
    client = FakeGitHub()
    with pytest.raises(ValueError, match="prepared.*draft"):
        delivery.deliver_bundle(directory, "publish", client)
    assert client.mutations == []

    delivery.deliver_bundle(directory, "prepare", client)
    client.assets[1].pop()
    before = copy.deepcopy(client.mutations)
    with pytest.raises(ValueError, match="missing|complete|prepared|verified"):
        delivery.deliver_bundle(directory, "publish", client)
    assert client.mutations == before
    assert client.releases[0]["draft"] is True


def test_publish_uses_frozen_source_and_keeps_existing_published_assets(candidate):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    assets = copy.deepcopy(client.assets)
    contents = dict(client.contents)
    uploads = list(client.upload_attempts)

    published = delivery.deliver_bundle(directory, "publish", client)

    assert published["draft"] is False
    assert published["prerelease"] is True
    assert published["make_latest"] == "false"
    assert client.tags[TAG] == COMMIT
    assert client.assets == assets
    assert client.contents == contents
    assert client.upload_attempts == uploads
    after_publish = copy.deepcopy(client.mutations)
    assert delivery.deliver_bundle(directory, "publish", client) == published
    with pytest.raises(ValueError, match="already published"):
        delivery.deliver_bundle(directory, "prepare", client)
    assert client.mutations == after_publish


@pytest.mark.parametrize("change", ["artifact", "checksums", "manifest", "audit"])
def test_altered_bundle_refuses_delivery_before_client_creation(
    candidate, monkeypatch, change
):
    directory, manifest, _ = candidate
    if change == "artifact":
        next(directory.glob("*.whl")).write_bytes(b"Changed wheel")
    elif change == "checksums":
        (directory / "SHA256SUMS").write_text("Wrong checksum\n", encoding="utf-8")
    elif change == "manifest":
        manifest["commit"] = "2" * 40
        refresh_bundle(directory, manifest)
    else:
        audit = directory / "audit-current.json"
        audit.write_text(
            json.dumps(
                {"dependencies": [{"name": "Markdown", "vulns": ["GHSA-test"]}]}
            ),
            encoding="utf-8",
        )
        refresh_bundle(directory, manifest)
    constructor = Mock(side_effect=AssertionError("Invalid bundles must stay local"))
    monkeypatch.setattr(delivery, "GitHub", constructor)

    with pytest.raises(ValueError):
        delivery.deliver_bundle(directory, "prepare")

    constructor.assert_not_called()


@pytest.mark.parametrize("change", ["version", "commit", "dirty"])
def test_delivery_requires_exact_clean_checked_out_candidate(
    candidate, monkeypatch, change
):
    directory, _, source = candidate
    if change == "version":
        (source / "pyproject.toml").write_text(
            '[project]\nversion = "0.1.0a2"\n', encoding="utf-8"
        )
    elif change == "commit":
        monkeypatch.setattr(delivery, "git", lambda *args: "2" * 40)
    else:
        monkeypatch.setattr(
            delivery,
            "git",
            lambda *args: COMMIT if args == ("rev-parse", "HEAD") else " M changed.py",
        )
    constructor = Mock(side_effect=AssertionError("Source mismatch must stay local"))
    monkeypatch.setattr(delivery, "GitHub", constructor)

    with pytest.raises(ValueError, match="identity|clean"):
        delivery.deliver_bundle(directory, "prepare")

    constructor.assert_not_called()


def test_missing_required_acceptance_evidence_is_rejected(candidate):
    directory, manifest, _ = candidate
    del manifest["checks"]["tests_coverage_95"]
    refresh_bundle(directory, manifest)

    with pytest.raises(ValueError, match="acceptance"):
        release.validate_bundle(directory)


def test_missing_frozen_runtime_requirements_is_rejected(candidate):
    directory, manifest, _ = candidate
    (directory / "runtime-minimum.txt").unlink()
    refresh_bundle(directory, manifest)

    with pytest.raises(ValueError, match="runtime|evidence"):
        release.validate_bundle(directory)


@pytest.mark.parametrize("change", ["version", "tag", "wheel_name", "extra_check"])
def test_bundle_requires_matching_alpha_identity_and_exact_acceptance(
    candidate, change
):
    directory, manifest, _ = candidate
    if change == "version":
        manifest["version"] = "0.1.0rc1"
        manifest["tag"] = "v0.1.0rc1"
    elif change == "tag":
        manifest["tag"] = "v0.1.0a2"
    elif change == "wheel_name":
        wheel = next(directory.glob("*.whl"))
        wheel.rename(directory / "static_site_gen-0.1.0a2-py3-none-any.whl")
    else:
        manifest["checks"]["invented_check"] = "passed"
    refresh_bundle(directory, manifest)

    with pytest.raises(ValueError):
        release.validate_bundle(directory)


def test_reusing_a_verified_bundle_does_not_build_again(candidate, monkeypatch):
    directory, _, _ = candidate
    commands = Mock(side_effect=AssertionError("Frozen artifacts must not be rebuilt"))
    monkeypatch.setattr(release, "run", commands)

    assert release.prepare_bundle(directory.parent) == directory

    commands.assert_not_called()


def test_a_different_source_cannot_overwrite_a_frozen_bundle(candidate, monkeypatch):
    directory, _, _ = candidate
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    monkeypatch.setattr(
        release,
        "git",
        lambda *args: "2" * 40 if args == ("rev-parse", "HEAD") else "",
    )

    with pytest.raises(ValueError, match="another candidate"):
        release.prepare_bundle(directory.parent)

    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before


def test_published_asset_corruption_cannot_be_repaired_in_place(candidate):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    delivery.deliver_bundle(directory, "publish", client)
    client.contents[client.assets[1][0]["id"]] = b"Altered published asset"
    before = copy.deepcopy(client.mutations)

    with pytest.raises(ValueError, match="differs"):
        delivery.deliver_bundle(directory, "publish", client)

    assert client.mutations == before
    assert client.releases[0]["draft"] is False


def test_fetch_recovers_identical_prepared_bytes_without_remote_writes(
    candidate, tmp_path
):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    before = copy.deepcopy(client.mutations)

    fetched = delivery.fetch_prepared_bundle(tmp_path / "downloaded", client)

    assert fetched.name == VERSION
    assert {path.name: path.read_bytes() for path in fetched.iterdir()} == {
        path.name: path.read_bytes() for path in directory.iterdir()
    }
    assert client.mutations == before
    assert client.releases[0]["draft"] is True


@pytest.mark.parametrize(
    "problem", ["missing_run", "failed_run", "wrong_commit", "wrong_workflow"]
)
def test_fetch_requires_passing_release_workflow_for_exact_source(
    candidate, tmp_path, problem
):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    if problem == "missing_run":
        client.workflow_runs.clear()
    elif problem == "failed_run":
        client.workflow_runs["123"]["conclusion"] = "failure"
    elif problem == "wrong_commit":
        client.workflow_runs["123"]["head_sha"] = "2" * 40
    else:
        client.workflow_runs["123"]["name"] = "Unrelated workflow"
    before = copy.deepcopy(client.mutations)
    output = tmp_path / "downloaded"

    with pytest.raises((ValueError, delivery.GitHubError)):
        delivery.fetch_prepared_bundle(output, client)

    assert not (output / VERSION).exists()
    assert list(output.iterdir()) == []
    assert client.mutations == before


@pytest.mark.parametrize(
    "ci_run", [None, "https://github.com/other/repo/actions/runs/123"]
)
def test_fetch_rejects_missing_or_foreign_workflow_evidence(
    candidate, tmp_path, ci_run
):
    directory, manifest, _ = candidate
    manifest["ci_run"] = ci_run
    refresh_bundle(directory, manifest)
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    before = copy.deepcopy(client.mutations)

    with pytest.raises(ValueError, match="acceptance workflow"):
        delivery.fetch_prepared_bundle(tmp_path / "downloaded", client)

    assert client.mutations == before
    assert not (tmp_path / "downloaded" / VERSION).exists()


@pytest.mark.parametrize(
    "problem", ["corrupt", "missing", "unsafe", "marker", "source"]
)
def test_fetch_rejects_incomplete_or_changed_draft_without_remote_mutations(
    candidate, tmp_path, problem
):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    if problem == "corrupt":
        client.contents[client.assets[1][0]["id"]] = b"Changed remote bytes"
    elif problem == "missing":
        client.assets[1].pop()
    elif problem == "unsafe":
        client.assets[1][0]["name"] = "../escaped.txt"
    elif problem == "marker":
        client.releases[0]["body"] = client.releases[0]["body"].replace(
            digest(directory / "bundle.json"), "0" * 64
        )
    else:
        client.releases[0]["target_commitish"] = "2" * 40
    before = copy.deepcopy(client.mutations)

    with pytest.raises(ValueError):
        delivery.fetch_prepared_bundle(tmp_path / "downloaded", client)

    assert client.mutations == before
    assert not (tmp_path / "downloaded" / VERSION).exists()
    assert not (tmp_path / "downloaded" / "escaped.txt").exists()


def test_fetch_preserves_an_existing_local_candidate(candidate, tmp_path):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    before = copy.deepcopy(client.mutations)
    output = tmp_path / "downloaded"
    previous = output / VERSION / "sentinel.txt"
    previous.parent.mkdir(parents=True)
    previous.write_text("Existing candidate", encoding="utf-8")

    with pytest.raises(ValueError, match="destination already exists"):
        delivery.fetch_prepared_bundle(output, client)

    assert previous.read_text(encoding="utf-8") == "Existing candidate"
    assert client.mutations == before


def test_fetch_cli_exports_frozen_commit_and_bundle_for_later_checkout(
    candidate, tmp_path, monkeypatch
):
    directory, _, _ = candidate
    client = FakeGitHub()
    delivery.deliver_bundle(directory, "prepare", client)
    before = copy.deepcopy(client.mutations)
    output = tmp_path / "downloaded"
    github_output = tmp_path / "job-output.txt"
    monkeypatch.setattr(delivery, "GitHub", lambda: client)
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setattr(
        sys,
        "argv",
        ["deliver_release.py", "--mode", "fetch", "--output-dir", str(output)],
    )

    assert delivery.main() == 0

    assert github_output.read_text(encoding="utf-8").splitlines() == [
        f"commit={COMMIT}",
        f"bundle={(output / VERSION).resolve()}",
    ]
    assert client.mutations == before


def test_github_retries_transient_http_error_then_returns_response(monkeypatch):
    transport = Mock(
        side_effect=[
            subprocess.CompletedProcess([], 1, b"", b"gh: unavailable (HTTP 503)"),
            subprocess.CompletedProcess([], 0, b'{"id": 17}', b""),
        ]
    )
    pause = Mock()
    monkeypatch.setattr(delivery.subprocess, "run", transport)
    monkeypatch.setattr(delivery.time, "sleep", pause)

    assert delivery.GitHub().request("GET", "test-endpoint") == {"id": 17}
    assert transport.call_count == 2
    pause.assert_called_once_with(1)


def test_github_does_not_retry_authorization_failure(monkeypatch):
    transport = Mock(
        return_value=subprocess.CompletedProcess(
            [], 1, b"", b"gh: forbidden (HTTP 403)"
        )
    )
    pause = Mock()
    monkeypatch.setattr(delivery.subprocess, "run", transport)
    monkeypatch.setattr(delivery.time, "sleep", pause)

    with pytest.raises(delivery.GitHubError) as failure:
        delivery.GitHub().request("GET", "test-endpoint")

    assert failure.value.status == 403
    transport.assert_called_once()
    pause.assert_not_called()


def test_github_stops_after_bounded_transient_retries(monkeypatch):
    transport = Mock(
        return_value=subprocess.CompletedProcess(
            [], 1, b"", b"gh: unavailable (HTTP 503)"
        )
    )
    pause = Mock()
    monkeypatch.setattr(delivery.subprocess, "run", transport)
    monkeypatch.setattr(delivery.time, "sleep", pause)

    with pytest.raises(delivery.GitHubError) as failure:
        delivery.GitHub().request("GET", "test-endpoint")

    assert failure.value.status == 503
    assert transport.call_count == 3
    assert [call.args[0] for call in pause.call_args_list] == [1, 2]
