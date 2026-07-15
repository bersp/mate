"""Code element: source text rendered as mate primitives.

A :class:`Code` is a :class:`~mate.elements.group.Group` holding a background
:class:`~mate.elements.shapes.Rectangle`, one monospace
:class:`~mate.elements.text.Text` per source line, and (optionally) one Text
per line number. Syntax highlighting runs in Python: Pygments tokenizes the
source and each token role is styled with the property dict the ``code.theme``
config maps it to. The backend receives plain styled text and shapes.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from pygments.lexers import get_lexer_by_name
from pygments.token import Comment, Keyword, Name, Number, String
from pygments.util import ClassNotFound

from ..config import config
from ..core.element import Anchor, HAlign, Placement, measure_all
from ..core.registry import IDKey
from ..core.vec import VecLike
from .group import Group
from .shapes import Rectangle
from .text import Text, _match_bracket, _parse_markup_props

_PT_TO_CM = 2.54 / 72.0

# A ``[body][props]`` pair is markup only when the second bracket reads as
# keyword properties; any other bracket pair (indexing, list literals) is code.
_PROPS_START_RE = re.compile(r"\s*[A-Za-z_]\w*\s*=")

# Pygments token classes mapped to the ``code.theme`` roles, checked in order
# (subtypes match their parent class, e.g. ``String.Doc`` is a ``string``).
_TOKEN_ROLES = (
    (Comment, "comment"),
    (String, "string"),
    (Number, "number"),
    (Name.Function, "function"),
    (Name.Class, "function"),
    (Name.Builtin, "builtin"),
    (Name.Decorator, "decorator"),
    (Keyword, "keyword"),
)


def _token_role(ttype) -> str | None:
    """Return the ``code.theme`` role of a Pygments token type, or ``None``."""
    for token_type, role in _TOKEN_ROLES:
        if ttype in token_type:
            return role
    return None


@dataclass
class _Interval:
    """A styled range of the plain source: ``props`` applies to it."""

    start: int
    end: int
    props: dict


def _scan_source(source: str) -> tuple[str, list[_Interval], list[int]]:
    r"""Scan a code ``source`` into plain text, styled spans, and reveal breaks.

    The only escape is ``\||``, yielding a literal ``||``; every backslash
    stays literal otherwise, since backslashes are ordinary characters in
    code. A ``||`` outside a span is a reveal marker: it is dropped from the
    plain text and its position recorded as a break. A ``[body][props]`` pair
    whose ``props`` reads as keyword properties becomes a styled span over
    ``body``; any other bracket pair stays literal code. Returns
    ``(plain, spans, breaks)`` with span and break positions as offsets into
    ``plain``.
    """
    plain: list[str] = []
    length = 0
    spans: list[_Interval] = []
    breaks: list[int] = []
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if c == "\\" and source.startswith("||", i + 1):
            plain.append("||")
            length += 2
            i += 3
            continue
        if source.startswith("||", i):
            breaks.append(length)
            i += 2
            continue
        if c == "[":
            j = _match_bracket(source, i)
            if j is not None and j + 1 < n and source[j + 1] == "[":
                k = _match_bracket(source, j + 1)
                props = None if k is None else source[j + 2 : k]
                if props is not None and _PROPS_START_RE.match(props):
                    body = source[i + 1 : j].replace("\\||", "||")
                    parsed = _parse_markup_props(props)
                    spans.append(_Interval(length, length + len(body), parsed))
                    plain.append(body)
                    length += len(body)
                    i = k + 1
                    continue
        plain.append(c)
        length += 1
        i += 1
    return "".join(plain), spans, breaks


def _theme_intervals(plain: str, language: str, theme: dict) -> list[_Interval]:
    """Tokenize ``plain`` with Pygments and style each token from ``theme``.

    An empty ``language`` yields no intervals (plain text). A ``language``
    with no Pygments lexer raises :class:`ValueError`.
    """
    if not language:
        return []
    try:
        lexer = get_lexer_by_name(language, stripnl=False, ensurenl=False)
    except ClassNotFound:
        raise ValueError(
            f"unknown code language {language!r}: not a Pygments lexer name "
            "(e.g. 'python', 'c', 'bash'); omit the language for plain text"
        ) from None
    out: list[_Interval] = []
    for index, ttype, value in lexer.get_tokens_unprocessed(plain):
        if not value:
            continue
        role = _token_role(ttype)
        props = theme.get(role) if role is not None else None
        if props:
            out.append(_Interval(index, index + len(value), props))
    return out


def _word_intervals(plain: str, words: dict[str, dict]) -> list[_Interval]:
    """Style every whole-word occurrence of each ``words`` entry.

    A key that starts and ends with a word character matches at word
    boundaries; any other key matches every literal occurrence.
    """
    out: list[_Interval] = []
    for word, props in words.items():
        if not isinstance(props, dict):
            raise ValueError(
                f"words[{word!r}] must be a dict of properties "
                f"(e.g. {{'color': 'red'}}), got {props!r}"
            )
        pattern = re.escape(word)
        if word and word[0].isidentifier():
            pattern = rf"\b{pattern}"
        if word and (word[-1].isalnum() or word[-1] == "_"):
            pattern = rf"{pattern}\b"
        for match in re.finditer(pattern, plain):
            out.append(_Interval(match.start(), match.end(), props))
    return out


class Code(Group):
    r"""Source code rendered as a background box, monospace lines, and numbers.

    ``[body][<props>]`` styling spans and ``||`` reveal markers work inside
    the source as they do in :class:`Text`; everything else is verbatim (no
    Markdown markup, exact spacing):

    - A bracket pair is a span only when ``<props>`` reads as keyword
      properties (``[x][color="red"]``); pairs that read as code
      (``a[i][j]``) stay literal. A span's properties apply to each styled
      run it covers, and ``id=`` registers those runs in
      :data:`~mate.core.registry.id_registry`.
    - ``||`` opens a reveal step for the rest of the block, which holds its
      space from the start. ``\||`` escapes the marker, yielding a literal
      ``||``; it is the only escape sequence, every other backslash is code.

    With a ``language``, Pygments tokenizes the source and each token role
    (keyword, string, comment, number, function, builtin, decorator) is styled
    with the property dict ``code.theme`` maps it to. ``words`` styles
    whole-word matches on top of the theme, and explicit spans win over both.

    Parameters
    ----------
    source : str
        The code text. Tabs expand to 4 spaces; one trailing newline is
        dropped. Positional.
    language : str, optional
        Pygments lexer name (``"python"``, ``"c"``, ...). ``""`` (default)
        renders plain unhighlighted text.
    width : float or None, optional
        Background width in cm. ``None`` (default) hugs the longest line
        plus padding.
    font : str or None, optional
        Monospace font family. ``None`` reads ``code.font`` from the config.
    fontsize : float or None, optional
        Font size in points. ``None`` reads ``code.fontsize``.
    color : str or None, optional
        Base text color (palette name or hex). ``None`` reads ``code.color``.
    bg_color : str or None, optional
        Background fill (palette name or hex). ``None`` reads
        ``code.bg_color``.
    padding : float or None, optional
        Space in cm between the code and the background edges. ``None``
        reads ``code.padding``.
    corner_radius : float or None, optional
        Corner rounding radius of the background in cm. ``None`` reads
        ``code.corner_radius``.
    line_height : float or None, optional
        Vertical step between lines, in multiples of the font size. ``None``
        reads ``code.line_height``.
    numbers : bool or None, optional
        Show line numbers in a gutter left of the code. ``None`` reads
        ``code.numbers``.
    numbers_start : int or None, optional
        Number of the first line. ``None`` reads ``code.numbers_start``.
    words : dict or None, optional
        ``word -> props`` mapping styling every whole-word occurrence, e.g.
        ``{"x": {"color": "red", "style": "italic"}}``. Each props dict is
        applied through the ``set_<prop>`` methods of the matching runs.
    theme : dict or None, optional
        ``role -> props`` entries updating the ``code.theme`` mapping for
        this element: an entry replaces that role's properties, and roles
        left out keep their ``code.theme`` styling.
    pos, anchor, align, placement, id
        Keyword-only. See :class:`~mate.core.element.Element`.

    Attributes
    ----------
    reveal_segments : list[list[Element]]
        Nodes grouped by reveal segment when the source carries ``||``
        markers; empty otherwise.
    """

    def __init__(
        self,
        source: str,
        *,
        language: str = "",
        width: float | None = None,
        font: str | None = None,
        fontsize: float | None = None,
        color: str | None = None,
        bg_color: str | None = None,
        padding: float | None = None,
        corner_radius: float | None = None,
        line_height: float | None = None,
        numbers: bool | None = None,
        numbers_start: int | None = None,
        words: dict[str, dict] | None = None,
        theme: dict[str, dict] | None = None,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        super().__init__(
            pos=pos, anchor=anchor, align=align, placement=placement, id=id
        )
        font = config.get("code.font") if font is None else font
        fontsize = config.get("code.fontsize") if fontsize is None else fontsize
        color = config.get("code.color") if color is None else color
        bg_color = config.get("code.bg_color") if bg_color is None else bg_color
        padding = config.get("code.padding") if padding is None else padding
        corner_radius = (
            config.get("code.corner_radius") if corner_radius is None else corner_radius
        )
        line_height = (
            config.get("code.line_height") if line_height is None else line_height
        )
        numbers = config.get("code.numbers") if numbers is None else numbers
        numbers_start = (
            config.get("code.numbers_start") if numbers_start is None else numbers_start
        )
        theme = {**config.get("code.theme"), **(theme or {})}

        source = source.expandtabs(4)
        if source.endswith("\n"):
            source = source[:-1]
        plain, spans, breaks = _scan_source(source)
        intervals = (
            _theme_intervals(plain, language, theme)
            + _word_intervals(plain, words or {})
            + spans
        )

        # Property intervals contributing to each position, in application
        # order (theme, then words, then spans: the most specific wins).
        contribs: list[list[_Interval]] = [[] for _ in range(len(plain))]
        for interval in intervals:
            for position in range(interval.start, interval.end):
                contribs[position].append(interval)

        char_w, cap_h = _mono_metrics(font, fontsize)
        step = line_height * fontsize * _PT_TO_CM
        lines = plain.split("\n")

        gutter = 0.0
        if numbers:
            digits = len(str(numbers_start + len(lines) - 1))
            gutter = digits * char_w + 1.5 * char_w
        code_x = padding + gutter
        if width is None:
            width = code_x + max(len(li) for li in lines) * char_w + padding
        height = 2 * padding + len(lines) * step

        segment_nodes: list[list] = [[] for _ in range(len(breaks) + 1)]
        members: list = [
            Rectangle(
                width,
                height,
                corner_radius=corner_radius,
                fill_color=bg_color,
                pos=(0.0, 0.0),
                anchor="top-left",
            )
        ]
        offset = 0
        for line_index, line in enumerate(lines):
            top_y = -padding - line_index * step - (step - cap_h) / 2
            if numbers:
                number = Text(
                    str(numbers_start + line_index),
                    font=font,
                    fontsize=fontsize,
                    fill_color=config.get("code.numbers_color"),
                    pos=(padding + gutter - 1.5 * char_w, top_y),
                    anchor="top-right",
                )
                members.append(number)
                segment_nodes[bisect_right(breaks, offset)].append(number)
            leaves = self._line_leaves(
                line, offset, contribs, breaks, segment_nodes,
                font=font, fontsize=fontsize, color=color,
            )
            if leaves:
                text_line = Text(
                    None,
                    font=font,
                    fontsize=fontsize,
                    fill_color=color,
                    pos=(code_x, top_y),
                    anchor="top-left",
                )
                text_line._take_children(leaves)
                members.append(text_line)
            offset += len(line) + 1
        self._take_children(members)
        if breaks:
            self.reveal_segments = segment_nodes
        else:
            self.reveal_segments = []

    @staticmethod
    def _line_leaves(
        line: str,
        offset: int,
        contribs: list[list[_Interval]],
        breaks: list[int],
        segment_nodes: list[list],
        *,
        font: str,
        fontsize: float,
        color: str,
    ) -> list[Text]:
        """Build one line's leaf Texts, one per run of uniform style.

        A run is a maximal stretch of characters sharing the same contributing
        intervals and the same reveal segment. Each leaf is verbatim, carries
        the merged properties of its intervals, and is recorded under its
        segment in ``segment_nodes``.
        """
        leaves: list[Text] = []
        start = 0
        n = len(line)

        def run_key(column: int) -> tuple:
            position = offset + column
            return (
                tuple(map(id, contribs[position])),
                bisect_right(breaks, position),
            )

        while start < n:
            end = start + 1
            key = run_key(start)
            while end < n and run_key(end) == key:
                end += 1
            leaf = Text(
                None, font=font, fontsize=fontsize, fill_color=color,
                placement="inline",
            )
            leaf.content = line[start:end]
            leaf.verbatim = True
            merged: dict = {}
            for interval in contribs[offset + start]:
                merged.update(interval.props)
            for name, value in merged.items():
                leaf.apply_prop(name, value)
            leaves.append(leaf)
            segment_nodes[key[1]].append(leaf)
            start = end
        return leaves

    def _copy(self, mapping: dict) -> Code:
        # Remap the `reveal_segments` cross-references onto the clones, like
        # `Text._copy`.
        new = super()._copy(mapping)
        new.reveal_segments = [
            [mapping[id(node)] for node in seg] for seg in self.reveal_segments
        ]
        return new


_MONO_METRICS_CACHE: dict[tuple[str, float], tuple[float, float]] = {}


def _mono_metrics(font: str, fontsize: float) -> tuple[float, float]:
    """Return ``(advance width, cap height)`` in cm of a digit in ``font``.

    In a monospace font every glyph shares the digit's advance width, so one
    cached probe measurement sizes gutters and line widths for the whole
    process (the probe itself hits the persistent measure cache across runs).
    """
    key = (font, fontsize)
    metrics = _MONO_METRICS_CACHE.get(key)
    if metrics is None:
        probe = Text("0", font=font, fontsize=fontsize)
        measure_all([probe])
        metrics = (probe.get_width(), probe.get_height())
        _MONO_METRICS_CACHE[key] = metrics
    return metrics
