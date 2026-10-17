"""Exercise first-alpha scaffolding and preview failure contracts."""

import http.client
import os
import re
import selectors
import signal
import subprocess
import sys
from argparse import Namespace
from contextlib import closing
from unittest.mock import patch

import pytest

from static_site_gen.cli import cmd_init, cmd_serve
from static_site_gen.generator.core import SiteGenerator


def test_init_preserves_an_existing_regular_file(tmp_path, capsys):
    """An existing file is reported without a traceback or any modification."""
    target = tmp_path / "existing"
    target.write_bytes(b"Existing user content")

    assert cmd_init(Namespace(project_name=str(target))) == 1

    assert target.read_bytes() == b"Existing user content"
    assert "not a directory" in capsys.readouterr().out


def test_unicode_scaffold_builds_under_non_utf8_file_locale(tmp_path):
    """Scaffold content uses UTF-8 independently of the process file locale."""
    environment = dict(
        os.environ,
        PYTHONUTF8="0",
        PYTHONCOERCECLOCALE="0",
        LC_ALL="C",
        LANG="C",
        PYTHONIOENCODING="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from argparse import Namespace; from pathlib import Path; "
            "from static_site_gen.cli import cmd_init; "
            "from static_site_gen.generator.core import SiteGenerator; "
            "project = Path(sys.argv[1]) / '\\u65e5\\u672c\\u8a9e'; "
            "assert cmd_init(Namespace(project_name=str(project))) == 0; "
            "SiteGenerator(project).build(); "
            "assert (project / 'site/index.html').is_file()",
            str(tmp_path),
        ],
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    project = tmp_path / "\u65e5\u672c\u8a9e"
    assert "\u65e5\u672c\u8a9e" in (project / "config.yaml").read_text(encoding="utf-8")
    about = (project / "site/about/index.html").read_text(encoding="utf-8")
    assert "https://github.com/johnmulder/static_site_gen" in about
    assert "github.com/example/" not in about


@pytest.mark.parametrize("port", [-1, 65536])
def test_serve_rejects_invalid_ports_before_binding(sample_project, capsys, port):
    """Invalid ports produce a controlled failure and no readiness announcement."""
    with patch("http.server.HTTPServer") as server:
        assert cmd_serve(Namespace(project_dir=str(sample_project), port=port)) == 1

    server.assert_not_called()
    output = capsys.readouterr().out
    assert "Port must be between 0 and 65535" in output
    assert "Serving site" not in output


def test_serve_reports_bind_failure_without_readiness(sample_project, capsys):
    """An unavailable port fails cleanly before announcing a running server."""
    (sample_project / "site").mkdir()
    with patch("http.server.HTTPServer", side_effect=OSError("Address already in use")):
        assert cmd_serve(Namespace(project_dir=str(sample_project), port=8000)) == 1

    output = capsys.readouterr().out
    assert "Error serving site: Address already in use" in output
    assert "Serving site" not in output


def test_preview_announces_bound_port_serves_and_stops(tmp_path):
    """A bounded HTTP request follows the printed URL, then Ctrl+C exits cleanly."""
    project = tmp_path / "preview"
    assert cmd_init(Namespace(project_name=str(project))) == 0
    SiteGenerator(project).build()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "static_site_gen",
            "serve",
            "--project-dir",
            str(project),
            "--port",
            "0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            assert ready.select(timeout=10), "Preview did not announce readiness"
            announcement = process.stdout.readline()
        address = re.search(r"http://localhost:(\d+)/", announcement)
        assert address is not None, announcement
        port = int(address.group(1))
        assert 1 <= port <= 65535
        with closing(
            http.client.HTTPConnection("localhost", port, timeout=5)
        ) as connection:
            connection.request("GET", "/")
            response = connection.getresponse()
            assert response.status == 200
            assert b"Hello World" in response.read()
        process.send_signal(signal.SIGINT)
        output, errors = process.communicate(timeout=10)
        assert process.returncode == 0, errors
        assert "Server stopped." in output
        assert "Traceback" not in errors
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
