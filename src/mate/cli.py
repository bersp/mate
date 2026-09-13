"""Command-line entry point: ``mate <presentation.md>`` builds a PDF."""

from __future__ import annotations

import argparse
import pkgutil
import textwrap
from pathlib import Path

from . import Presentation, __all__ as api_names, config, templates
from .backends.typst import _available_font_families
from .parser import ParsedDocument, ParsedSlide, parse_markdown


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
    parser.add_argument("source", type=Path, nargs="?", help="the deck's Markdown file")
    parser.add_argument(
        "--warn",
        action="store_true",
        help="run every build-time check of the deck (see the 'warn.*' config keys)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="print the templates, config keys, colors, commands, regions, fonts "
        "and API names available, then exit; with a deck given, the listing is "
        "the one that deck builds with",
    )
    args = parser.parse_args()
    if args.source is None and not args.info:
        parser.error("the deck's Markdown file is required")
    return args


def _load_deck(source_path: Path) -> ParsedDocument:
    """Parse ``source_path`` and point the configuration at its front matter."""
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
    return doc


def _enable_warnings() -> None:
    """Turn on every check of the ``warn`` namespace."""
    config.set_multiple(
        {
            key: True
            for key in config.keys_under("warn")
            if isinstance(config.get(key), bool)
        }
    )


def _print_section(title: str, lines: list[str]) -> None:
    """Print a titled block of indented ``lines``."""
    print(f"\n{title}")
    for line in lines:
        print(f"  {line}")


def _wrapped(names: list[str]) -> list[str]:
    """Return ``names`` as comma-separated lines that fit a terminal width."""
    return textwrap.wrap(", ".join(names), width=86) or ["none"]


def _print_info(source_path: Path | None) -> None:
    """Print the names a deck can use, resolved against ``source_path``.

    With a deck given, its front matter is applied first and the listing
    carries the templates it loads, the keys and colors they define, the
    commands they add and the regions they build.
    """
    frontmatter = None
    if source_path is not None:
        frontmatter = _load_deck(source_path).frontmatter
    presentation = Presentation("info", frontmatter=frontmatter)

    scope = (
        f"resolved for {source_path}"
        if source_path is not None
        else "no deck given: a deck with no front matter"
    )
    print(f"mate ({scope})")

    built_in = sorted(
        module.name for module in pkgutil.iter_modules(templates.__path__)
    )
    _print_section(
        "TEMPLATES",
        [
            f"built-in: {', '.join(built_in)}",
            f"loaded: {', '.join(config.templates) or 'none'}",
        ],
    )

    values = config.items()
    width = max(len(key) for key in values)
    _print_section(
        "CONFIG KEYS", [f"{key:<{width}} = {values[key]!r}" for key in sorted(values)]
    )

    palette = config.colors.items()
    width = max(len(name) for name in palette)
    _print_section(
        "COLORS", [f"{name:<{width}} = {palette[name]}" for name in sorted(palette)]
    )

    presentation_class = type(presentation)
    commands = sorted(
        name
        for name in dir(presentation_class)
        if not name.startswith("_")
        and callable(getattr(presentation_class, name, None))
    )
    from_templates = [name for name in commands if not hasattr(Presentation, name)]
    _print_section(
        "COMMANDS",
        _wrapped(commands)
        + [f"added by the loaded templates: {', '.join(from_templates) or 'none'}"],
    )

    _print_section(
        "REGIONS",
        [f"{name}: {region!r}" for name, region in presentation.layout.regions.items()],
    )

    _print_section("FONTS", _wrapped(sorted(_available_font_families())))
    _print_section("API NAMES", _wrapped(list(api_names)))


def main() -> None:
    """Parse the command line and write the deck's slides to a PDF."""
    args = _parse_args()
    if args.info:
        _print_info(args.source)
        return
    source_path = args.source
    doc = _load_deck(source_path)
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
