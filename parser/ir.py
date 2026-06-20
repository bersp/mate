"""Tokenized representation of a parsed Markdown document.

A :class:`ParsedDocument` is a list of :class:`ParsedSlide`s; each slide holds
its title and subtitle as inline tokens plus a list of body blocks. Blocks and
inlines are dataclasses so the later element-mapping step consumes a typed tree
rather than a backend-specific token stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    """Inline ``$...$`` math. ``raw`` is the Typst-syntax body, kept verbatim.

    Inline vs. display is carried by the token type, not by border whitespace:
    surrounding whitespace is trimmed so the markdown delimiter alone decides.
    """

    raw: str


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


Block = Paragraph | Heading | BulletList | OrderedList | MathBlock | MethodCall


# --- Document ---------------------------------------------------------------


@dataclass
class ParsedSlide:
    title: list[Inline] | None = None
    subtitle: list[Inline] | None = None
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ParsedDocument:
    slides: list[ParsedSlide] = field(default_factory=list)
