from __future__ import annotations

from typing import Literal

from ..core.element import Anchor, Element, anchor_offsets, measure_all
from ..core.vec import Vec, VecLike
from ..elements.shapes import Circle, Curve, Ellipse, Line, Polygon, Rectangle
from ..elements.spacing import HSpace, VSpace

# Fraction of the region's horizontal extent at which an element's
# matching bbox edge sits: left edge at 0, center at 0.5, right at 1.
ALIGN_FRACTION = {"left": 0.0, "center": 0.5, "right": 1.0}


def arrange(
    elements: list[Element],
    pos: VecLike,
    anchor: Anchor,
    *,
    gap: float = 0.0,
    width: float | None = None,
    direction: Direction = "column",
) -> None:
    """Stack ``elements`` in a single column, or a single row, with optional gap.

    The stack as a whole is anchored at ``pos`` with mode ``anchor``:
    the union bbox is positioned so that its ``anchor`` point lands at
    ``pos``. Elements are laid out in list order, top to bottom in a
    column and left to right in a row.

    In a row (``direction="row"``) the gap runs horizontally and the
    vertical half of ``anchor`` places every element within the row's
    height: ``top-*`` aligns the tops, ``center-*`` the centres,
    ``bottom-*`` the bottoms. ``width``, an element's ``align`` and its
    ``indent`` belong to the column form and play no part in a row.

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
    direction : {"column", "row"}, optional
        ``"column"`` (default) stacks top to bottom, ``"row"`` left to
        right.

    Performance
    -----------
    The intrinsic-size primitives (the shapes and the spacers, see
    :data:`_INTRINSIC_SIZE`) report their dimensions without measuring;
    every other element needs a measured bbox and is collected into a
    single batched :func:`measure_all` pass, so the whole call spends at
    most one Typst query regardless of N.

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

    if direction == "row":
        _arrange_row(elements, widths, heights, gaps, anchor_pos, stack_h_mul, stack_v_mul)
        return
    if direction != "column":
        raise ValueError(
            f"{direction!r} is not an arrange direction. Valid: column, row."
        )

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
        a = stack_h_mul if el.align is None else ALIGN_FRACTION[el.align]
        # Place the element so its left edge sits at `a` of the way
        # through the free space `extent - w`; `move_to` then honors the
        # element's own anchor to land that left edge.
        left_edge = left_x + a * (extent - w) + el.indent
        pos_x = left_edge + h_mul * w
        # bbox.bottom = y_cursor - h; pos_y = bbox.bottom + v_mul * h.
        pos_y = y_cursor - (1.0 - v_mul) * h
        # `offset` is the element's accumulated manual displacement (from
        # `shift`), added on top of the stack position.
        el.move_to((pos_x + el.offset.x, pos_y + el.offset.y))
        y_cursor -= h + (gaps[i] if i < len(gaps) else 0.0)


def _arrange_row(
    elements: list[Element],
    widths: list[float],
    heights: list[float],
    gaps: list[float],
    anchor_pos: Vec,
    stack_h_mul: float,
    stack_v_mul: float,
) -> None:
    """Lay ``elements`` left to right; the row's ``anchor`` point sits at ``anchor_pos``."""
    total_w = sum(widths) + sum(gaps)
    extent = max(heights)
    # The row's left edge is `stack_h_mul` of its width left of `anchor_pos.x`;
    # its top edge is `(1 - stack_v_mul)` of its height above `anchor_pos.y`.
    x_cursor = anchor_pos.x - stack_h_mul * total_w
    top_y = anchor_pos.y + (1.0 - stack_v_mul) * extent

    for i, (el, h, w) in enumerate(zip(elements, heights, widths)):
        h_mul, v_mul = anchor_offsets(el.anchor)
        # The element's top edge sits `(1 - stack_v_mul)` of the way down the
        # free space `extent - h`; `move_to` then honors the element's own
        # anchor to land it.
        top_edge = top_y - (1.0 - stack_v_mul) * (extent - h)
        pos_x = x_cursor + h_mul * w
        pos_y = top_edge - (1.0 - v_mul) * h
        el.move_to((pos_x + el.offset.x, pos_y + el.offset.y))
        x_cursor += w + (gaps[i] if i < len(gaps) else 0.0)


Direction = Literal["column", "row"]

_INTRINSIC_SIZE = (Rectangle, Circle, Ellipse, Line, Polygon, Curve, VSpace, HSpace)
_SPACER = (VSpace, HSpace)
