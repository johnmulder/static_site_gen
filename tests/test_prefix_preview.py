"""Exercise prefix mounts through the preview HTTP interface."""

import functools
import http.client
from argparse import Namespace
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.parse import quote

import pytest
import yaml

from static_site_gen.cli import _PreviewHandler, _PreviewServer, cmd_serve


@contextmanager
def _preview(directory: Path, prefix: str) -> Iterator[int]:
    handler = functools.partial(
        _PreviewHandler, directory=str(directory), url_prefix=prefix
    )
    with _PreviewServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive(), "Preview did not stop"


def _request(
    port: int, target: str, method: str = "GET"
) -> tuple[int, dict[str, str], bytes]:
    with closing(
        http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    ) as connection:
        connection.request(method, target)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    output = tmp_path / "site"
    output.mkdir()
    (output / "index.html").write_text("Preview home", encoding="utf-8")
    (output / "docs").mkdir()
    (output / "docs/index.html").write_text("Nested document", encoding="utf-8")
    (output / "style.css").write_text("body {}", encoding="utf-8")
    return output


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "/blog",
        "/nested/blog",
        "/caf%C3%A9",
        "/space%20%23%3F%25",
        "/literal%2520",
        "/%252e%252e",
    ],
)
def test_preview_mounts_existing_output_for_get_and_head(output_dir, prefix):
    with _preview(output_dir, prefix) as port:
        status, headers, body = _request(port, prefix + "/")
        assert status == 200
        assert body == b"Preview home"
        assert int(headers["Content-Length"]) == len(body)

        status, headers, body = _request(port, prefix + "/", "HEAD")
        assert status == 200
        assert int(headers["Content-Length"]) == len(b"Preview home")
        assert body == b""
        assert _request(port, prefix + "/style.css")[2] == b"body {}"


@pytest.mark.parametrize("prefix", ["/blog", "/nested/blog", "/caf%C3%A9"])
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_prefix_and_directory_redirects_preserve_public_path_and_query(
    output_dir, prefix, method
):
    query = "?next=%2Fdocs%2F&search=two%20words"
    with _preview(output_dir, prefix) as port:
        for directory in (prefix, prefix + "/docs"):
            status, headers, body = _request(port, directory + query, method)
            assert status == 301
            assert headers["Location"] == directory + "/" + query
            assert body == b""
            status, _, body = _request(port, headers["Location"], method)
            assert status == 200
            assert body == (
                b""
                if method == "HEAD"
                else (
                    b"Nested document"
                    if directory.endswith("/docs")
                    else b"Preview home"
                )
            )


@pytest.mark.parametrize("prefix", ["", "/blog", "/caf%C3%A9"])
@pytest.mark.parametrize(
    "slug", ["café #?% done", "literal%20", "encoded%2Fname", "literal%ff"]
)
def test_encoded_unicode_and_reserved_slug_paths_are_decoded_once(
    output_dir, prefix, slug
):
    page = output_dir / slug
    page.mkdir()
    (page / "index.html").write_text(slug, encoding="utf-8")
    with _preview(output_dir, prefix) as port:
        status, _, body = _request(port, prefix + "/" + quote(slug, safe="") + "/")
        assert status == 200
        assert body.decode("utf-8") == slug


def test_encoded_nested_slug_and_root_directory_listing(output_dir):
    page = output_dir / "nested/child"
    page.mkdir(parents=True)
    (page / "index.html").write_text("Nested slug", encoding="utf-8")
    listing = output_dir / "listing"
    listing.mkdir()
    (listing / "café #?.txt").write_text("Listed file", encoding="utf-8")
    with _preview(output_dir, "") as port:
        assert _request(port, "/nested%2Fchild/")[2] == b"Nested slug"
        status, _, body = _request(port, "/listing/")
        assert status == 200
        assert b"caf%C3%A9%20%23%3F.txt" in body
        assert _request(port, "/listing/caf%C3%A9%20%23%3F.txt")[2] == b"Listed file"
        assert _request(port, "/style.css/")[0] == 404


@pytest.mark.parametrize(
    "target",
    [
        "/",
        "/index.html",
        "/docs/",
        "/blogger/",
        "/blog-other/",
        "/blog.html",
        "/blog%252Fdocs/",
        "http://localhost/blog/",
    ],
)
def test_paths_outside_prefix_are_not_served(output_dir, target):
    with _preview(output_dir, "/blog") as port:
        assert _request(port, target)[0] == 404


@pytest.mark.parametrize("prefix", ["", "/blog", "/nested/blog"])
@pytest.mark.parametrize(
    "suffix",
    [
        "/../private.txt",
        "/docs/../../private.txt",
        "/./index.html",
        "/%2e%2e/private.txt",
        "/%2E%2E%2Fprivate.txt",
        "/%252e%252e%252fprivate.txt",
        "/%25252e%25252e/private.txt",
        "/%5c..%5cprivate.txt",
        "/%255c..%255cprivate.txt",
        "/%00index.html",
        "/%2500index.html",
        "/%FF",
    ],
)
def test_traversal_and_invalid_paths_do_not_expose_siblings(output_dir, prefix, suffix):
    (output_dir.parent / "private.txt").write_text("Sibling secret", encoding="utf-8")
    with _preview(output_dir, prefix) as port:
        status, _, body = _request(port, prefix + suffix)
        assert status == 404
        assert b"Sibling secret" not in body


@pytest.mark.parametrize("prefix", ["", "/blog"])
def test_symlink_files_directories_and_index_pages_cannot_expose_siblings(
    output_dir, prefix
):
    sibling = output_dir.parent / "private"
    sibling.mkdir()
    (sibling / "index.html").write_text("Sibling secret", encoding="utf-8")
    (output_dir / "leaked-file").symlink_to(sibling / "index.html")
    (output_dir / "leaked-directory").symlink_to(sibling, target_is_directory=True)
    (output_dir / "index-link").mkdir()
    (output_dir / "index-link/index.html").symlink_to(sibling / "index.html")
    (output_dir / "loop").symlink_to(output_dir / "loop")
    with _preview(output_dir, prefix) as port:
        for suffix in ("/leaked-file", "/leaked-directory/", "/index-link/", "/loop"):
            status, _, body = _request(port, prefix + suffix)
            assert status == 404
            assert b"Sibling secret" not in body


def test_serve_announces_canonical_prefix_and_passes_mount_to_handler(
    sample_project, capsys
):
    config_path = sample_project / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["base_url"] = "https://example.com/nested/café/"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    (sample_project / "site").mkdir()
    with patch("static_site_gen.cli._PreviewServer") as server:
        running = server.return_value.__enter__.return_value
        running.server_port = 43210
        running.serve_forever.side_effect = KeyboardInterrupt
        assert cmd_serve(Namespace(project_dir=str(sample_project), port=0)) == 0

    _, handler = server.call_args.args
    assert handler.keywords["url_prefix"] == "/nested/caf%C3%A9"
    assert handler.keywords["directory"] == str(sample_project / "site")
    output = capsys.readouterr().out
    assert "http://localhost:43210/nested/caf%C3%A9/" in output
    assert "Server stopped." in output
