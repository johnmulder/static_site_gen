"""
Command-line interface for the static site generator.

This module provides the CLI commands for building and managing static sites.
"""

import argparse
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from .generator.core import SiteGenerator

# ---------------------------------------------------------------------------
# Default scaffolding content embedded as strings so ``init`` works without
# needing to locate installed package data.
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = """\
site_name: "{site_name}"
base_url: "https://example.com"
author: "Your Name"
description: "A new static site"
timezone: "UTC"
posts_per_page: 10
output_dir: "site"
"""

_DEFAULT_FIRST_POST = """\
---
title: "Hello World"
date: {today}
tags: [welcome]
description: "My first post"
---

# Hello World

Welcome to my new site! This is a sample post created by `static-site-gen init`.
"""

_DEFAULT_ABOUT_PAGE = """\
---
title: "About"
date: {today}
description: "About this site"
---

# About

This site was generated with [static-site-gen](https://github.com/example/static-site-gen).
"""

_DEFAULT_STYLE = """\
/* Basic reset and typography */
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: system-ui, -apple-system, sans-serif;
    line-height: 1.6;
    max-width: 42rem;
    margin: 0 auto;
    padding: 1rem;
    color: #222;
}
a { color: #0366d6; }
pre { background: #f6f8fa; padding: 1rem; overflow-x: auto; }
code { font-size: 0.9em; }
"""


def cmd_build(args: argparse.Namespace) -> int:
    """
    Execute site build command.

    Args:
        args: Parsed command-line arguments
    """
    try:
        project_root = Path(args.project_dir).resolve()
        generator = SiteGenerator(project_root)
        generator.build()
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Make sure you're in a valid project directory with config.yaml")
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"Build failed: {e}")
        return 1


def cmd_init(args: argparse.Namespace) -> int:
    """
    Scaffold a new static site project.

    Creates the directory structure, default templates (copied from the
    package's own templates/ directory when available, otherwise skipped),
    sample content, configuration, and a minimal stylesheet.

    Args:
        args: Parsed command-line arguments (expects ``project_name``)
    """
    from datetime import date

    project_dir = Path(args.project_name).resolve()

    if project_dir.exists() and any(project_dir.iterdir()):
        print(f"Error: '{args.project_name}' already exists and is not empty")
        return 1

    try:
        today = date.today().isoformat()

        # Directory skeleton
        dirs = [
            project_dir / "content" / "posts",
            project_dir / "content" / "pages",
            project_dir / "templates",
            project_dir / "static",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # Config
        config_text = _DEFAULT_CONFIG.format(site_name=args.project_name)
        (project_dir / "config.yaml").write_text(config_text)

        # Sample content
        first_post = _DEFAULT_FIRST_POST.format(today=today)
        filename = f"{today}-hello-world.md"
        (project_dir / "content" / "posts" / filename).write_text(first_post)

        about_page = _DEFAULT_ABOUT_PAGE.format(today=today)
        (project_dir / "content" / "pages" / "about.md").write_text(about_page)

        # Stylesheet
        (project_dir / "static" / "style.css").write_text(_DEFAULT_STYLE)

        # Copy real templates from the package's sibling templates/ directory
        # (works when running from a source checkout or editable install).
        package_root = Path(__file__).resolve().parent.parent
        source_templates = package_root / "templates"
        if source_templates.is_dir():
            for src in source_templates.iterdir():
                if src.is_file():
                    shutil.copy(src, project_dir / "templates" / src.name)

        print(f"Created new site project in '{args.project_name}'")
        print(f"  {project_dir}/")
        print("  |-- config.yaml")
        print("  |-- content/posts/  (1 sample post)")
        print("  |-- content/pages/  (about page)")
        print("  |-- templates/")
        print("  |-- static/style.css")
        print()
        print("Next steps:")
        print(f"  cd {args.project_name}")
        print("  static-site-gen build")
        return 0
    except OSError as e:
        print(f"Error creating project: {e}")
        return 1


def create_parser() -> argparse.ArgumentParser:
    """
    Create command-line argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="static-site-gen", description="A minimal Python static site generator"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build static site")
    build_parser.add_argument(
        "--project-dir",
        default=".",
        help="Project directory (default: current directory)",
    )
    build_parser.set_defaults(func=cmd_build)

    # Init command (placeholder for future)
    init_parser = subparsers.add_parser("init", help="Initialize new site project")
    init_parser.add_argument("project_name", help="Name of the new project")
    init_parser.set_defaults(func=cmd_init)

    return parser


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = create_parser()

    if len(sys.argv) == 1:
        parser.print_help()
        return 1

    args: argparse.Namespace = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    command_func = cast(Callable[[argparse.Namespace], int], getattr(args, "func"))
    return command_func(args)


if __name__ == "__main__":
    sys.exit(main())
