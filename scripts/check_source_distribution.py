"""Reproduce non-Git validation from one exact source archive without recursion."""

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
import venv
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_installed_artifacts import inspect_artifact  # noqa: E402


def check_source_distribution(
    artifact: Path, *, expected_version: str | None = None
) -> None:
    """Extract, install, lint, type-check, test, and build a wheel exactly once."""
    artifact = artifact.resolve(strict=True)
    if not artifact.name.endswith(".tar.gz"):
        raise ValueError(f"Expected a source distribution: {artifact}")
    version = inspect_artifact(artifact, expected_version)
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(PYTHONNOUSERSITE="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    with tempfile.TemporaryDirectory(prefix="static-site-gen-source-") as name:
        directory = Path(name)
        source = directory / "source"
        source.mkdir()
        with tarfile.open(artifact) as archive:
            archive.extractall(source, filter="data")
        project = next(source.iterdir())
        prefix = directory / "venv"
        venv.EnvBuilder(with_pip=True).create(prefix)
        python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        def run(*args: str | Path) -> None:
            subprocess.run(
                [str(python), *(str(argument) for argument in args)],
                cwd=project,
                env=environment,
                check=True,
                timeout=600,
            )

        run("-m", "pip", "install", "--no-input", ".[dev]")
        run("-m", "pip", "check")
        run("-m", "ruff", "check", ".")
        run("-m", "ruff", "format", "--check", ".")
        run("-m", "mypy", "static_site_gen", "tests", "scripts")
        run("-m", "pytest", "--cov-fail-under=95")
        wheels = directory / "wheels"
        run("-m", "build", "--wheel", "--outdir", wheels)
        wheel = next(wheels.glob("*.whl"))
        inspect_artifact(wheel, version)
        run("-m", "twine", "check", "--strict", wheel)
        print(f"Source distribution acceptance passed: {artifact.name}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--expected-version")
    args = parser.parse_args()
    check_source_distribution(args.artifact, expected_version=args.expected_version)


if __name__ == "__main__":
    main()
