"""Build-time checks over the arranged content, one per ``warn.*`` config key.

Each check is a ``find_*`` returning what it found and a ``log_*`` writing one
warning per entry, opening with the subject the caller names (a slide number, a
figure file).
"""

from __future__ import annotations

from typing import Iterable

from ..core.element import Element, measure_all, union_bbox
from ..elements.group import Group
from ..elements.shapes import Arrow
from ..elements.spacing import HSpace, VSpace
from ..elements.text import Text
from ..log import logger
from .layout import Layout

# An overlap thinner than this in either axis is two boxes touching.
_TOLERANCE = 0.01  # cm

# Overlaps smaller than this are below what a reader sees.
_MIN_AREA = 0.01  # cm2

# Characters of an element's text kept in a report line.
_DESCRIPTION_LENGTH = 30

Collision = tuple[Element, Element, float]
Overflow = tuple[str, float, float]


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
    of a single arrow. The boxes are the measured bounding boxes: a diagonal
    line reports against the rectangle it spans.

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
            collisions.append((other, el, area))
        active.append((el, arrow, bbox))
    collisions.sort(key=lambda c: c[2], reverse=True)
    return collisions


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
    return label.replace("[", r"\[")


def log_collisions(collisions: list[Collision], subject: str) -> None:
    """Log one warning per collision, each line opening with ``subject``."""
    for a, b, area in collisions:
        logger.warning(
            rf"[yellow b]{subject}[/yellow b] [magenta]{_describe(a)}[/magenta] "
            rf"overlaps [magenta]{_describe(b)}[/magenta] over "
            rf"{area:.2f} cm2",
            extra={"markup": True, "highlighter": None},
        )
