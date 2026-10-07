"""Exercise packaged templates through fresh installed init/build commands."""

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def check_artifact(artifact: Path) -> None:
    """Install one wheel or sdist without importing the source checkout."""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONNOUSERSITE"] = "1"
    with tempfile.TemporaryDirectory(prefix="static-site-gen-installed-") as name:
        directory = Path(name)
        prefix = directory / "venv"
        venv.EnvBuilder(with_pip=True).create(prefix)
        executable_dir = prefix / ("Scripts" if os.name == "nt" else "bin")
        python = executable_dir / ("python.exe" if os.name == "nt" else "python")
        cli = executable_dir / (
            "static-site-gen.exe" if os.name == "nt" else "static-site-gen"
        )

        def run(*args: str | Path) -> None:
            subprocess.run(
                [str(argument) for argument in args],
                cwd=directory,
                env=environment,
                check=True,
            )

        run(python, "-m", "pip", "install", artifact)
        run(
            python,
            "-I",
            "-c",
            "import static_site_gen, sys; from pathlib import Path; "
            "origin = Path(static_site_gen.__file__).resolve(); "
            "print(origin); "
            "sys.exit(0 if origin.is_relative_to(Path(sys.prefix).resolve()) else 1)",
        )
        run(cli, "init", "sample-site")
        project = directory / "sample-site"
        run(cli, "build", "--project-dir", project)
        expected = (
            "index.html",
            "posts/hello-world/index.html",
            "about/index.html",
            "tag/index.html",
            "tag/welcome/index.html",
            "feed.xml",
            "sitemap.xml",
            "static/style.css",
        )
        for relative in expected:
            output = project / "site" / relative
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError(f"{artifact.name}: missing or empty {relative}")
        print(f"Installed init/build passed: {artifact.name}", flush=True)


def main() -> None:
    """Check every supplied distribution independently."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path, nargs="+")
    args = parser.parse_args()
    for artifact in args.artifacts:
        artifact = artifact.resolve(strict=True)
        if not artifact.name.endswith((".whl", ".tar.gz")):
            parser.error(f"expected a wheel or sdist: {artifact}")
        check_artifact(artifact)


if __name__ == "__main__":
    main()
