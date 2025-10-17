"""
Command-line interface for the static site generator.

This module provides the CLI commands for building and managing static sites.
"""

import argparse
import sys
from pathlib import Path

from .generator.core import SiteGenerator


def cmd_build(args):
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


def cmd_init(args):
    """
    Initialize new site project (future feature).

    Args:
        args: Parsed command-line arguments
    """
    print("Init command not yet implemented")
    return 1


def create_parser():
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


def main():
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = create_parser()

    if len(sys.argv) == 1:
        parser.print_help()
        return 1

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
