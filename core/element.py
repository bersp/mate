from __future__ import annotations

import copy as _copy
from typing import Literal

from .registry import IDKey, id_registry
from .vec import Vec, VecLike


_mid_counter = [0]


def _next_mid() -> int:
    """Return the next process-global element id (monotonic)."""
    _mid_counter[0] += 1
    return _mid_counter[0]


Placement = Literal["fixed", "inline", "omitted"]


class Element:
    """Base class of every visual node that can appear on a slide.

    Every element exposes a uniform ``(x, y, w, h)`` bounding box in cm.
    Elements form a tree via ``children``; measurement is a function of
    the tree alone — orphan elements (no slide membership, no parent)
    can call :meth:`get_bbox` and the measurer runs over their own
    subtree.

    Center anchor
    -------------
    Every element carries a single absolute position in slide
    coordinates (cm) exposed as :attr:`center`. ``center`` is the
    **center** of the element's bounding box: the renderer measures the
    body's size and emits a ``#place(top + left, dx: center.x - w/2,
    dy: center.y - h/2, body)`` block so the body's center lands at
    ``center``. This makes recentering trivially idempotent —
    ``el.move_to(el.center)`` is the identity.

    Storage is in the private ``_center`` field; reads go through the
    :attr:`center` property so subclasses can override the public
    reading (e.g. :class:`~mate.elements.group.Group` returns the union
    bbox center, since a Group has no rendered body of its own).
    Internal hot paths (``_translate``, the backend) read/write
    ``_center`` directly to avoid measurement.

    The :attr:`placement` enum decides how ``center`` is used:

    - ``"fixed"``   — drawn with its center anchored at ``_center``.
    - ``"inline"``  — flows within its parent's content; ``_center`` is
      ignored at render time and reading :attr:`center` measures the
      actual visual center (Typst ``here().position()`` probe for x;
      the parent's line top for y). Used by
      :class:`~mate.elements.text.Text` subs created by ``[...](id=K)``
      markup.
    - ``"omitted"`` — neither rendered nor measured; the element stays
      in the tree but contributes nothing.

    Movement
    --------
    Two mutators flip ``placement`` to ``"fixed"`` and propagate to
    every fixed descendant so the whole subtree translates as a unit:

    - :meth:`move_to(p)` writes ``_center = p``. The visual delta is
      ``p - <current visual center>``.
    - :meth:`shift(d)` adds ``d`` to ``_center`` (accumulates over
      repeated calls). When the element is currently ``"inline"`` it
      first *freezes* ``_center`` to its measured visual center so the
      increment is taken from the flowed position; ``shift((0, 0))``
      is then a true visual no-op.

    Both call :meth:`_translate` on every child with the same delta so
    that fixed descendants move together. ``"inline"`` children are not
    touched (their ``_center`` is meaningless), but the recursion
    descends through them so that fixed grand-descendants still follow.

    Parameters
    ----------
    center : VecLike, optional
        Initial center in cm. Defaults to ``Vec(0, 0)``.
    placement : Placement, optional
        Initial placement state. Defaults to ``"fixed"``.
    id : IDKey or list[IDKey] or None, optional
        User-facing id(s). Accepts a single ``int``/``float``/``str`` or
        a list of them; stored normalized to a list. Each entry registers
        this element in :data:`~mate.core.registry.id_registry`.

    Attributes
    ----------
    center : Vec
        Visual center in slide coordinates. Property — reads return the
        true visual center (measuring for ``"inline"`` elements on
        cache miss); writes store the value in ``_center``.
    placement : Placement
        See ``placement`` parameter.
    parent : Element or None
        Set automatically when this element is attached to another
        element's ``children``. Root elements (direct children of a
        :class:`~mate.core.presentation.Slide`) keep ``parent = None``.
    hidden : bool
        If ``True`` the element takes space but is not drawn.
    children : list[Element]
        Sub-elements forming the tree.
    id : list[IDKey]
        User-facing ids; empty when none. Clones from :meth:`copy` are
        born with an empty ``id`` and are not in the registry.
    _center : Vec
        Storage backing :attr:`center`. Internal hot paths read/write
        this directly.
    _mid : int
        Globally unique monotonic id (used by the backend for metadata).
    _bbox : tuple[float, float, float, float] or None
        Cached ``(x, y, w, h)`` in cm; ``None`` means not yet measured.
    """

    def __init__(
        self,
        *,
        center: VecLike | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        self._center: Vec = Vec(center) if center is not None else Vec(0, 0)
        self.placement: Placement = placement
        self.parent: Element | None = None
        self.hidden: bool = False
        self.children: list[Element] = []
        self.id: list[IDKey] = []
        self._mid: int = _next_mid()
        self._bbox: tuple[float, float, float, float] | None = None
        if id is not None:
            keys = id if isinstance(id, list) else [id]
            for k in keys:
                self.id.append(k)
                id_registry.register(self, k)

    @property
    def center(self) -> Vec:
        """Return the current visual center in slide coordinates.

        Fast path for ``"fixed"`` / ``"omitted"``: returns the stored
        ``_center`` directly, no measurement. For ``"inline"`` the
        anchor has no meaning until layout runs, so this triggers a
        measurement (one Typst subprocess on cache miss) and returns
        the bbox center.

        The setters that write the center are :meth:`move_to` and
        :meth:`shift`.
        """
        if self.placement == "inline":
            x, y, w, h = self.get_bbox()
            return Vec(x + w / 2, y + h / 2)
        return self._center

    @center.setter
    def center(self, value: VecLike) -> None:
        self._center = Vec(value)

    def move_to(self, p: VecLike) -> Element:
        """Anchor the element at slide coordinates ``p`` and translate descendants.

        Sets ``_center = p`` and forces ``placement = "fixed"``.
        Computes the visual delta against the current :attr:`center`
        (which measures for inline/Group) and applies it to every fixed
        descendant, so the subtree translates as a unit.

        Geometric mutator: invalidates the bbox cache of this element's tree.

        Returns
        -------
        Element
            ``self``, to allow chaining.
        """
        new_center = Vec(p)
        old_center = self.center
        self._center = new_center
        self.placement = "fixed"
        self._translate_children(new_center - old_center)
        self._invalidate_tree()
        return self

    def shift(self, d: VecLike) -> Element:
        """Add ``d`` to ``_center`` and translate descendants by the same delta.

        Accumulates over repeated calls (``shift((1, 0)).shift((1, 0))``
        ends up at ``+2cm`` on x). When the element is currently
        ``"inline"``, ``_center`` is first frozen to the element's
        measured visual center so the increment is taken from the
        flowed position; ``shift((0, 0))`` is then a true visual no-op.
        Forces ``placement = "fixed"`` and may trigger one measurement
        on the first call against an inline element.

        Geometric mutator: invalidates the bbox cache of this element's tree.

        Returns
        -------
        Element
            ``self``, to allow chaining.
        """
        delta = Vec(d)
        if self.placement == "inline":
            self._center = self.center
        self._center = self._center + delta
        self.placement = "fixed"
        self._translate_children(delta)
        self._invalidate_tree()
        return self

    def _translate_children(self, delta: Vec) -> None:
        """Apply ``delta`` to every fixed descendant in this subtree.

        ``"inline"`` descendants are skipped for the position update
        (their ``_center`` is irrelevant) but recursion descends
        through them so fixed grand-descendants still follow.
        ``"omitted"`` subtrees are pruned entirely.
        """
        if delta.x == 0 and delta.y == 0:
            return
        for c in self.children:
            c._translate(delta)

    def _translate(self, delta: Vec) -> None:
        if self.placement == "omitted":
            return
        if self.placement == "fixed":
            self._center = self._center + delta
        for c in self.children:
            c._translate(delta)

    def get_hidden(self) -> bool:
        """Return this element's own ``hidden`` flag (no ancestor walk)."""
        return self.hidden

    def get_placement(self) -> Placement:
        """Return the element's :attr:`placement` (``"fixed"``/``"inline"``/``"omitted"``)."""
        return self.placement

    def get_parent(self) -> Element | None:
        """Return the owning :class:`Element`, or ``None`` for tree roots."""
        return self.parent

    def get_children(self) -> list[Element]:
        """Return the live ``children`` list. Mutation routes through ``add`` / ``_take_children``."""
        return self.children

    def get_id(self) -> list[IDKey]:
        """Return the user-facing ids assigned at construction (empty when none)."""
        return self.id

    def get_effective_hidden(self) -> bool:
        """``True`` if this element or any ancestor has ``hidden=True``."""
        el: Element | None = self
        while el is not None:
            if el.hidden:
                return True
            el = el.parent
        return False

    def set_hidden(self, hidden: bool, propagate: bool = True) -> Element:
        """Set ``hidden``; with ``propagate=True`` (default) also rewrites every descendant.

        Visual-only — does not invalidate the bbox cache. Walks every
        descendant regardless of type, since ``hidden`` is an
        :class:`Element` field (not gated by :class:`Drawable`).

        Returns
        -------
        Element
            ``self``, to allow chaining.
        """
        self._set_field("hidden", hidden, propagate)
        return self

    def _set_field(self, field: str, value: object, propagate: bool) -> None:
        """Write ``field`` on ``self`` and optionally on every descendant that owns it.

        With ``propagate=True``, walks the subtree and sets the field on
        every node where ``hasattr(node, field)`` is true — so a
        :class:`Drawable`-only field (``fill_color`` etc.) skips plain
        :class:`Element` descendants automatically, and a class-specific
        intrinsic (``width``, ``radius``) only touches nodes that have it.
        With ``propagate=False`` only the receiver is written.
        """
        if not propagate:
            setattr(self, field, value)
            return

        def walk(el: Element) -> None:
            if hasattr(el, field):
                setattr(el, field, value)
            for c in el.children:
                walk(c)
        walk(self)

    def get_bbox(self) -> tuple[float, float, float, float]:
        """Return the cached ``(x, y, w, h)``, measuring on cache miss.

        On cache miss, walks to the tree root (the topmost ancestor
        reachable through ``parent``) and runs the backend measurer
        over that subtree. Membership in a :class:`Slide` is
        irrelevant — measurement is a function of the tree alone.
        """
        if self._bbox is None:
            from ..backends.typst import TypstMeasurer
            TypstMeasurer([self._tree_root()]).measure()
        return self._bbox  # type: ignore[return-value]

    def _tree_root(self) -> Element:
        """Return the topmost ancestor reachable through ``parent``."""
        el = self
        while el.parent is not None:
            el = el.parent
        return el

    def get_bbox_center(self) -> Vec:
        """Return the bbox center as a :class:`Vec`.

        Always measures (on cache miss), regardless of placement. Use
        :attr:`center` for the cheaper "anchor or measured" reading.
        """
        x, y, w, h = self.get_bbox()
        return Vec(x + w / 2, y + h / 2)

    def copy(self) -> Element:
        """Public deep-copy entry point.

        Drives the two-pass copy protocol: subclasses override
        :meth:`_copy` (not this method) and use the shared ``mapping``
        to fix up cross-references between cloned descendants.
        """
        return self._copy({})

    def _copy(self, mapping: dict[int, Element]) -> Element:
        """Clone this node and recurse into ``children``.

        Uses :func:`copy.copy` to duplicate the instance's ``__dict__``,
        so subclasses with intrinsic-data fields (``w``, ``h``, ``r``,
        ``content``, ...) need no override at all. Identity-bearing
        fields (``_mid``, ``id``, ``parent``) are then reset, the bbox
        cache is dropped, and ``children`` is deep-cloned via the
        recursion. Only subclasses with **cross-references between
        descendants** (e.g. :class:`Text` and its ``subs``) override
        this method to remap those references via ``mapping``.

        Parameters
        ----------
        mapping : dict[int, Element]
            ``id(old) -> new`` accumulator shared across the whole copy.
        """
        new = _copy.copy(self)
        new._mid = _next_mid()
        new._bbox = None
        new.id = []
        new.parent = None
        new._take_children([c._copy(mapping) for c in self.children])
        mapping[id(self)] = new
        return new

    def _take_children(self, children: list[Element]) -> None:
        """Adopt ``children``: assign the list and set each child's parent."""
        self.children = children
        for c in children:
            c.parent = self

    def _invalidate_tree(self) -> None:
        """Drop the bbox cache for every node in this element's tree.

        Walks to the tree root and clears ``_bbox`` on every descendant.
        Used by geometric mutators: a position change can shift the
        flowed top-left of inline siblings, so the whole tree's cache
        must be re-measured on the next :meth:`get_bbox` call.
        """
        root = self._tree_root()

        def clear(el: Element) -> None:
            el._bbox = None
            for c in el.children:
                clear(c)
        clear(root)
