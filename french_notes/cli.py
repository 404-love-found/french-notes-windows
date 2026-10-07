"""Launch the desktop app or validate a packaged executable."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local French notes with CSV storage and Word export")
    parser.add_argument("--version", action="version", version=f"FrenchNotes {__version__}")
    parser.add_argument("--self-test", metavar="NEW_DIRECTORY", type=Path, help="Validate the packaged app in a new temporary directory")
    args = parser.parse_args(argv)
    if args.self_test is not None:
        from .smoke import run_self_test

        return run_self_test(args.self_test)
    from .ui import main as launch_app

    launch_app()
    return 0
