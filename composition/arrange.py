from __future__ import annotations

from ..core.element import Anchor, Element, anchor_offsets, measure_all
from ..core.vec import Vec, VecLike
from ..elements.shapes import Circle, Ellipse, Line, Rectangle
from ..elements.spacing import HSpace, VSpace

# Fraction of the region's horizontal extent at which an element's
# matching bbox edge sits: left edge at 0, center at 0.5, right at 1.
_ALIGN_FRACTION = {"left": 0.0, "center": 0.5, "right": 1.0}


def arrange(
    elements: list[Element],
    pos: VecLike,
    anchor: Anchor,
    *,
    gap: float = 0.0,
    width: float | None = None,
) -> None:
    """Stack ``elements`` in a single column with optional gap.

    The stack as a whole is anchored at ``pos`` with mode ``anchor``:
    the union bbox is positioned so that its ``anchor`` point lands at
    ``pos``. Elements are laid out in list order, top to bottom.

    Horizontal alignment is per element: each one is placed within the
    region's horizontal extent according to its own
    :attr:`~mate.core.element.Element.align` (``"left"``/``"center"``/
    ``"right"``), falling back to the horizontal half of ``anchor`` when
    ``align`` is ``None``. So a left-anchored region can still hold a
    centered image among left-flush text. The extent is ``width``
    (defaulting to the widest element when omitted), positioned so that
    the stack's ``anchor`` edge lands at ``pos.x``.

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
        total height for anchoring purposes. No gap is inserted next to
        a spacer (:class:`~mate.elements.spacing.VSpace` /
        :class:`~mate.elements.spacing.HSpace`), so a spacer alone sets
        the space between its neighbours.
    width : float or None, optional
        Horizontal extent (in cm) within which each element's
        :attr:`~mate.core.element.Element.align` resolves. ``None``
        (default) uses the widest element's width, so per-element
        alignment still has an extent to act in for a standalone call.

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
    widths = [el.get_width() for el in elements]
    # A spacer *is* the spacing, so no gap is inserted on either side of
    # one: the gap between consecutive elements is dropped whenever either
    # neighbour is a spacer. `gaps[i]` is the space following element `i`.
    gaps = [
        0.0 if isinstance(a, _SPACER) or isinstance(b, _SPACER) else gap
        for a, b in zip(elements, elements[1:])
    ]
    total_h = sum(heights) + sum(gaps)

    # Horizontal extent the per-element `align` resolves within, and its
    # left edge: the stack's `anchor` edge is at `anchor_pos.x`, which is
    # `stack_h_mul` of the way across that extent.
    extent = max(widths) if width is None else width
    left_x = anchor_pos.x - stack_h_mul * extent
    # Slide coords are y-up: list order is top-to-bottom, so the cursor
    # starts at the stack's top edge and decreases by each element's
    # height (plus gap). Top edge = anchor_pos.y + (1 - v_mul) * total_h.
    y_cursor = anchor_pos.y + (1.0 - stack_v_mul) * total_h

    for i, (el, h, w) in enumerate(zip(elements, heights, widths)):
        h_mul, v_mul = anchor_offsets(el.anchor)
        align = el.get_effective_align()
        a = stack_h_mul if align is None else _ALIGN_FRACTION[align]
        # Place the element so its left edge sits at `a` of the way
        # through the free space `extent - w`; `move_to` then honors the
        # element's own anchor to land that left edge.
        left_edge = left_x + a * (extent - w) + el.indent
        pos_x = left_edge + h_mul * w
        # bbox.bottom = y_cursor - h; pos_y = bbox.bottom + v_mul * h.
        pos_y = y_cursor - (1.0 - v_mul) * h
        el.move_to((pos_x, pos_y))
        y_cursor -= h + (gaps[i] if i < len(gaps) else 0.0)


_INTRINSIC_SIZE = (Rectangle, Circle, Ellipse, Line, VSpace, HSpace)
_SPACER = (VSpace, HSpace)
