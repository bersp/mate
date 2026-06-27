"""Tokenized representation of a parsed Markdown document.

A :class:`ParsedDocument` holds a :class:`FrontMatter` config block and a list
of :class:`ParsedSlide`s; each slide holds its title and subtitle as inline
tokens plus a list of body blocks. Blocks and inlines are dataclasses so the
later element-mapping step consumes a typed tree rather than a backend-specific
token stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.topic import Topic

# --- Inline tokens ----------------------------------------------------------


@dataclass
class TextRun:
    text: str


@dataclass
class Bold:
    children: list[Inline]


@dataclass
class Italic:
    children: list[Inline]


@dataclass
class Code:
    """Inline code span. ``text`` is the raw span content."""

    text: str


@dataclass
class Math:
    """``$...$`` (inline) or ``$$...$$`` (display) math.

    ``raw`` is the Typst-syntax body, kept verbatim; ``display`` selects block
    vs inline rendering. Surrounding whitespace is trimmed; the markdown
    delimiter alone decides inline vs display.
    """

    raw: str
    display: bool = False


Inline = TextRun | Bold | Italic | Code | Math


# --- Block tokens -----------------------------------------------------------


@dataclass
class Paragraph:
    inlines: list[Inline]


@dataclass
class Heading:
    """In-body heading. The ``#``/``##`` that open a slide's title and subtitle
    are consumed by the parser and never appear as a ``Heading``."""

    level: int
    inlines: list[Inline]


@dataclass
class ListItem:
    blocks: list[Block]


@dataclass
class BulletList:
    items: list[ListItem]


@dataclass
class OrderedList:
    start: int
    items: list[ListItem]


@dataclass
class MathBlock:
    """Display ``$$...$$`` math. ``raw`` is the Typst-syntax body, kept verbatim
    (surrounding whitespace trimmed)."""

    raw: str


@dataclass
class MethodCall:
    """A blockquote call to a presentation method.

    Written as one blockquote line, ``> method name : args`` (or just
    ``> method name`` with no arguments). ``name`` is the text before ``:``
    stripped and with its inner spaces turned into underscores; ``args`` is
    the verbatim text after ``:``, stripped, and empty for a no-argument call.
    ``args`` is spliced into a ``name(args)`` expression and evaluated when the
    slide is rendered.
    """

    name: str
    args: str


@dataclass
class FencedBlock:
    """A ``markdown <name> : args`` fenced block with a parsed body.

    ``name`` selects the directive (e.g. ``fragment``, ``overwrite``), dispatched
    to the matching ``add_<name>`` method with ``blocks`` and the verbatim
    ``args`` from the fence info string.
    """

    name: str
    args: str
    blocks: list[Block]


Block = (
    Paragraph
    | Heading
    | BulletList
    | OrderedList
    | MathBlock
    | MethodCall
    | FencedBlock
)


# --- Document ---------------------------------------------------------------


@dataclass
class ParsedSlide:
    title: list[Inline] | None = None
    subtitle: list[Inline] | None = None
    topic: Topic | None = None
    blocks: list[Block] = field(default_factory=list)


@dataclass
class FrontMatter:
    """A document's leading YAML config block.

    ``templates`` names the template files to inherit (see
    ``config.templates``); ``config`` maps dotted config keys to override
    values; ``colors`` maps palette names to hex strings; ``font_paths``
    lists extra font directories (see ``config.font_paths``).
    """

    templates: list[str] = field(default_factory=list)
    config: dict[str, object] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=dict)
    font_paths: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    slides: list[ParsedSlide] = field(default_factory=list)
    frontmatter: FrontMatter = field(default_factory=FrontMatter)
