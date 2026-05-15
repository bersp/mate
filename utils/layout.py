from __future__ import annotations

from ..core.element import Element, anchor_offsets, measure_all
from ..elements.shapes import Circle, Ellipse, Rectangle
from ..elements.text import Text


def arrange(elements: list[Element], line_height: bool = False) -> None:
    """Stack elements in a single column, top-to-bottom, bboxes flush.

    The first element stays where it is and defines the anchor of the
    stack: every subsequent element is moved so its bbox top-left meets
    the previous element's bbox bottom-left, and all bboxes share the
    first element's left ``x``. Consecutive bboxes touch with zero gap.

    Parameters
    ----------
    elements : list[Element]
        Elements to stack, in top-to-bottom order.
    line_height : bool, optional
        When ``True``, :class:`~mate.elements.text.Text` heights come
        from the font-determined line slot (see
        :meth:`Text.get_line_height`) instead of the bbox height. The
        slot is cached per ``(font, size)`` so a stack of N homogeneous
        texts spends one measurement total for height. Non-Text
        elements still use :meth:`Element.get_height`.

    Performance
    -----------
    Width measurements are skipped for any element whose anchor is on
    the left edge (``"top-left"``, ``"center-left"``,
    ``"bottom-left"``). Heights come from intrinsic fields for shape
    primitives (:class:`Rectangle`, :class:`Circle`, :class:`Ellipse`)
    and from the cached line-height for :class:`Text` when
    ``line_height=True``. Any remaining elements that genuinely need
    a bbox (non-left anchors, or :class:`Text` with
    ``line_height=False``, or custom non-intrinsic subclasses) are
    measured together in **one** :func:`measure_all` pass before the
    positioning loop, so the whole call spends at most one Typst
    subprocess for size regardless of N.

    Elements are mutated in place via :meth:`Element.move_to`, which
    forces ``placement="fixed"`` and preserves each element's anchor.
    """
    if not elements:
        return

    pending = [el for el in elements if _needs_bbox(el, line_height)]
    if pending:
        measure_all(pending)

    heights = [_height(el, line_height) for el in elements]

    first = elements[0]
    h_mul0, v_mul0 = anchor_offsets(first.anchor)
    x0 = first.pos.x if h_mul0 == 0 else first.pos.x - h_mul0 * first.get_width()
    top0 = first.pos.y - v_mul0 * heights[0]
    y_cursor = top0 + heights[0]

    for el, h in zip(elements[1:], heights[1:]):
        h_mul, v_mul = anchor_offsets(el.anchor)
        pos_x = x0 if h_mul == 0 else x0 + h_mul * el.get_width()
        pos_y = y_cursor + v_mul * h
        el.move_to((pos_x, pos_y))
        y_cursor += h


_INTRINSIC_SIZE = (Rectangle, Circle, Ellipse)


def _needs_bbox(el: Element, line_height: bool) -> bool:
    """``True`` if ``arrange`` will end up reading a measured bbox for ``el``.

    The positioning loop reads ``get_width`` only for non-left-anchored
    elements, and ``get_height`` only for elements without an intrinsic
    height (everything that isn't a shape primitive or a Text under
    ``line_height=True``).
    """
    if anchor_offsets(el.anchor)[0] != 0:
        return True
    if isinstance(el, _INTRINSIC_SIZE):
        return False
    if isinstance(el, Text) and line_height:
        return False
    return True


def _height(el: Element, line_height: bool) -> float:
    """Return the stacking height of ``el`` under the current mode."""
    if line_height and isinstance(el, Text):
        return el.get_line_height()
    return el.get_height()
