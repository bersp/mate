from __future__ import annotations

from typing import Iterable

from ..core.element import Anchor, Element, Placement, anchor_offsets
from ..core.registry import IDKey
from ..core.drawable import Drawable
from ..core.vec import Vec, VecLike


class Group(Drawable):
    """Composite container with no markup of its own.

    A :class:`Group` is a real tree node: its children are reparented
    to it on construction (or via :meth:`add`), its bbox is the union
    of the children's bboxes, and it participates in measurement and
    rendering like any element with no intrinsic markup. Movement
    (``move_to`` / ``shift``) follows the base :class:`Element`
    behavior — every fixed descendant translates as a unit.

    :class:`Group` inherits :class:`~mate.core.drawable.Drawable` purely
    so its ``set_fill_color`` / ``set_stroke_color`` / ... methods can
    bulk-overwrite the style of its subtree. The Group itself has no
    rendered body, so its own ``fill_color`` / ``stroke_color`` /
    ``fill_opacity`` / ``stroke_width`` are inert at render time — only
    the descendants' values matter.

    Parameters
    ----------
    children : iterable of :class:`Element`, optional
        Initial members. Each one's ``parent`` is set to this group.
        More can be appended later via :meth:`add`. Positional.
    pos, anchor, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.
    """

    def __init__(
        self,
        children: Iterable[Element] | None = None,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
    ) -> None:
        super().__init__(
            pos=pos,
            anchor=anchor,
            placement=placement,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
        )
        if children:
            self._take_children(list(children))

    def add(self, element: Element) -> Element:
        """Append ``element`` to the group, reparenting it.

        Invalidates the tree's bbox cache and returns ``element`` (not the
        group), so the freshly added child can be chained on.
        """
        element.parent = self
        self.children.append(element)
        self._invalidate_tree()
        return element

    def remove(self, element: Element) -> Element:
        """Detach ``element`` from the group, clearing its ``parent``.

        Invalidates the tree's bbox cache before unlinking, so the
        former subtree gets its own clean cache. Raises ``ValueError``
        if ``element`` is not a direct child of this group.

        Returns the removed element so the caller can re-attach it
        elsewhere.
        """
        if element.parent is not self:
            raise ValueError("element is not a child of this group")
        self._invalidate_tree()
        self.children.remove(element)
        element.parent = None
        return element

    @property
    def center(self) -> Vec:
        """Return the union bbox center.

        A Group has no rendered body of its own, so its visual center
        is always the centre of the union of its children's bboxes.
        Under the centre-storage bbox convention this is just
        ``(bbox[0], bbox[1])``. Measures on cache miss; warm-cache
        calls are O(1).
        """
        cx, cy, _, _ = self.get_bbox()
        return Vec(cx, cy)

    def _current_anchor_point(self) -> Vec:
        """Return the union-bbox anchor point.

        Always measures (no stored-``_pos`` fast path): a Group's
        ``_pos`` is updated by :meth:`move_to` / :meth:`shift` but does
        not stay in sync when descendants are moved independently, so
        the only reliable read is via the union bbox.
        """
        cx, cy, w, h = self.get_bbox()
        h_mul, v_mul = anchor_offsets(self._anchor)
        return Vec(cx + (h_mul - 0.5) * w, cy + (v_mul - 0.5) * h)
