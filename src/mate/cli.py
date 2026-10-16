"""Command-line entry point: ``mate <presentation.md>`` builds a PDF."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import runpy
import sys
import textwrap
import threading
import time
from importlib.metadata import distribution
from pathlib import Path

from . import Presentation, __all__ as api_names, config
from .backends.typst import _available_font_families
from .core.authoring import eval_call
from .log import logger
from .parser import FrontMatter, MethodCall, ParsedDocument, ParsedSlide, parse_markdown
from .templates import built_in_templates

_LLM_DOCS = Path(__file__).resolve().parent / "docs" / "llm_docs.md"
_PYPI_URL = "https://pypi.org/pypi/yerba/json"
_UPDATE_CHECK_INTERVAL = 24 * 60 * 60  # seconds between two PyPI requests


def _resolve_template(name: str, base_dir: Path) -> str:
    """Resolve a front-matter template entry against the Markdown file.

    A sibling ``<name>.py`` (``~`` expanded, relative to ``base_dir``) wins and
    yields its absolute path; otherwise ``name`` is kept as a built-in name.
    """
    candidate = (base_dir / Path(name).expanduser()).with_suffix(".py")
    return str(candidate.resolve()) if candidate.is_file() else name


class _PrintVersion(argparse.Action):
    """Print the installed version and exit, reading it only when asked."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        print(f"mate {distribution('yerba').version}")
        parser.exit()


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(
        prog="mate", description="Build a PDF from a Markdown deck."
    )
    parser.add_argument("source", type=Path, nargs="?", help="the deck's Markdown file")
    parser.add_argument(
        "--version",
        action=_PrintVersion,
        nargs=0,
        help="print the installed version of mate, then exit",
    )
    parser.add_argument(
        "--warn",
        action="store_true",
        help="run every build-time check of the deck (see the 'warn.*' config keys)",
    )
    parser.add_argument(
        "--png",
        action="store_true",
        help="write one PNG per page, <deck>-<n>.png, instead of the PDF",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        metavar="DIR",
        help="the directory the build writes to, the deck's own by default",
    )
    parser.add_argument(
        "--figure",
        type=Path,
        metavar="FILE",
        help="run a figure file as a script under the deck's front matter "
        "(templates, palette, config), then exit",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="print the templates, config keys, colors, commands, regions, fonts "
        "and API names available, then exit; with a deck given, the listing is "
        "the one that deck builds with",
    )
    parser.add_argument(
        "--llm-docs",
        action="store_true",
        help="print the documentation written for a language model that authors "
        "decks, then exit",
    )
    args = parser.parse_args()
    if args.source is None and not (args.info or args.llm_docs):
        parser.error("the deck's Markdown file is required")
    if args.out is not None and not args.out.is_dir():
        parser.error(f"--out: no such directory: {args.out}")
    return args


