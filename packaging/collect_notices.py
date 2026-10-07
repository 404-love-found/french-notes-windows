"""Collect installed dependency license files into the Windows distribution."""

from __future__ import annotations

import argparse
from importlib import metadata
from pathlib import Path
import shutil
import sys


def collect(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for package in ("python-docx", "lxml", "typing_extensions", "pyinstaller"):
        distribution = metadata.distribution(package)
        destination = output / package
        destination.mkdir(exist_ok=True)
        copied = []
        for relative in distribution.files or []:
            if not any(word in relative.name.casefold() for word in ("license", "copying", "notice")):
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                target = destination / relative.name
                if target.exists() and target.read_bytes() != source.read_bytes():
                    target = destination / (str(relative).replace("/", "_").replace("\\", "_"))
                shutil.copyfile(source, target)
                copied.append(target.name)
        summaries.append(f"{package} {distribution.version}: " + ", ".join(copied))
        if not copied:
            (destination / "PACKAGE-METADATA.txt").write_text(str(distribution.metadata), encoding="utf-8")

    python_folder = output / "Python-and-Tcl-Tk"
    python_folder.mkdir(exist_ok=True)
    prefix = Path(sys.base_prefix)
    for license_name in ("LICENSE.txt", "LICENSE", "LICENSE.md"):
        source = prefix / license_name
        if source.is_file():
            shutil.copyfile(source, python_folder / source.name)
    tcl_folder = prefix / "tcl"
    if tcl_folder.exists():
        for source in tcl_folder.rglob("license.terms"):
            shutil.copyfile(source, python_folder / (source.parent.name + "-license.terms"))
    (output / "README.txt").write_text(
        "FrenchNotes — Licences des logiciels tiers\n\n"
        + f"Python {sys.version.split()[0]}\n"
        + "\n".join(summaries)
        + "\n\nLes textes des licences conservent les conditions et les mentions de leurs auteurs respectifs.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    collect(parser.parse_args().output)
