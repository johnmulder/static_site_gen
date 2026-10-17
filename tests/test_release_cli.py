"""Exercise first-alpha scaffolding and preview failure contracts."""

import http.client
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from argparse import Namespace
from contextlib import closing
from importlib import resources
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


def test_unicode_project_name_builds_with_utf8_filesystem(tmp_path):
    """Unicode names work with the supported platforms' normal filesystem encoding."""
    project = tmp_path / "\u65e5\u672c\u8a9e"
    assert cmd_init(Namespace(project_name=str(project))) == 0

    SiteGenerator(project).build()

    assert "\u65e5\u672c\u8a9e" in (project / "config.yaml").read_text(encoding="utf-8")
    assert (project / "site/index.html").is_file()


def test_unicode_scaffold_content_uses_utf8_under_ascii_locale(tmp_path):
    """Unicode text does not depend on the default file encoding or Unicode paths."""
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
            "import codecs, locale, sys; "
            "from argparse import Namespace; from pathlib import Path; "
            "from static_site_gen import cli; "
            "from static_site_gen.generator.core import SiteGenerator; "
            "assert codecs.lookup(locale.getpreferredencoding(False)).name == 'ascii'; "
            "label = '\\u65e5\\u672c\\u8a9e'; "
            "cli._DEFAULT_CONFIG = cli._DEFAULT_CONFIG.replace("
            "'site_name: {site_name}', 'site_name: Locale ' + label); "
            "cli._DEFAULT_FIRST_POST = cli._DEFAULT_FIRST_POST.replace("
            "'Hello World', 'Locale Post ' + label); "
            "cli._DEFAULT_STYLE += '\\n/* ' + label + ' */\\n'; "
            "project = Path(sys.argv[1]) / 'ascii-project'; "
            "assert cli.cmd_init(Namespace(project_name=str(project))) == 0; "
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
    project = tmp_path / "ascii-project"
    assert "Locale \u65e5\u672c\u8a9e" in (project / "config.yaml").read_text(
        encoding="utf-8"
    )
    assert "Locale Post \u65e5\u672c\u8a9e" in next(
        (project / "content/posts").glob("*.md")
    ).read_text(encoding="utf-8")
    assert "Locale Post \u65e5\u672c\u8a9e" in (
        project / "site/posts/locale-post/index.html"
    ).read_text(encoding="utf-8")
    template = project / "templates/index.html"
    packaged = resources.files("static_site_gen.resources").joinpath(
        "templates/index.html"
    )
    assert template.read_bytes() == packaged.read_bytes()
    assert "\u2190" in template.read_text(encoding="utf-8")
    assert "\u65e5\u672c\u8a9e" in (project / "site/static/style.css").read_text(
        encoding="utf-8"
    )
    about = (project / "site/about/index.html").read_text(encoding="utf-8")
    assert "https://github.com/johnmulder/static_site_gen" in about
    assert "github.com/example/" not in about


def test_init_reports_filesystem_encoding_failure(tmp_path, capsys):
    """A filesystem that cannot encode a name gets a controlled diagnostic."""
    with patch(
        "static_site_gen.cli.Path.resolve",
        side_effect=UnicodeEncodeError("ascii", "\u65e5", 0, 1, "unsupported path"),
    ):
        assert cmd_init(Namespace(project_name=str(tmp_path / "\u65e5"))) == 1

    assert "Error creating project:" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


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
        bufsize=0,
    )
    try:
        assert process.stdout is not None
        announcement = bytearray()
        deadline = time.monotonic() + 30
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            while b"\n" not in announcement:
                remaining = deadline - time.monotonic()
                assert remaining > 0, "Preview startup timed out"
                events = ready.select(timeout=remaining)
                assert events, "Preview did not announce readiness"
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                announcement.extend(chunk)
        address = re.search(rb"http://localhost:(\d+)/", announcement)
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
        assert b"Server stopped." in output
        assert b"Traceback" not in errors
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
