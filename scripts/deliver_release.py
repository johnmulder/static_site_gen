"""Prepare or publish a GitHub prerelease from an unchanged verified bundle."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.parse
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release import REPOSITORY, ROOT, git, sha256, validate_bundle


class GitHubError(RuntimeError):
    """A failed GitHub request with its HTTP status when available."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class GitHub:
    """Use gh's existing authentication without exposing credentials."""

    def _call(self, args: list[str], data: bytes | None = None) -> bytes:
        for attempt in range(3):
            result = subprocess.run(args, input=data, capture_output=True)
            if result.returncode == 0:
                return result.stdout
            message = result.stderr.decode("utf-8", errors="replace")
            match = re.search(r"HTTP (\d{3})", message)
            status = int(match[1]) if match else None
            if status not in {429, 500, 502, 503, 504} or attempt == 2:
                raise GitHubError(message.strip(), status)
            time.sleep(attempt + 1)
        raise AssertionError("unreachable")

    def request(self, method: str, path: str, payload: dict | None = None) -> Any:
        args = ["gh", "api", "--method", method, path]
        data = None
        if payload is not None:
            args += ["--input", "-"]
            data = json.dumps(payload).encode("utf-8")
        return json.loads(self._call(args, data))

    def download(self, asset: dict) -> bytes:
        return self._call(
            [
                "gh",
                "api",
                "-H",
                "Accept: application/octet-stream",
                f"repos/{REPOSITORY}/releases/assets/{asset['id']}",
            ]
        )

    def upload(self, release: dict, path: Path) -> dict:
        url = release["upload_url"].split("{", 1)[0]
        url += "?name=" + urllib.parse.quote(path.name, safe="")
        result = json.loads(
            self._call(
                [
                    "gh",
                    "api",
                    "--method",
                    "POST",
                    "-H",
                    "Content-Type: application/octet-stream",
                    url,
                    "--input",
                    str(path),
                ]
            )
        )
        if not isinstance(result, dict):
            raise ValueError("GitHub did not return an uploaded release asset")
        return result


def tag_commit(client: GitHub, tag: str) -> str | None:
    """Resolve an existing lightweight or annotated tag without moving it."""
    try:
        ref = client.request(
            "GET", f"repos/{REPOSITORY}/git/ref/tags/{urllib.parse.quote(tag, safe='')}"
        )
    except GitHubError as exc:
        if exc.status == 404:
            return None
        raise
    target = ref["object"]
    for _ in range(5):
        if target["type"] == "commit":
            return str(target["sha"])
        if target["type"] != "tag":
            break
        target = client.request("GET", f"repos/{REPOSITORY}/git/tags/{target['sha']}")[
            "object"
        ]
    raise ValueError("Release tag does not resolve to a source commit")


def find_release(client: GitHub, tag: str) -> dict | None:
    """Include authenticated drafts, which are absent from public tag lookups."""
    page = 1
    while True:
        releases = client.request(
            "GET", f"repos/{REPOSITORY}/releases?per_page=100&page={page}"
        )
        matches = [release for release in releases if release["tag_name"] == tag]
        if len(matches) > 1:
            raise ValueError("Multiple releases identify the same candidate tag")
        if matches:
            return dict(matches[0])
        if len(releases) < 100:
            return None
        page += 1


def verify_assets(client: GitHub, release: dict, directory: Path) -> None:
    """Require complete remote assets with identical bytes before publication."""
    assets = client.request(
        "GET", f"repos/{REPOSITORY}/releases/{release['id']}/assets?per_page=100"
    )
    names = [asset["name"] for asset in assets]
    if len(names) != len(set(names)) or set(names) != {
        path.name for path in directory.iterdir()
    }:
        raise ValueError("GitHub release has missing, duplicate, or unexpected assets")
    for asset in assets:
        expected = directory / asset["name"]
        if asset.get("state") != "uploaded" or hashlib.sha256(
            client.download(asset)
        ).hexdigest() != sha256(expected):
            raise ValueError(
                f"Uploaded release asset differs from frozen bundle: {asset['name']}"
            )


