"""Prepare a retained release bundle from one clean, verified source commit."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.version import Version

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_installed_artifacts import check_artifact
from scripts.check_source_distribution import check_source_distribution

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "johnmulder/static_site_gen"
REQUIRED_CHECKS = {
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
}


def run(
    *args: str | Path, cwd: Path = ROOT, **kwargs: Any
) -> subprocess.CompletedProcess:
    """Run an argument vector without shell interpolation."""
    return subprocess.run([str(arg) for arg in args], cwd=cwd, check=True, **kwargs)


def git(*args: str) -> str:
    """Read repository state."""
    return str(run("git", *args, capture_output=True, text=True).stdout).strip()


def sha256(path: Path) -> str:
    """Hash an artifact without loading it all into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Write stable, readable release evidence."""
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_bundle(directory: Path) -> dict[str, Any]:
    """Validate the frozen identity and every byte of a complete bundle."""
    manifest_path = directory / "bundle.json"
    if manifest_path.is_symlink():
        raise ValueError("Bundle manifest must be a regular file")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise ValueError("Unsupported release bundle schema")
    version = str(manifest.get("version", ""))
    parsed_version = Version(version)
    if (
        parsed_version.pre is None
        or parsed_version.pre[0] != "a"
        or str(parsed_version) != version
        or manifest.get("tag") != f"v{version}"
    ):
        raise ValueError(
            "Release bundle must identify one matching prerelease version/tag"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("commit", ""))):
        raise ValueError("Release bundle requires an exact source commit")
    if manifest.get("repository") != REPOSITORY:
        raise ValueError("Release bundle repository does not match this project")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Release bundle is missing its artifact hashes")
    required = {
        "release-notes.md",
        "audit-current.json",
        "audit-minimum.json",
        "runtime-current.txt",
        "runtime-minimum.txt",
    }
    if not required.issubset(files):
        raise ValueError(
            "Release bundle is missing release notes or dependency audit evidence"
        )
    wheels = [name for name in files if name.endswith(".whl")]
    sdists = [name for name in files if name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Release bundle must contain exactly one wheel and one sdist")
    if (
        not wheels[0].startswith(f"static_site_gen-{version}-")
        or sdists[0] != f"static_site_gen-{version}.tar.gz"
    ):
        raise ValueError("Artifact filenames do not match the frozen package version")
    expected_names = set(files) | {"bundle.json", "SHA256SUMS"}
    if {path.name for path in directory.iterdir()} != expected_names:
        raise ValueError("Release bundle contains missing or unexpected files")
    for name, digest in files.items():
        if Path(name).name != name or name in {".", ".."}:
            raise ValueError(f"Unsafe bundle member: {name}")
        path = directory / name
        if path.is_symlink() or not path.is_file() or sha256(path) != digest:
            raise ValueError(f"Release bundle hash mismatch: {name}")
    for audit_name in ("audit-current.json", "audit-minimum.json"):
        audit = json.loads((directory / audit_name).read_text(encoding="utf-8"))
        if not isinstance(audit.get("dependencies"), list) or not audit["dependencies"]:
            raise ValueError(f"Missing dependency audit results: {audit_name}")
        if any(
            item.get("vulns") or item.get("skip_reason")
            for item in audit["dependencies"]
        ):
            raise ValueError(f"Unresolved dependency audit finding: {audit_name}")
    checks = manifest.get("checks", {})
    if (
        not isinstance(checks, dict)
        or set(checks) != REQUIRED_CHECKS
        or any(value != "passed" for value in checks.values())
    ):
        raise ValueError("Release bundle has incomplete acceptance results")
    checksums = dict(files)
    checksums["bundle.json"] = sha256(manifest_path)
    expected_sums = "".join(
        f"{digest}  {name}\n" for name, digest in sorted(checksums.items())
    )
    sums = directory / "SHA256SUMS"
    if sums.is_symlink() or sums.read_text(encoding="utf-8") != expected_sums:
        raise ValueError("Release bundle checksum manifest does not match its contents")
    return manifest


def audit_runtime(
    wheel: Path, project: dict[str, Any], output: Path, minimum: bool
) -> None:
    """Resolve, exercise and audit runtime-only dependencies independently of dev tools."""
    label = "minimum" if minimum else "current"
    with tempfile.TemporaryDirectory(prefix=f"static-site-gen-{label}-") as name:
        directory = Path(name)
        prefix = directory / "venv"
        venv.EnvBuilder(with_pip=True).create(prefix)
        python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        constraints = []
        if minimum:
            for dependency in project["dependencies"]:
                requirement = Requirement(dependency)
                if requirement.marker and not requirement.marker.evaluate():
                    continue
                floors = [
                    item.version
                    for item in requirement.specifier
                    if item.operator == ">="
                ]
                if len(floors) != 1:
                    raise ValueError(
                        f"Dependency needs one explicit tested minimum: {dependency}"
                    )
                constraints.append(f"{requirement.name}=={floors[0]}")
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONTZPATH"] = ""
        run(
            python,
            "-m",
            "pip",
            "install",
            wheel,
            *constraints,
            cwd=directory,
            env=environment,
        )
        run(python, "-m", "pip", "check", cwd=directory, env=environment)
        run(
            python,
            "-I",
            "-c",
            "from zoneinfo import ZoneInfo; "
            "assert ZoneInfo('UTC'); assert ZoneInfo('America/Denver')",
            cwd=directory,
            env=environment,
        )
        run(
            python,
            "-I",
            "-m",
            "static_site_gen",
            "init",
            "sample",
            cwd=directory,
            env=environment,
        )
        run(
            python,
            "-I",
            "-m",
            "static_site_gen",
            "build",
            "--project-dir",
            "sample",
            cwd=directory,
            env=environment,
        )
        installed = json.loads(
            run(
                python,
                "-m",
                "pip",
                "list",
                "--format=json",
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
            ).stdout
        )
        requirements = output / f"runtime-{label}.txt"
        requirements.write_text(
            "".join(
                f"{item['name']}=={item['version']}\n"
                for item in sorted(installed, key=lambda item: item["name"].lower())
                if item["name"].lower().replace("_", "-")
                not in {"pip", "setuptools", "wheel", "static-site-gen"}
            ),
            encoding="utf-8",
        )
        run(
            sys.executable,
            "-m",
            "pip_audit",
            "--no-deps",
            "--disable-pip",
            "--requirement",
            requirements,
            "--format",
            "json",
            "--output",
            output / f"audit-{label}.json",
        )


def prepare_bundle(output_root: Path) -> Path:
    """Run all release gates once and freeze the exact checked artifacts."""
    if git("status", "--porcelain"):
        raise ValueError("Release preparation requires a clean committed working tree")
    commit = git("rev-parse", "HEAD")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    version = str(project["version"])
    parsed_version = Version(version)
    if parsed_version.pre is None or parsed_version.pre[0] != "a":
        raise ValueError("The first release must have an explicit prerelease version")
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / version
    if destination.exists():
        existing_manifest = validate_bundle(destination)
        if (
            existing_manifest["commit"] != commit
            or existing_manifest["version"] != version
        ):
            raise ValueError(
                "Existing frozen bundle belongs to another candidate; do not overwrite it"
            )
        print(f"Verified existing release bundle: {destination}")
        return destination
    environment = dict(os.environ)
    environment["PATH"] = (
        str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
    )
    run("make", "lint", "test", "hooks", env=environment)
    with tempfile.TemporaryDirectory(
        prefix=f".{version}-prepare-", dir=output_root
    ) as name:
        staged = Path(name)
        try:
            run(sys.executable, "-m", "build", "--outdir", staged)
            artifacts = sorted(
                path
                for path in staged.iterdir()
                if path.name.endswith((".whl", ".tar.gz"))
            )
            if len(artifacts) != 2:
                raise ValueError(
                    "Build did not produce exactly one wheel and one sdist"
                )
            run(sys.executable, "-m", "twine", "check", "--strict", *artifacts)
            wheel = next(path for path in artifacts if path.suffix == ".whl")
            sdist = next(path for path in artifacts if path.name.endswith(".tar.gz"))
            for artifact in artifacts:
                check_artifact(artifact, expected_version=version)
            check_source_distribution(sdist, expected_version=version)
            audit_runtime(wheel, project, staged, minimum=False)
            audit_runtime(wheel, project, staged, minimum=True)
            (staged / "release-notes.md").write_text(
                (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), encoding="utf-8"
            )
            if git("status", "--porcelain") or git("rev-parse", "HEAD") != commit:
                raise ValueError("Source checkout changed during release preparation")
            run_id = os.environ.get("GITHUB_RUN_ID")
            manifest: dict[str, Any] = {
                "schema": 1,
                "version": version,
                "tag": f"v{version}",
                "commit": commit,
                "repository": REPOSITORY,
                "python": sys.version.split()[0],
                "ci_run": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"
                if run_id
                else None,
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
                "files": {path.name: sha256(path) for path in sorted(staged.iterdir())},
            }
            write_json(staged / "bundle.json", manifest)
            hashes = dict(manifest["files"])
            hashes["bundle.json"] = sha256(staged / "bundle.json")
            (staged / "SHA256SUMS").write_text(
                "".join(
                    f"{digest}  {filename}\n"
                    for filename, digest in sorted(hashes.items())
                ),
                encoding="utf-8",
            )
            validate_bundle(staged)
            staged.replace(destination)
        except Exception:
            failed = output_root / f"failed-{version}-{commit[:12]}"
            if not failed.exists():
                staged.replace(failed)
                print(
                    f"Incomplete release evidence retained at {failed}", file=sys.stderr
                )
            raise
    print(f"Verified release bundle: {destination}")
    return destination


def main() -> int:
    """Prepare or verify an existing bundle without publication."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "verify"))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/release")
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            if args.bundle is None:
                parser.error("verify requires --bundle")
            manifest = validate_bundle(args.bundle)
            print(f"Verified {manifest['tag']} at {manifest['commit']}")
        else:
            prepare_bundle(args.output_dir)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Release validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
