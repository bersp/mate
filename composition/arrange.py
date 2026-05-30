from __future__ import annotations

from ..core.element import Anchor, Element, anchor_offsets, measure_all
from ..core.vec import Vec, VecLike
from ..elements.shapes import Circle, Ellipse, Rectangle


def arrange(
    elements: list[Element],
    pos: VecLike,
    anchor: Anchor,
    *,
    gap: float = 0.0,
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

    Performance
    -----------
    Intrinsic-size primitives (:class:`Rectangle`, :class:`Circle`,
    :class:`Ellipse`) report their dimensions without measuring; every
    other element needs a measured bbox and is collected into a single
    batched :func:`measure_all` pass, so the whole call spends at most
    one Typst query regardless of N.

    Elements are mutated in place via :meth:`Element.move_to`, which
    forces ``placement="fixed"`` and preserves each element's anchor.
    """
    if not elements:
        return

    anchor_pos = Vec(pos)
    stack_h_mul, stack_v_mul = anchor_offsets(anchor)

    pending = [el for el in elements if not isinstance(el, _INTRINSIC_SIZE)]
    if pending:
        measure_all(pending)

    heights = [el.get_height() for el in elements]
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
