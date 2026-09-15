"""Build-time checks over the arranged content, one per ``warn.*`` config key.

Each check is a ``find_*`` returning what it found and a ``log_*`` writing one
warning per entry, opening with the subject the caller names (a slide number, a
figure file).
"""

from __future__ import annotations

import re
from typing import Iterable

from ..config import config
from ..core.element import Element, measure_all, union_bbox
from ..core.vec import Vec
from ..elements.group import Group
from ..elements.shapes import Arrow, Curve, Line, LineTo, MoveTo
from ..elements.spacing import HSpace, VSpace
from ..elements.text import Text
from ..log import logger
from ..parser import inlines_to_markdown, parse_markup
from ..parser.ir import Bold, Code, Inline, Italic, LineBreak, Math, TextRun
from .layout import Layout

# An overlap thinner than this in either axis is two boxes touching.
_TOLERANCE = 0.01  # cm

# Overlaps smaller than this are below what a reader sees.
_MIN_AREA = 0.01  # cm2

# Characters of an element's text kept in a report line.
_DESCRIPTION_LENGTH = 30

# One word of running text.
_WORD = re.compile(r"\S+")

Collision = tuple[Element, Element, float]
Overflow = tuple[str, float, float]
Widow = tuple[Text, int, str]


def find_overflows(layout: Layout) -> list[Overflow]:
    """Return the regions holding more than they fit, with the excess in cm.

    Reads the boxes the arrange pass measured, without a query of its own.
    """
    overflows: list[Overflow] = []
    for name, region in layout.regions.items():
        if not region.elements:
            continue
        _, _, width, height = union_bbox(region.elements)
        extra_width = width - region.width
        extra_height = height - region.height
        if extra_width > _TOLERANCE or extra_height > _TOLERANCE:
            overflows.append((name, extra_width, extra_height))
    return overflows


def log_overflows(overflows: list[Overflow], subject: str) -> None:
    """Log one warning per overflowing region, each line opening with ``subject``."""
    for name, extra_width, extra_height in overflows:
        excess = []
        if extra_width > _TOLERANCE:
            excess.append(f"{extra_width:.2f} cm wider")
        if extra_height > _TOLERANCE:
            excess.append(f"{extra_height:.2f} cm taller")
        logger.warning(
            rf"[yellow b]{subject}[/yellow b] content is "
            rf"{' and '.join(excess)} than region [magenta]{name}[/magenta]",
            extra={"markup": True, "highlighter": None},
        )


def _collect(
    el: Element,
    hidden_ids: set[int] | frozenset[int],
    arrow: Arrow | None,
    out: list[tuple[Element, Arrow | None]],
) -> None:
    """Gather the drawn nodes of ``el``'s subtree, each with its ``Arrow`` owner.

    A node that draws nothing of its own (a group, a spacer), one that does not
    hold a place (an inline run inside a text, an omitted element) and a hidden
    subtree are left out. The ``Arrow`` an element belongs to travels down with
    it: an arrow's shaft and its marker are one drawing.
    """
    if el.placement == "omitted" or el.hidden or id(el) in hidden_ids:
        return
    if el.placement == "fixed" and not isinstance(el, (Group, VSpace, HSpace)):
        out.append((el, arrow))
    owner = el if isinstance(el, Arrow) else arrow
    for child in el.children:
        _collect(child, hidden_ids, owner, out)


def _is_ancestor(el: Element, other: Element) -> bool:
    """Return whether ``el`` is an ancestor of ``other``."""
    node = other.parent
    while node is not None:
        if node is el:
            return True
        node = node.parent
    return False


def _ink_box(el: Element) -> tuple[float, float, float, float]:
    """Return the element's box grown by the ink its stroke lays outside it."""
    x, y, w, h = el.get_bbox()
    width = getattr(el, "stroke_width", None)
    if not width:
        return x, y, w, h
    return x, y, w + width, h + width