def load_deck(source_path: Path) -> ParsedDocument:
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
        frontmatter = load_deck(source_path).frontmatter
    presentation = Presentation("info", frontmatter=frontmatter)

    scope = (
        f"resolved for {source_path}"
        if source_path is not None
        else "no deck given: a deck with no front matter"
    )
    print(f"mate ({scope})")

    _print_section(
        "TEMPLATES",
        [
            f"built-in: {', '.join(built_in_templates())}",
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

    directives = presentation_class._declared_directive_properties()
    from_templates = [
        name for name in directives if name not in Presentation.directive_properties
    ]
    width = max(len(name) for name in directives)
    _print_section(
        "DIRECTIVES",
        [f"{name:<{width}}  {directives[name]}" for name in directives]
        + [f"added by the loaded templates: {', '.join(from_templates) or 'none'}"],
    )

    _print_section(
        "REGIONS",
        [f"{name}: {region!r}" for name, region in presentation.layout.regions.items()],
    )

    _print_section("FONTS", _wrapped(sorted(_available_font_families())))
    _print_section("API NAMES", _wrapped(list(api_names)))


def _run_figure(path: Path, frontmatter: FrontMatter) -> None:
    """Run the figure file ``path`` as ``__main__`` with ``frontmatter`` applied.

    Building a presentation on the front matter runs the templates' ``setup``
    and the deck's ``config`` and ``colors``, the state a ``> add mate figure``
    line embeds the file under; the file's own ``write`` then compiles the
    drawing against the deck's palette.
    """
    if not path.is_file():
        raise ValueError(f"--figure: no such file: {str(path)!r}")
    Presentation("figure", frontmatter=frontmatter)
    directory = str(path.resolve().parent)
    sys.path.insert(0, directory)
    try:
        runpy.run_path(str(path), run_name="__main__")
    finally:
        sys.path.remove(directory)


def _declared_slide_total(doc: ParsedDocument) -> int:
    """Return the number of ``#`` headings in ``doc`` plus every
    ``> adjust slide count`` delta its slides carry: the value the slide
    counter reaches when the deck builds."""
    deltas = sum(
        eval_call(block.args, lambda delta: delta)
        for slide in doc.slides
        for block in slide.blocks
        if isinstance(block, MethodCall) and block.name == "adjust_slide_count"
    )
    return len(doc.slides) + deltas


def _update_check_file() -> Path:
    """Return the file holding the latest release found on PyPI and when."""
    cache_home = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(cache_home) / "mate" / "update_check.json"


def _release_parts(release: str) -> tuple[int, ...]:
    """Return the numbers of a ``major.minor.patch`` release string."""
    return tuple(int(part) for part in re.findall(r"\d+", release)[:3])


def _store_latest_release(path: Path) -> None:
    """Ask PyPI for the latest ``yerba`` release and store it with the time.

    A failure (no network, PyPI down, an unwritable cache) leaves the file as
    it is, and the next run asks again.
    """
    from urllib.request import urlopen

    try:
        with urlopen(_PYPI_URL, timeout=2) as response:
            latest = json.load(response)["info"]["version"]
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial")
        partial.write_text(
            json.dumps({"checked_at": time.time(), "latest": latest}), encoding="utf-8"
        )
        partial.replace(path)
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        pass


def _update_notice() -> str | None:
    """Return the update notice from the last PyPI check, or ``None``.

    The notice names a release newer than the installed one. A check older than
    a day starts a new one in a background thread, read by the next run. An
    editable install and a set ``MATE_NO_UPDATE_CHECK`` skip both.
    """
    if os.environ.get("MATE_NO_UPDATE_CHECK"):
        return None
    installed = distribution("yerba")
    direct_url = installed.read_text("direct_url.json")
    if direct_url and json.loads(direct_url).get("dir_info", {}).get("editable"):
        return None
    path = _update_check_file()
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    if time.time() - stored.get("checked_at", 0) > _UPDATE_CHECK_INTERVAL:
        threading.Thread(
            target=_store_latest_release, args=(path,), daemon=True
        ).start()
    latest = stored.get("latest")
    if latest is None or _release_parts(latest) <= _release_parts(installed.version):
        return None
    return (
        rf"[yellow b]Update[/yellow b] mate {latest} is available "
        rf"(installed: {installed.version}): pip install -U yerba"
    )


def main() -> None:
    """Parse the command line and write the deck's slides to a PDF."""
    args = _parse_args()
    if args.llm_docs:
        print(_LLM_DOCS.read_text(encoding="utf-8"))
        return
    if args.info:
        _print_info(args.source)
        return
    source_path = args.source
    doc = load_deck(source_path)
    if args.figure is not None:
        _run_figure(args.figure, doc.frontmatter)
        return
    update_notice = _update_notice()
    pres = Presentation(
        str(source_path.with_suffix("")),
        total_slides=_declared_slide_total(doc),
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
            pres.run_directive(item)
    out_dir = args.out if args.out is not None else source_path.parent
    name = f"{source_path.stem}-{{n}}.png" if args.png else f"{source_path.stem}.pdf"
    pres.write(out_dir / name)
    if update_notice is not None:
        logger.info(update_notice, extra={"markup": True, "highlighter": None})
