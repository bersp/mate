from __future__ import annotations

from typing import Iterable

from ..core.element import Element, Placement
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
    center, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.
    """

    def __init__(
        self,
        children: Iterable[Element] | None = None,
        *,
        center: VecLike | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
    ) -> None:
        super().__init__(
            center=center,
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

        Invalidates the tree's bbox cache. Returns ``element`` for
        chaining (matches :meth:`Slide.add`).
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
        is always the center of the union of its children's bboxes —
        not the stored ``_center``, which only exists to make
        :meth:`Element.move_to` arithmetic uniform across subclasses.
        Measures on cache miss; warm-cache calls are O(1).
        """
        x, y, w, h = self.get_bbox()
        return Vec(x + w / 2, y + h / 2)

    @center.setter
    def center(self, value: VecLike) -> None:
        self._center = Vec(value)
