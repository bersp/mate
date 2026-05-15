from __future__ import annotations

import copy as _copy
from typing import Iterable, Literal

from .registry import IDKey, id_registry
from .vec import Vec, VecLike


_mid_counter = [0]


def _next_mid() -> int:
    """Return the next process-global element id (monotonic)."""
    _mid_counter[0] += 1
    return _mid_counter[0]


Placement = Literal["fixed", "inline", "omitted"]

Anchor = Literal[
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

# (h_mul, v_mul) such that the bbox top-left is at
# ``_pos - (h_mul * w, v_mul * h)``. Equivalently the anchor point is at
# ``bbox.top_left + (h_mul * w, v_mul * h)``. left=0, center=0.5, right=1;
# top=0, center=0.5, bottom=1.
_ANCHOR_OFFSETS: dict[Anchor, tuple[float, float]] = {
    "top-left":      (0.0, 0.0),
    "top-center":    (0.5, 0.0),
    "top-right":     (1.0, 0.0),
    "center-left":   (0.0, 0.5),
    "center":        (0.5, 0.5),
    "center-right":  (1.0, 0.5),
    "bottom-left":   (0.0, 1.0),
    "bottom-center": (0.5, 1.0),
    "bottom-right":  (1.0, 1.0),
}


def anchor_offsets(anchor: Anchor) -> tuple[float, float]:
    """Return ``(h_mul, v_mul)`` for ``anchor`` (see :data:`_ANCHOR_OFFSETS`)."""
    return _ANCHOR_OFFSETS[anchor]


def measure_all(elements: Iterable[Element]) -> None:
    """Fill ``_bbox`` for every element in a single Typst measurement pass.

    Groups the elements by tree root, dedupes, and runs one
    :class:`~mate.backends.typst.TypstMeasurer` over the unique roots.
    After this call, ``get_bbox`` / ``get_width`` / ``get_height`` on
    any of the given elements (or their descendants) are cache hits
    until the next geometric mutation.

    Useful before any layout helper that would otherwise pay one Typst
    subprocess per element with a distinct tree root.
    """
    seen: dict[int, Element] = {}
    for el in elements:
        root = el._tree_root()
        seen.setdefault(id(root), root)
    if not seen:
        return
    from ..backends.typst import TypstMeasurer
    TypstMeasurer(list(seen.values())).measure()


class Element:
    """Base class of every visual node that can appear on a slide.

    Every element exposes a uniform ``(x, y, w, h)`` bounding box in cm.
    Elements form a tree via ``children``; measurement is a function of
    the tree alone — orphan elements (no slide membership, no parent)
    can call :meth:`get_bbox` and the measurer runs over their own
    subtree.

    Anchor model
    ------------
    Every element stores a single position ``_pos: Vec`` in slide
    coordinates (cm) together with an :data:`Anchor` mode ``_anchor``
    that names which point of the bbox sits at ``_pos``. Nine anchors
    are supported — all combinations of vertical (``top``/``center``/
    ``bottom``) and horizontal (``left``/``center``/``right``) — written
    as hyphenated strings (``"top-left"``, ``"center"``,
    ``"bottom-right"``, ...). The renderer emits a ``#place`` block that
    shifts the body so its ``_anchor`` point lands at ``_pos``.

    With ``anchor="top-left"`` the placement formula is simply
    ``dx = _pos.x, dy = _pos.y`` — Python never needs to know the body's
    measured size to place the element. With other anchors the formula
    involves ``_pos - (h_mul * w, v_mul * h)`` and Typst handles the
    subtraction inline via ``measure(...)``; Python still doesn't
    measure for rendering, but the measurer fills ``_bbox`` for
    geometric queries.

    Placement
    ---------
    The :attr:`placement` enum decides how ``_pos`` is used:

    - ``"fixed"``   — drawn with its ``_anchor`` point at ``_pos``.
    - ``"inline"``  — flows within its parent's content; ``_pos`` is
      ignored at render time and reading the visual anchor point
      requires measurement. Used by :class:`~mate.elements.text.Text`
      subs created by ``[...](id=K)`` markup.
    - ``"omitted"`` — neither rendered nor measured; the element stays
      in the tree but contributes nothing.

    Movement
    --------
    Two mutators flip ``placement`` to ``"fixed"`` and propagate to
    every fixed descendant so the whole subtree translates as a unit:

    - :meth:`move_to(p)` writes ``_pos = p``. The visual delta is
      ``p - <current visual anchor point>``.
    - :meth:`shift(d)` adds ``d`` to ``_pos`` (accumulates over
      repeated calls). When the element is currently ``"inline"`` it
      first *freezes* ``_pos`` to its measured anchor point so the
      increment is taken from the flowed position; ``shift((0, 0))``
      is then a true visual no-op.

    Both call :meth:`_translate` on every child with the same delta so
    that fixed descendants move together. ``"inline"`` children are not
    touched (their ``_pos`` is meaningless), but the recursion descends
    through them so that fixed grand-descendants still follow.

    Parameters
    ----------
    pos : VecLike, optional
        Initial anchor point in cm. Defaults to ``Vec(0, 0)``.
    anchor : Anchor, optional
        Which bbox point sits at ``pos``. Defaults to ``"center"``.
    placement : Placement, optional
        Initial placement state. Defaults to ``"fixed"``.
    id : IDKey or list[IDKey] or None, optional
        User-facing id(s). Accepts a single ``int``/``float``/``str`` or
        a list of them; stored normalized to a list. Each entry registers
        this element in :data:`~mate.core.registry.id_registry`.

    Attributes
    ----------
    pos : Vec
        Stored anchor point (read via the :attr:`pos` property).
    anchor : Anchor
        Stored anchor mode.
    center : Vec
        Visual center in slide coordinates. Property — measures on
        cache miss when the stored anchor is not already the center.
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
    _pos : Vec
        Storage backing :attr:`pos`. Internal hot paths read/write
        this directly.
    _anchor : Anchor
        Storage backing :attr:`anchor`.
    _mid : int
        Globally unique monotonic id (used by the backend for metadata).
    _bbox : tuple[float, float, float, float] or None
        Cached ``(x, y, w, h)`` in cm; ``None`` means not yet measured.
    """

    def __init__(
        self,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        self._pos: Vec = Vec(pos) if pos is not None else Vec(0, 0)
        self._anchor: Anchor = anchor
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
    def pos(self) -> Vec:
        """Return the stored anchor point. Never measures."""
        return self._pos

    @pos.setter
    def pos(self, value: VecLike) -> None:
        self._pos = Vec(value)

    @property
    def anchor(self) -> Anchor:
        """Return the stored anchor mode."""
        return self._anchor

    @property
    def center(self) -> Vec:
        """Return the current visual center in slide coordinates.

        Fast path when ``placement != "inline"`` *and* ``_anchor ==
        "center"``: returns ``_pos`` directly. Otherwise measures the
        bbox (one Typst subprocess on cache miss) and returns its
        center.
        """
        if self.placement != "inline" and self._anchor == "center":
            return self._pos
        x, y, w, h = self.get_bbox()
        return Vec(x + w / 2, y + h / 2)

    def _current_anchor_point(self) -> Vec:
        """Return the current visual position of this element's anchor.

        For ``"fixed"`` placement this is ``_pos`` directly (no
        measurement). For ``"inline"`` placement the anchor point is
        recovered from the measured bbox plus the anchor's offset
        multipliers. :class:`~mate.elements.group.Group` overrides this
        to always measure, since a Group's stored ``_pos`` is not
        guaranteed to track the union-bbox anchor point when descendants
        are moved independently.
        """
        if self.placement == "inline":
            x, y, w, h = self.get_bbox()
            h_mul, v_mul = _ANCHOR_OFFSETS[self._anchor]
            return Vec(x + h_mul * w, y + v_mul * h)
        return self._pos

    def move_to(self, p: VecLike) -> Element:
        """Anchor the element at slide coordinates ``p`` and translate descendants.

        Sets ``_pos = p`` and forces ``placement = "fixed"``.
        Computes the visual delta against the current anchor point
        (which measures for inline/Group) and applies it to every fixed
        descendant, so the subtree translates as a unit.

        Geometric mutator: invalidates the bbox cache of this element's tree.

        Returns
        -------
        Element
            ``self``, to allow chaining.
        """
        new_pos = Vec(p)
        old_anchor = self._current_anchor_point()
        self._pos = new_pos
        self.placement = "fixed"
        self._translate_children(new_pos - old_anchor)
        self._invalidate_tree()
        return self

    def shift(self, d: VecLike) -> Element:
        """Add ``d`` to ``_pos`` and translate descendants by the same delta.

        Accumulates over repeated calls (``shift((1, 0)).shift((1, 0))``
        ends up at ``+2cm`` on x). When the element is currently
        ``"inline"``, ``_pos`` is first frozen to the measured anchor
        point so the increment is taken from the flowed position;
        ``shift((0, 0))`` is then a true visual no-op. Forces
        ``placement = "fixed"`` and may trigger one measurement on the
        first call against an inline element.

        Geometric mutator: invalidates the bbox cache of this element's tree.

        Returns
        -------
        Element
            ``self``, to allow chaining.
        """
        delta = Vec(d)
        if self.placement == "inline":
            self._pos = self._current_anchor_point()
        self._pos = self._pos + delta
        self.placement = "fixed"
        self._translate_children(delta)
        self._invalidate_tree()
        return self

    def set_anchor(self, anchor: Anchor) -> Element:
        """Change the anchor mode in place.

        The stored ``_pos`` is not modified, so the visual position
        shifts to put the new anchor point at the same coordinate.
        Geometric mutator: invalidates the bbox cache of this element's
        tree (the bbox top-left moves).

        Returns ``self`` for chaining.
        """
        self._anchor = anchor
        self._invalidate_tree()
        return self

    def _translate_children(self, delta: Vec) -> None:
        """Apply ``delta`` to every fixed descendant in this subtree.

        ``"inline"`` descendants are skipped for the position update
        (their ``_pos`` is irrelevant) but recursion descends
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
            self._pos = self._pos + delta
        for c in self.children:
            c._translate(delta)

    def get_hidden(self) -> bool:
        """Return this element's own ``hidden`` flag (no ancestor walk)."""
        return self.hidden

    def get_placement(self) -> Placement:
        """Return the element's :attr:`placement` (``"fixed"``/``"inline"``/``"omitted"``)."""
        return self.placement

    def get_anchor(self) -> Anchor:
        """Return the element's :attr:`anchor` mode."""
        return self._anchor

    def get_pos(self) -> Vec:
        """Return the stored anchor point. Never measures."""
        return self._pos

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

    def get_width(self) -> float:
        """Return the bbox width in cm (measures on cache miss)."""
        return self.get_bbox()[2]

    def get_height(self) -> float:
        """Return the bbox height in cm (measures on cache miss)."""
        return self.get_bbox()[3]

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
