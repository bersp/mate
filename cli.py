"""Command-line entry point: ``mate <presentation.md>`` builds a PDF."""

from __future__ import annotations

import sys
from pathlib import Path

from . import Presentation
from .parser import parse_markdown


def main() -> None:
    """Parse the Markdown file in ``sys.argv`` and write the slides to a PDF."""
    if len(sys.argv) != 2:
        sys.exit("usage: mate <presentation.md>")

    source_path = Path(sys.argv[1])
    doc = parse_markdown(source_path.read_text(encoding="utf-8"))

    pres = Presentation(str(source_path.with_suffix("")), total_slides=len(doc.slides))
    for parsed in doc.slides:
        pres.new_slide()
        pres.add_parsed_slide(parsed)
        pres.end_slide()
    pres.write()
