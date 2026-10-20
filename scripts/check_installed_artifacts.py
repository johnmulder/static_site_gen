"""Inspect exact distributions and exercise their installed CLI contracts."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import venv
import zipfile
from collections.abc import Iterator
from email.parser import Parser
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import yaml

TEMPLATES = {
    "base.html",
    "feed.xml",
    "index.html",
    "page.html",
    "post.html",
    "sitemap.xml",
    "tag.html",
    "tag_index.html",
}


def inspect_artifact(artifact: Path, expected_version: str | None = None) -> str:
    """Require complete package resources and consistent distribution metadata."""
    artifact = artifact.resolve(strict=True)
    if artifact.name.endswith(".whl"):
        with zipfile.ZipFile(artifact) as wheel:
            names = set(wheel.namelist())
            metadata_paths = [
                name for name in names if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_paths) != 1:
                raise RuntimeError(f"{artifact.name}: expected one wheel metadata file")
            metadata = Parser().parsestr(wheel.read(metadata_paths[0]).decode("utf-8"))
            required = {
                "static_site_gen/__init__.py",
                "static_site_gen/__main__.py",
                "static_site_gen/cli.py",
                *(f"static_site_gen/resources/templates/{name}" for name in TEMPLATES),
            }
            licenses = [
                name for name in names if name.endswith(".dist-info/licenses/LICENSE")
            ]
            if len(licenses) != 1:
                raise RuntimeError(f"{artifact.name}: missing MIT license")
            license_content = wheel.read(licenses[0])
            for name in TEMPLATES:
                path = f"static_site_gen/resources/templates/{name}"
                if path in names and not wheel.read(path).strip():
                    raise RuntimeError(f"{artifact.name}: empty template: {name}")
    elif artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact) as source:
            roots = {Path(name).parts[0] for name in source.getnames()}
            if len(roots) != 1:
                raise RuntimeError(f"{artifact.name}: expected one source archive root")
            root = roots.pop()
            names = {name.removeprefix(root + "/") for name in source.getnames()}
            if not {"PKG-INFO", "pyproject.toml"}.issubset(names):
                raise RuntimeError(f"{artifact.name}: missing source metadata")
            member = source.extractfile(f"{root}/PKG-INFO")
            project_file = source.extractfile(f"{root}/pyproject.toml")
            if member is None or project_file is None:
                raise RuntimeError(f"{artifact.name}: missing source metadata")
            metadata = Parser().parsestr(member.read().decode("utf-8"))
            project = tomllib.loads(project_file.read().decode("utf-8"))["project"]
            if metadata["Version"] != project["version"]:
                raise RuntimeError(
                    f"{artifact.name}: source and metadata versions differ"
                )
            required = {
                "LICENSE",
                "README.md",
                "CHANGELOG.md",
                "DEVELOPMENT.md",
                "RELEASE_PLAN.md",
                "Makefile",
                "MANIFEST.in",
                ".pre-commit-config.yaml",
                "tests/__init__.py",
                "tests/conftest.py",
                "tests/fixtures/sample_post.md",
                "tests/fixtures/draft_post.md",
                "tests/fixtures/sample_page.md",
                "tests/fixtures/minimal_post.md",
                "scripts/check_installed_artifacts.py",
                "scripts/check_source_distribution.py",
                *(f"templates/{name}" for name in TEMPLATES),
                *(f"static_site_gen/resources/templates/{name}" for name in TEMPLATES),
            }
            license_file = (
                source.extractfile(f"{root}/LICENSE") if "LICENSE" in names else None
            )
            license_content = license_file.read() if license_file is not None else b""
            for path in required:
                if path in names and path.startswith(
                    ("templates/", "static_site_gen/resources/templates/")
                ):
                    template = source.extractfile(f"{root}/{path}")
                    if template is None or not template.read().strip():
                        raise RuntimeError(f"{artifact.name}: empty template: {path}")
    else:
        raise ValueError(f"Expected a wheel or sdist: {artifact}")
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"{artifact.name}: missing files: {', '.join(missing)}")
    if (
        b"MIT License" not in license_content
        or b"Permission is hereby granted" not in license_content
    ):
        raise RuntimeError(f"{artifact.name}: incorrect MIT license contents")
    if metadata["Name"] != "static-site-gen" or metadata["License-Expression"] != "MIT":
        raise RuntimeError(
            f"{artifact.name}: unexpected package name or license metadata"
        )
    version = metadata["Version"]
    if not version or (expected_version is not None and version != expected_version):
        raise RuntimeError(f"{artifact.name}: unexpected version {version!r}")
    return str(version)


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.values.extend(
            value for name, value in attrs if name in {"href", "src"} and value
        )


def _origin(parsed: urllib.parse.SplitResult) -> tuple[str, str | None, int | None]:
    """Compare HTTP origins with their default ports made explicit."""
    return (
        parsed.scheme.lower(),
        parsed.hostname,
        parsed.port
        if parsed.port is not None
        else {"http": 80, "https": 443}.get(parsed.scheme.lower()),
    )


def _check_link(
    output: Path,
    source: Path,
    link: str,
    base_url: str = "https://example.com",
    *,
    require_same_site: bool = False,
) -> tuple[str, Path] | None:
    """Resolve a public URL inside its mount, retaining authored relative paths."""
    link = link.strip()
    base = urllib.parse.urlsplit(base_url)
    parsed = urllib.parse.urlsplit(link)
    if require_same_site and (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or _origin(parsed) != _origin(base)
    ):
        raise RuntimeError(f"{source}: expected configured site origin: {link}")
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc and _origin(
        urllib.parse.urlsplit(urllib.parse.urljoin(base_url, link))
    ) != _origin(base):
        return None
    if parsed.scheme and not parsed.netloc:
        raise RuntimeError(f"{source}: invalid local URL: {link}")
    if not parsed.path and not require_same_site:
        return None
    prefix = urllib.parse.unquote(base.path, errors="strict").rstrip("/")
    source_url = urllib.parse.urlunsplit(
        (
            base.scheme,
            base.netloc,
            base.path.rstrip("/")
            + "/"
            + urllib.parse.quote(source.relative_to(output).as_posix(), safe="/"),
            "",
            "",
        )
    )
    resolved = urllib.parse.urlsplit(urllib.parse.urljoin(source_url, link))
    try:
        path = urllib.parse.unquote(resolved.path, errors="strict")
    except UnicodeError as exc:
        raise RuntimeError(f"{source}: invalid local URL encoding: {link}") from exc
    if "\x00" in path or "\\" in path:
        raise RuntimeError(f"{source}: invalid local URL path: {link}")
    if prefix and path != prefix and not path.startswith(prefix + "/"):
        raise RuntimeError(f"{source}: link escapes configured URL prefix: {link}")
    relative = path[len(prefix) :].lstrip("/")
    destination = output / relative
    if path.endswith("/") or destination.is_dir():
        destination /= "index.html"
    if not destination.resolve().is_relative_to(output.resolve()):
        raise RuntimeError(f"{source}: link escapes output: {link}")
    if not destination.is_file():
        raise RuntimeError(f"{source}: broken local link: {link}")
    public_path = urllib.parse.quote(path or "/", safe="/")
    if resolved.query:
        public_path += "?" + urllib.parse.quote(
            resolved.query, safe="%=&;:+,/?@!$'()*[]-"
        )
    return public_path, destination


def _site_links(output: Path) -> Iterator[tuple[Path, str, bool]]:
    """Collect HTML links and the machine-owned XML URLs that must stay local."""
    for document in output.rglob("*.html"):
        links = _Links()
        links.feed(document.read_text(encoding="utf-8"))
        for link in links.values:
            yield document, link, False
    feed = ElementTree.parse(output / "feed.xml")
    if feed.getroot().tag != "rss" or feed.find("channel") is None:
        raise RuntimeError("Expected an RSS channel")
    for selector in ("./channel/link", "./channel/item/link"):
        for element in feed.findall(selector):
            yield output / "feed.xml", element.text or "", True
    for element in feed.findall("./channel/item/guid"):
        if element.get("isPermaLink", "true").lower() != "false":
            yield output / "feed.xml", element.text or "", True
    for element in feed.findall("./channel/{http://www.w3.org/2005/Atom}link"):
        yield output / "feed.xml", element.get("href", ""), True
    sitemap = ElementTree.parse(output / "sitemap.xml")
    if sitemap.getroot().tag != "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset":
        raise RuntimeError("Expected a sitemap urlset")
    for element in sitemap.findall("{*}url/{*}loc"):
        yield output / "sitemap.xml", element.text or "", True


def validate_site(output: Path, base_url: str = "https://example.com") -> None:
    """Require generated local HTML and XML links to resolve within the mount."""
    for source, link, machine_owned in _site_links(output):
        _check_link(output, source, link, base_url, require_same_site=machine_owned)


def _preview(
    cli: Path,
    project: Path,
    environment: dict[str, str],
    output_dir: Path,
    base_url: str = "https://example.com",
) -> None:
    """Request mounted pages, linked assets, XML URLs, and directory redirects."""
    prefix = urllib.parse.urlsplit(base_url).path.rstrip("/")
    homepage = prefix + "/"
    requests = {homepage: output_dir / "index.html"}
    for source, link, machine_owned in _site_links(output_dir):
        local = _check_link(
            output_dir, source, link, base_url, require_same_site=machine_owned
        )
        if local is not None:
            requests[local[0]] = local[1]
    for path, destination in list(requests.items()):
        if path.endswith("/"):
            requests[(path.rstrip("/") or "/") + "?preview=1"] = destination
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    process = subprocess.Popen(
        [str(cli), "serve", "--project-dir", str(project), "--port", str(port)],
        cwd=project.parent,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}{homepage}", timeout=1
                ) as response:
                    if response.read() != (output_dir / "index.html").read_bytes():
                        raise RuntimeError(
                            "Preview did not serve the generated homepage"
                        )
                break
            except urllib.error.URLError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Preview server did not become ready") from None
                time.sleep(0.05)
        for path, destination in requests.items():
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{path}", timeout=2
            ) as response:
                if response.read() != destination.read_bytes():
                    raise RuntimeError(f"Preview returned incorrect content: {path}")
                requested = urllib.parse.urlsplit(path)
                expected_path = requested.path or "/"
                if destination.name == "index.html" and not expected_path.endswith(
                    ("/", "/index.html")
                ):
                    expected_path += "/"
                actual = urllib.parse.urlsplit(response.geturl())
                if actual.path != expected_path or actual.query != requested.query:
                    raise RuntimeError(f"Preview lost its URL prefix or query: {path}")
        if prefix:
            for path in ("/", "/static/style.css", prefix + "-outside/"):
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}{path}", timeout=2
                    ):
                        pass
                except urllib.error.HTTPError as exc:
                    if exc.code != 404:
                        raise RuntimeError(
                            f"Preview returned {exc.code}: {path}"
                        ) from exc
                else:
                    raise RuntimeError(f"Preview served outside its URL prefix: {path}")
        process.send_signal(signal.SIGINT)
        output, _ = process.communicate(timeout=5)
        if process.returncode != 0:
            raise RuntimeError(f"Preview shutdown failed: {output.decode('utf-8')}")
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def _snapshot(output: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }


def check_artifact(artifact: Path, *, expected_version: str | None = None) -> None:
    """Check one exact wheel or sdist through a fresh installation outside the repo."""
    artifact = artifact.resolve(strict=True)
    version = inspect_artifact(artifact, expected_version)
    subprocess.run(
        [sys.executable, "-m", "twine", "check", "--strict", str(artifact)], check=True
    )
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        PYTHONNOUSERSITE="1", PYTHONTZPATH="", PIP_DISABLE_PIP_VERSION_CHECK="1"
    )
    with tempfile.TemporaryDirectory(prefix="static-site-gen-installed-") as name:
        directory = Path(name)
        prefix = directory / "venv"
        venv.EnvBuilder(with_pip=True).create(prefix)
        executable_dir = prefix / ("Scripts" if os.name == "nt" else "bin")
        python = executable_dir / ("python.exe" if os.name == "nt" else "python")
        cli = executable_dir / (
            "static-site-gen.exe" if os.name == "nt" else "static-site-gen"
        )

        def run(*args: str | Path, expected_exit: int = 0) -> None:
            result = subprocess.run(
                [str(argument) for argument in args],
                cwd=directory,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=300,
            )
            if (
                result.returncode != expected_exit
                or "Traceback (most recent call last)" in result.stdout
            ):
                raise RuntimeError(f"Command failed: {args}\n{result.stdout}")

        run(python, "-m", "pip", "install", "--no-input", artifact)
        run(python, "-m", "pip", "check")
        run(
            python,
            "-I",
            "-c",
            "import static_site_gen, sys; from pathlib import Path; "
            "from importlib.metadata import version; from zoneinfo import ZoneInfo; "
            "from static_site_gen import generator; "
            "assert Path(static_site_gen.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); "
            "assert static_site_gen.__version__ == generator.__version__ == version('static-site-gen') == sys.argv[1]; "
            "assert ZoneInfo('UTC').key == 'UTC'; assert ZoneInfo('America/Denver').key == 'America/Denver'",
            version,
        )
        run(cli, "--help")
        module = (python, "-I", "-m", "static_site_gen")
        run(*module, "--help")
        run(cli, "init", "sample-site")
        project = directory / "sample-site"
        run(cli, "build", "--project-dir", project)
        validate_site(project / "site")
        _preview(cli, project, environment, project / "site")

        configuration = project / "config.yaml"
        config = yaml.safe_load(configuration.read_text(encoding="utf-8"))
        config.update(posts_per_page=1, output_dir="artifacts/public")
        configuration.write_text(yaml.safe_dump(config), encoding="utf-8")
        published = project / "content/posts/reserved.md"
        published.write_text(
            "---\n"
            + yaml.safe_dump(
                {
                    "title": "Reserved route",
                    "date": "2025-10-17",
                    "slug": "\u65e5\u672c\u8a9e#?%20/part",
                    "tags": ["\u65e5\u672c\u8a9e#?%20"],
                },
                allow_unicode=True,
            )
            + "---\nPublished route body.\n\n[Site home](../../../)\n"
            "\n[Stylesheet](../../../static/style.css)\n",
            encoding="utf-8",
        )
        draft = project / "content/posts/draft.md"
        draft.write_text(
            "---\ntitle: Private Draft\ndate: 2025-10-18\ndraft: true\ntags: [private-draft]\n---\nPrivate draft body.\n",
            encoding="utf-8",
        )
        output = project / "artifacts/public"
        run(*module, "build", "--project-dir", project)
        if (
            not (output / "page/2/index.html").is_file()
            or not (output / "posts/\u65e5\u672c\u8a9e#?%20/part/index.html").is_file()
        ):
            raise RuntimeError("Pagination or reserved-character output is missing")
        if any(
            b"Private Draft" in data or b"private-draft" in data
            for data in _snapshot(output).values()
        ):
            raise RuntimeError("Draft content leaked into default output")
        validate_site(output)
        _preview(cli, project, environment, output)
        for base_url in (
            "https://example.com/blog",
            "https://example.com/nested/blog",
            "https://example.com/%E6%97%A5%E6%9C%AC%E8%AA%9E/blog",
        ):
            config["base_url"] = base_url
            configuration.write_text(yaml.safe_dump(config), encoding="utf-8")
            run(*module, "build", "--project-dir", project)
            validate_site(output, base_url)
            _preview(cli, project, environment, output, base_url)
        run(*module, "build", "--project-dir", project, "--drafts")
        if len(ElementTree.parse(output / "feed.xml").findall("./channel/item")) != 3:
            raise RuntimeError("--drafts did not include the draft in RSS")
        validate_site(output, base_url)

        for post in (project / "content/posts").glob("*.md"):
            if post != draft:
                post.unlink()
        run(cli, "build", "--project-dir", project)
        if (
            ElementTree.parse(output / "feed.xml").findall("./channel/item")
            or (output / "posts").exists()
        ):
            raise RuntimeError(
                "Draft-only build published posts or retained stale output"
            )
        draft.unlink()
        run(*module, "build", "--project-dir", project)
        validate_site(output, base_url)
        if "No posts yet." not in (output / "index.html").read_text(encoding="utf-8"):
            raise RuntimeError("Empty site did not render its homepage")
        previous = _snapshot(output)
        (project / "templates/index.html").unlink()
        run(cli, "build", "--project-dir", project, expected_exit=1)
        if _snapshot(output) != previous:
            raise RuntimeError("Failed rebuild changed the previous output")
        print(f"Installed acceptance passed: {artifact.name}", flush=True)


def main() -> None:
    """Check every supplied distribution independently."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path, nargs="+")
    parser.add_argument("--expected-version")
    args = parser.parse_args()
    for artifact in args.artifacts:
        check_artifact(artifact, expected_version=args.expected_version)


if __name__ == "__main__":
    main()
