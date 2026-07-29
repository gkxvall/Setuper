"""Root command-line application."""

import argparse
from collections.abc import Sequence

from setuper import __version__

DESCRIPTION = "Capture and restore reproducible work setups."


def build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser."""
    parser = argparse.ArgumentParser(prog="setuper", description=DESCRIPTION)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("version", help="show the installed Setuper version")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Setuper command-line application."""
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "version":
        print(f"setuper {__version__}")
        return 0

    parser.print_help()
    return 0