def fetch_prepared_bundle(output_root: Path, client: GitHub | None = None) -> Path:
    """Recover the exact prepared files instead of rebuilding them for publication."""
    client = client or GitHub()
    version = str(
        tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "version"
        ]
    )
    release = find_release(client, f"v{version}")
    if release is None or not release.get("prerelease"):
        raise ValueError("No prepared alpha release exists for this package version")
    marker = re.match(
        r"<!-- static-site-gen ([0-9a-f]{40}) ([0-9a-f]{64}) -->\n",
        release.get("body", ""),
    )
    if marker is None or release.get("target_commitish") != marker[1]:
        raise ValueError("Prepared release is missing its frozen source identity")
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / version
    if destination.exists():
        raise ValueError(
            "Fetch destination already exists; preserve the existing candidate"
        )
    with tempfile.TemporaryDirectory(prefix=".fetch-", dir=output_root) as name:
        staged = Path(name)
        assets = client.request(
            "GET", f"repos/{REPOSITORY}/releases/{release['id']}/assets?per_page=100"
        )
        names = [asset["name"] for asset in assets]
        if len(names) != len(set(names)):
            raise ValueError("Prepared release has duplicate assets")
        for asset in assets:
            filename = asset["name"]
            if (
                Path(filename).name != filename
                or filename in {".", ".."}
                or asset.get("state") != "uploaded"
            ):
                raise ValueError("Prepared release has an unsafe or incomplete asset")
            (staged / filename).write_bytes(client.download(asset))
        manifest = validate_bundle(staged)
        if (
            manifest["commit"] != marker[1]
            or sha256(staged / "bundle.json") != marker[2]
            or manifest["version"] != version
        ):
            raise ValueError("Prepared release files do not match the frozen identity")
        ci_run = re.fullmatch(
            rf"https://github.com/{re.escape(REPOSITORY)}/actions/runs/([0-9]+)",
            str(manifest.get("ci_run", "")),
        )
        if ci_run is None:
            raise ValueError("Prepared candidate lacks a release acceptance workflow")
        evidence = client.request("GET", f"repos/{REPOSITORY}/actions/runs/{ci_run[1]}")
        if (
            evidence.get("conclusion") != "success"
            or evidence.get("head_sha") != manifest["commit"]
            or evidence.get("name") != "Release"
        ):
            raise ValueError(
                "Prepared candidate's release workflow did not pass for its source commit"
            )
        staged.replace(destination)
    return destination


def deliver_bundle(directory: Path, mode: str, client: GitHub | None = None) -> dict:
    """Resume a matching draft and never alter published assets or existing tags."""
    manifest = validate_bundle(directory)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    if manifest["version"] != version or manifest["commit"] != git("rev-parse", "HEAD"):
        raise ValueError(
            "Frozen release identity does not match the checked-out candidate"
        )
    if git("status", "--porcelain"):
        raise ValueError("Release delivery requires a clean source checkout")
    if mode not in {"prepare", "publish", "dry-run"}:
        raise ValueError("Unknown release delivery mode")
    if mode == "dry-run":
        return {"mode": mode, "tag": manifest["tag"], "commit": manifest["commit"]}
    client = client or GitHub()
    target = tag_commit(client, manifest["tag"])
    if target is not None and target != manifest["commit"]:
        raise ValueError("Existing release tag identifies a different source commit")
    marker = f"<!-- static-site-gen {manifest['commit']} {sha256(directory / 'bundle.json')} -->"
    release = find_release(client, manifest["tag"])
    if release is not None:
        if release.get("target_commitish") != manifest["commit"] or not release.get(
            "body", ""
        ).startswith(marker + "\n"):
            raise ValueError("Existing release belongs to a different frozen candidate")
        if not release["draft"]:
            if mode != "publish":
                raise ValueError(
                    "Candidate is already published; prepare cannot modify it"
                )
            verify_assets(client, release, directory)
            return release
    elif mode == "publish":
        raise ValueError("Publish requires an already prepared and verified draft")
    else:
        release = client.request(
            "POST",
            f"repos/{REPOSITORY}/releases",
            {
                "tag_name": manifest["tag"],
                "target_commitish": manifest["commit"],
                "name": manifest["tag"],
                "draft": True,
                "prerelease": True,
                "body": marker
                + "\n\n"
                + (directory / "release-notes.md").read_text(encoding="utf-8"),
            },
        )
    if mode == "prepare":
        assets = client.request(
            "GET", f"repos/{REPOSITORY}/releases/{release['id']}/assets?per_page=100"
        )
        names = [asset["name"] for asset in assets]
        if len(names) != len(set(names)) or not set(names).issubset(
            path.name for path in directory.iterdir()
        ):
            raise ValueError("Draft contains duplicate or unrelated assets")
        for asset in assets:
            if asset.get("state") != "uploaded" or hashlib.sha256(
                client.download(asset)
            ).hexdigest() != sha256(directory / asset["name"]):
                raise ValueError(
                    f"Existing draft asset differs from frozen bundle: {asset['name']}"
                )
        for path in sorted(directory.iterdir()):
            if path.name not in names:
                client.upload(release, path)
    verify_assets(client, release, directory)
    if mode == "publish":
        release = client.request(
            "PATCH",
            f"repos/{REPOSITORY}/releases/{release['id']}",
            {
                "draft": False,
                "prerelease": True,
                "make_latest": "false",
            },
        )
        if release.get("draft") or not release.get("prerelease"):
            raise ValueError("GitHub did not confirm prerelease publication")
        if tag_commit(client, manifest["tag"]) != manifest["commit"]:
            raise ValueError("Published tag does not match the frozen source commit")
    return release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("prepare", "publish", "dry-run", "fetch"), default="prepare"
    )
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/release")
    args = parser.parse_args()
    try:
        if args.mode == "fetch":
            bundle = fetch_prepared_bundle(args.output_dir)
            manifest = validate_bundle(bundle)
            if output := os.environ.get("GITHUB_OUTPUT"):
                with Path(output).open("a", encoding="utf-8") as stream:
                    stream.write(
                        f"commit={manifest['commit']}\nbundle={bundle.resolve()}\n"
                    )
            print(bundle)
        else:
            if args.bundle is None:
                parser.error("delivery requires --bundle")
            release = deliver_bundle(args.bundle, args.mode)
            print(json.dumps(release, sort_keys=True))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Release delivery failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
