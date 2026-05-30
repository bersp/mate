from __future__ import annotations

from ..core.element import Anchor, Element, anchor_offsets, measure_all
from ..core.vec import Vec, VecLike
from ..elements.shapes import Circle, Ellipse, Rectangle
from ..elements.text import Text


def arrange(
    elements: list[Element],
    pos: VecLike,
    anchor: Anchor,
    *,
    gap: float = 0.0,
    line_height: bool = True,
) -> None:
    """Stack ``elements`` in a single column with optional gap.

    The stack as a whole is anchored at ``pos`` with mode ``anchor``:
    the union bbox is positioned so that its ``anchor`` point lands at
    ``pos``. Elements are laid out in list order, top to bottom.

    Horizontal alignment within the stack is driven by the horizontal
    half of ``anchor``:

    - ``"*-left"``   — all bboxes share the same left ``x`` (= ``pos.x``).
    - ``"*-center"`` — all bboxes share the same center ``x``.
    - ``"*-right"``  — all bboxes share the same right ``x``.

    The vertical half decides where ``pos.y`` sits in the stack
    (slide coords are y-up, so the list's first element is at the
    larger y):

    - ``"top-*"``    — ``pos.y`` is the stack's top edge.
    - ``"center-*"`` — ``pos.y`` is the stack's vertical center.
    - ``"bottom-*"`` — ``pos.y`` is the stack's bottom edge.

    Each element is placed via :meth:`Element.move_to`, which honors
    that element's own anchor.

    Parameters
    ----------
    elements : list[Element]
        Elements to stack, in top-to-bottom order.
    pos : VecLike
        Slide coordinate (in cm) at which the stack is anchored.
    anchor : Anchor
        Anchor mode for the stack as a whole. One of ``"top-left"``,
        ``"top-center"``, ``"top-right"``, ``"center-left"``,
        ``"center"``, ``"center-right"``, ``"bottom-left"``,
        ``"bottom-center"``, ``"bottom-right"``.
    gap : float, optional
        Vertical space (in cm) inserted between consecutive bboxes.
        Defaults to ``0`` (bboxes touch). Counts towards the stack's
        total height for anchoring purposes.
    line_height : bool, optional
        When ``True``, :class:`~mate.elements.text.Text` heights come
        from the font-determined line slot (see
        :meth:`Text.get_line_height`) instead of the bbox height. The
        slot is cached per ``(font, size)`` so a stack of N homogeneous
        texts spends one measurement total for height. Non-Text
        elements still use :meth:`Element.get_height`.

    Performance
    -----------
    Heights are always required for every element to size the stack.
    Width measurements are skipped for any element whose anchor shares
    the same horizontal half as ``anchor`` (e.g. ``"top-left"``
    elements in a ``"top-left"`` stack, ``"center-right"`` elements in
    a ``"bottom-right"`` stack). Intrinsic-size primitives
    (:class:`Rectangle`, :class:`Circle`, :class:`Ellipse`) and
    :class:`Text` under ``line_height=True`` never trigger a
    measurement. Any element that genuinely needs a measured bbox is
    collected and passed to :func:`measure_all` in a single batched
    pass, so the whole call spends at most one Typst query
    regardless of N.

    Elements are mutated in place via :meth:`Element.move_to`, which
    forces ``placement="fixed"`` and preserves each element's anchor.
    """
    if not elements:
        return

    anchor_pos = Vec(pos)
    stack_h_mul, stack_v_mul = anchor_offsets(anchor)

    pending = [el for el in elements if _needs_bbox(el, line_height, stack_h_mul)]
    if pending:
        measure_all(pending)

    heights = [_height(el, line_height) for el in elements]
    total_h = sum(heights) + gap * (len(elements) - 1)

    x0 = anchor_pos.x
    # Slide coords are y-up: list order is top-to-bottom, so the cursor
    # starts at the stack's top edge and decreases by each element's
    # height (plus gap). Top edge = anchor_pos.y + (1 - v_mul) * total_h.
    y_cursor = anchor_pos.y + (1.0 - stack_v_mul) * total_h

    for el, h in zip(elements, heights):
        h_mul, v_mul = anchor_offsets(el.anchor)
        if h_mul == stack_h_mul:
            pos_x = x0
        else:
            pos_x = x0 + (h_mul - stack_h_mul) * el.get_width()
        # bbox.bottom = y_cursor - h; pos_y = bbox.bottom + v_mul * h.
        pos_y = y_cursor - (1.0 - v_mul) * h
        el.move_to((pos_x, pos_y))
        y_cursor -= h + gap


_INTRINSIC_SIZE = (Rectangle, Circle, Ellipse)


def _needs_bbox(el: Element, line_height: bool, stack_h_mul: float) -> bool:
    """Return ``True`` if ``arrange`` will read a measured bbox for ``el``.

    The positioning loop reads ``get_width`` only for elements whose
    horizontal anchor half differs from the stack's, and ``get_height``
    for every element. Intrinsic-size shapes report both dimensions
    without measuring; a single-line :class:`Text` under
    ``line_height=True`` reports height from the cached line slot but
    still needs measurement for width. A :class:`Text` with
    ``max_width`` wraps to several lines, so its height is the measured
    bbox and the line-slot shortcut does not apply.
    """
    if isinstance(el, _INTRINSIC_SIZE):
        return False
    needs_w = anchor_offsets(el.anchor)[0] != stack_h_mul
    if line_height and isinstance(el, Text) and el.max_width is None:
        return needs_w
    return True


def _height(el: Element, line_height: bool) -> float:
    """Return the stacking height of ``el`` under the current mode.

    The cached line slot is used only for a single-line :class:`Text`;
    a wrapped (``max_width``) Text reports its full measured height.
    """
    if line_height and isinstance(el, Text) and el.max_width is None:
        return el.get_line_height()
    return el.get_height()
