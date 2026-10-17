"""Installed metadata and timezone fallback remain usable without OS setup."""

import os
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import static_site_gen
from static_site_gen import generator


def test_public_versions_match_project_metadata():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert static_site_gen.__version__ == project["project"]["version"]
    assert generator.__version__ == static_site_gen.__version__
    assert version("static-site-gen") == static_site_gen.__version__


def test_timezones_work_without_system_timezone_files():
    environment = dict(os.environ, PYTHONTZPATH="")
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "from zoneinfo import ZoneInfo; "
            "assert ZoneInfo('UTC').key == 'UTC'; "
            "assert ZoneInfo('America/Denver').key == 'America/Denver'",
        ],
        env=environment,
        check=True,
        timeout=15,
    )
