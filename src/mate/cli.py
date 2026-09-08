"""Command-line entry point: ``mate <presentation.md>`` builds a PDF."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import Presentation, config
from .parser import ParsedSlide, parse_markdown


def _resolve_template(name: str, base_dir: Path) -> str:
    """Resolve a front-matter template entry against the Markdown file.

    A sibling ``<name>.py`` (``~`` expanded, relative to ``base_dir``) wins and
    yields its absolute path; otherwise ``name`` is kept as a built-in name.
    """
    candidate = (base_dir / Path(name).expanduser()).with_suffix(".py")
    return str(candidate.resolve()) if candidate.is_file() else name


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(
        prog="mate", description="Build a PDF from a Markdown deck."
    )
    parser.add_argument("source", type=Path, help="the deck's Markdown file")
    parser.add_argument(
        "--warn",
        action="store_true",
        help="run every build-time check of the deck (see the 'warn.*' config keys)",
    )
    return parser.parse_args()


def _enable_warnings() -> None:
    """Turn on every check of the ``warn`` namespace."""
    config.set_multiple(
        {
            key: True
            for key in config.keys_under("warn")
            if isinstance(config.get(key), bool)
        }
    )


def main() -> None:
    """Parse the command line and write the deck's slides to a PDF."""
    args = _parse_args()
    source_path = args.source
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
    # After the front matter, which the flag overrides.
    if args.warn:
        _enable_warnings()
    for item in doc.items:
        if isinstance(item, ParsedSlide):
            pres.new_slide()
            pres.add_parsed_slide(item)
            pres.end_slide()
        else:
            pres.on_directive(item)
    pres.write()