def _overlap_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    """Return the area shared by two centre-based boxes, ``0`` when they touch."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    width = min(ax + aw / 2, bx + bw / 2) - max(ax - aw / 2, bx - bw / 2)
    height = min(ay + ah / 2, by + bh / 2) - max(ay - ah / 2, by - bh / 2)
    if width <= _TOLERANCE or height <= _TOLERANCE:
        return 0.0
    return width * height


Segment = tuple[Vec, Vec]


def _segments_of(el: Element) -> list[Segment] | None:
    """Return the straight segments ``el`` draws, or ``None`` for a shape read as a box.

    A :class:`Line` is one segment. A :class:`Curve` of ``MoveTo`` and
    ``LineTo`` steps (an open arrow marker) is the polyline through them.
    """
    if isinstance(el, Line):
        return [(el.get_start(), el.get_end())]
    if isinstance(el, Curve):
        points: list[Vec] = []
        for segment in el.get_segments():
            if not isinstance(segment, (MoveTo, LineTo)):
                return None
            points.append(segment.point)
        return list(zip(points, points[1:]))
    return None


def _segment_crosses_box(
    segment: Segment, half_stroke: float, box: tuple[float, float, float, float]
) -> bool:
    """Return whether ``segment``, grown by ``half_stroke``, enters ``box``.

    Clips the segment against the box's four sides (Liang-Barsky); a
    segment that only grazes a side within the tolerance does not enter.
    """
    p, q = segment
    bx, by, bw, bh = box
    left = bx - bw / 2 - half_stroke + _TOLERANCE
    right = bx + bw / 2 + half_stroke - _TOLERANCE
    bottom = by - bh / 2 - half_stroke + _TOLERANCE
    top = by + bh / 2 + half_stroke - _TOLERANCE
    dx, dy = q.x - p.x, q.y - p.y
    t0, t1 = 0.0, 1.0
    for delta, low, high in ((dx, left - p.x, right - p.x), (dy, bottom - p.y, top - p.y)):
        if delta == 0:
            if low > 0 or high < 0:
                return False
            continue
        enter, leave = sorted((low / delta, high / delta))
        t0, t1 = max(t0, enter), min(t1, leave)
        if t0 >= t1:
            return False
    return True


def _segments_cross(a: Segment, b: Segment) -> bool:
    """Return whether two segments intersect."""
    p1, p2 = a
    q1, q2 = b

    def side(o: Vec, u: Vec, v: Vec) -> float:
        return (u.x - o.x) * (v.y - o.y) - (u.y - o.y) * (v.x - o.x)

    d1, d2 = side(q1, q2, p1), side(q1, q2, p2)
    d3, d4 = side(p1, p2, q1), side(p1, p2, q2)
    return d1 * d2 < 0 and d3 * d4 < 0


def _half_stroke(el: Element) -> float:
    """Return half the stroke width of ``el``, ``0`` for an unstroked one."""
    return (getattr(el, "stroke_width", None) or 0.0) / 2


def _cross(
    el: Element,
    bbox: tuple[float, float, float, float],
    other: Element,
    other_bbox: tuple[float, float, float, float],
) -> bool:
    """Return whether two drawn elements cross: by segment for a line or an open
    marker, by box for everything else."""
    segments, other_segments = _segments_of(el), _segments_of(other)
    if segments is not None and other_segments is not None:
        return any(_segments_cross(a, b) for a in segments for b in other_segments)
    if segments is not None:
        half = _half_stroke(el)
        return any(_segment_crosses_box(s, half, other_bbox) for s in segments)
    if other_segments is not None:
        half = _half_stroke(other)
        return any(_segment_crosses_box(s, half, bbox) for s in other_segments)
    return True


def _contains(
    outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]
) -> bool:
    """Return whether ``outer`` holds all of ``inner``."""
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return (
        ox - ow / 2 <= ix - iw / 2 + _TOLERANCE
        and ox + ow / 2 >= ix + iw / 2 - _TOLERANCE
        and oy - oh / 2 <= iy - ih / 2 + _TOLERANCE
        and oy + oh / 2 >= iy + ih / 2 - _TOLERANCE
    )


def find_collisions(
    roots: Iterable[Element], hidden_ids: set[int] | frozenset[int] = frozenset()
) -> list[Collision]:
    """Return the pairs of drawn boxes that cross, each with the shared area.

    A pair is reported when the two boxes overlap partially. One box holding
    the other is a deliberate arrangement (a label inside a shape, a slide
    background, the lines of a code block) and is left out, as are the pieces
    of a single arrow. The boxes are the measured bounding boxes, except that
    a :class:`Line` (an arrow's shaft included) is its segment: it reports
    against a box its stroke enters and against a segment it intersects, and
    a diagonal shaft passes the boxes its own box spans.

    Each box grows by the ink its stroke lays outside it, which gives a
    horizontal line the height a reader sees.

    Measures the elements whose box is cold; the pairs come out ordered by
    descending area.
    """
    bodies: list[tuple[Element, Arrow | None]] = []
    for root in roots:
        _collect(root, hidden_ids, None, bodies)
    cold = [el for el, _ in bodies if el._bbox is None]
    if cold:
        measure_all(cold)

    items = sorted(
        ((el, arrow, _ink_box(el)) for el, arrow in bodies),
        key=lambda item: item[2][0] - item[2][2] / 2,
    )
    collisions: list[Collision] = []
    active: list[tuple[Element, Arrow | None, tuple[float, float, float, float]]] = []
    for el, arrow, bbox in items:
        left = bbox[0] - bbox[2] / 2
        active = [item for item in active if item[2][0] + item[2][2] / 2 > left]
        for other, other_arrow, other_bbox in active:
            if arrow is not None and arrow is other_arrow:
                continue
            if _is_ancestor(el, other) or _is_ancestor(other, el):
                continue
            area = _overlap_area(bbox, other_bbox)
            if area < _MIN_AREA:
                continue
            if _contains(bbox, other_bbox) or _contains(other_bbox, bbox):
                continue
            if not _cross(el, bbox, other, other_bbox):
                continue
            collisions.append((other, el, area))
        active.append((el, arrow, bbox))
    collisions.sort(key=lambda c: c[2], reverse=True)
    return collisions


def _escape(text: str) -> str:
    """Escape the brackets of ``text`` for a rich-markup log line."""
    return text.replace("[", r"\[")


def _describe(el: Element) -> str:
    """Name an element for a report line."""
    name = type(el).__name__
    if el.id:
        label = f"{name} {el.id[0]!r}"
    elif isinstance(el, Text) and el.get_text():
        text = el.get_text()
        if len(text) > _DESCRIPTION_LENGTH:
            text = text[: _DESCRIPTION_LENGTH - 1] + "…"
        label = f"{name} {text!r}"
    else:
        label = f"{name} #{el._mid}"
    return _escape(label)


def log_collisions(collisions: list[Collision], subject: str) -> None:
    """Log one warning per collision, each line opening with ``subject``."""
    for a, b, area in collisions:
        logger.warning(
            rf"[yellow b]{subject}[/yellow b] [magenta]{_describe(a)}[/magenta] "
            rf"overlaps [magenta]{_describe(b)}[/magenta] over "
            rf"{area:.2f} cm2",
            extra={"markup": True, "highlighter": None},
        )


def _prose(el: Element, out: list[Text]) -> None:
    """Collect the wrapped texts of ``el``'s subtree.

    A text carrying a ``max_width`` is a paragraph the layout wraps. Verbatim
    runs (a code block's lines) and whole equations break where they break.
    """
    if el.placement == "omitted":
        return
    if (
        isinstance(el, Text)
        and el.max_width is not None
        and not el.verbatim
        and not el.is_math_run
    ):
        out.append(el)
        return
    for child in el.children:
        _prose(child, out)


def _leaves(el: Element, out: list[Element]) -> None:
    """Collect the childless nodes of ``el``'s subtree, in source order."""
    if not el.children:
        out.append(el)
        return
    for child in el.children:
        _leaves(child, out)


def _inline_words(nodes: list[Inline]) -> list[str]:
    """Return the words of an inline token list; a code or math span is one word."""
    words: list[str] = []
    for node in nodes:
        match node:
            case TextRun(text):
                words.extend(text.split())
            case Bold(children) | Italic(children):
                words.extend(_inline_words(children))
            case Code(text):
                words.append(f"`{text}`")
            case Math(raw, _):
                words.append(f"${raw}$")
    return words


def _words(text: Text) -> list[str]:
    """Return the words of a text, its spans included, in reading order."""
    leaves: list[Element] = []
    _leaves(text, leaves)
    words: list[str] = []
    for leaf in leaves:
        words.extend(_inline_words(parse_markup(leaf.content)))
    return words


def _has_line_break(text: Text) -> bool:
    """Return whether the text carries a line break the author wrote."""
    leaves: list[Element] = []
    _leaves(text, leaves)
    return any(
        isinstance(node, LineBreak)
        for leaf in leaves
        for node in parse_markup(leaf.content)
    )


def _drop_words(nodes: list[Inline], count: int) -> tuple[list[Inline], int]:
    """Return ``nodes`` without its last ``count`` words, and the count still owed.

    An emphasis emptied by the removal goes with its content, which keeps the
    markup balanced. A shortened run is cut at a word boundary, keeping the
    whitespace that separates it from the node before it.
    """
    kept: list[Inline] = []
    for node in reversed(nodes):
        if count == 0:
            kept.append(node)
            continue
        match node:
            case TextRun(text):
                starts = [m.start() for m in _WORD.finditer(text)]
                if len(starts) <= count:
                    count -= len(starts)
                    continue
                kept.append(TextRun(text[: starts[len(starts) - count]]))
                count = 0
            case Bold(children):
                inner, count = _drop_words(children, count)
                if inner:
                    kept.append(Bold(inner))
            case Italic(children):
                inner, count = _drop_words(children, count)
                if inner:
                    kept.append(Italic(inner))
            case Code() | Math():
                count -= 1
            case _:
                kept.append(node)
    kept.reverse()
    return kept, count


def _without_last_words(text: Text, count: int) -> Text:
    """Return a copy of ``text`` with its last ``count`` words removed."""
    clone = text.copy()
    leaves: list[Element] = []
    _leaves(clone, leaves)
    owed = count
    for leaf in reversed(leaves):
        if owed == 0:
            break
        nodes, owed = _drop_words(parse_markup(leaf.content), owed)
        leaf.content = inlines_to_markdown(nodes)
    return clone


def find_widows(elements: Iterable[Element], min_words: int) -> list[Widow]:
    """Return the paragraphs whose last line carries ``min_words`` words or fewer.

    Each paragraph is measured again with its last ``k`` words removed, for ``k``
    up to ``min_words``: the smallest ``k`` whose removal costs the paragraph a
    line is the number of words its last line carries. Typst breaks the lines
    both times, and every copy is measured in one pass.

    A paragraph carrying a hard line break is left out: its lines are the
    author's. So is a paragraph whose measure is under half the slide width
    (a grid column): its wrap is not steerable by rewording.
    """
    candidates: list[Text] = []
    for el in elements:
        _prose(el, candidates)
    narrow = config.slide_width / 2
    trials: list[tuple[Text, list[str], list[tuple[int, Text]]]] = []
    for text in candidates:
        words = _words(text)
        if len(words) <= min_words or _has_line_break(text) or text.max_width < narrow:
            continue
        shortened = [(k, _without_last_words(text, k)) for k in range(1, min_words + 1)]
        trials.append((text, words, shortened))
    if not trials:
        return []
    measure_all(
        [text for text, _, _ in trials]
        + [clone for _, _, shortened in trials for _, clone in shortened]
    )

    widows: list[Widow] = []
    for text, words, shortened in trials:
        height = text.get_height()
        for count, clone in shortened:
            if clone.get_height() < height - _TOLERANCE:
                widows.append((text, count, " ".join(words[-count:])))
                break
    return widows


def log_widows(widows: list[Widow], subject: str) -> None:
    """Log one warning per widowed paragraph, each line opening with ``subject``."""
    for text, count, words in widows:
        plural = "" if count == 1 else "s"
        logger.warning(
            rf"[yellow b]{subject}[/yellow b] the last line of "
            rf"[magenta]{_describe(text)}[/magenta] carries {count} word{plural}: "
            rf"[magenta]{_escape(repr(words))}[/magenta]",
            extra={"markup": True, "highlighter": None},
        )
