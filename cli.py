"""Command-line entry point: ``mate <presentation.md>`` builds a PDF."""

from __future__ import annotations

import sys
from pathlib import Path

from . import Presentation, config
from .parser import parse_markdown


def _resolve_template(name: str, base_dir: Path) -> str:
    """Resolve a front-matter template entry against the Markdown file.

    A sibling ``<name>.py`` (``~`` expanded, relative to ``base_dir``) wins and
    yields its absolute path; otherwise ``name`` is kept as a built-in name.
    """
    candidate = (base_dir / Path(name).expanduser()).with_suffix(".py")
    return str(candidate.resolve()) if candidate.is_file() else name


def main() -> None:
    """Parse the Markdown file in ``sys.argv`` and write the slides to a PDF."""
    if len(sys.argv) != 2:
        sys.exit("usage: mate <presentation.md>")

    source_path = Path(sys.argv[1])
    doc = parse_markdown(source_path.read_text(encoding="utf-8"))

    config.templates = [
        _resolve_template(t, source_path.parent) for t in doc.frontmatter.templates
    ]
    # Front-matter font directories expand a leading ~ and are otherwise
    # relative to the Markdown file.
    config.font_paths = [
        str((source_path.parent / Path(p).expanduser()).resolve())
        for p in doc.frontmatter.font_paths
    ]
    pres = Presentation(
        str(source_path.with_suffix("")),
        total_slides=len(doc.slides),
        frontmatter=doc.frontmatter,
    )
    prev_topic = None
    for parsed in doc.slides:
        topic = parsed.topic
        if topic is not None and topic is not prev_topic:
            pres.begin_topic(topic)
        prev_topic = topic
        pres.new_slide()
        pres.add_parsed_slide(parsed)
        pres.end_slide()
    pres.write()
