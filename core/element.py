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
    "top-left",
    "top-center",
    "top-right",
    "center-left",
    "center",
    "center-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]

# Horizontal alignment of an element within its region, resolved by
# ``arrange``. ``None`` inherits the region's horizontal half.
HAlign = Literal["left", "center", "right"]

# (h_mul, v_mul) such that the bbox centre is offset from ``_pos`` by
# ``((0.5 - h_mul) * w, (0.5 - v_mul) * h)``. Equivalently the anchor
# point is at ``bbox.centre + ((h_mul - 0.5) * w, (v_mul - 0.5) * h)``.
# left=0, center=0.5, right=1; bottom=0, center=0.5, top=1. Slide
# coordinates are y-up, so ``top-*`` anchors carry the larger ``v_mul``.
_ANCHOR_OFFSETS: dict[Anchor, tuple[float, float]] = {
    "top-left": (0.0, 1.0),
    "top-center": (0.5, 1.0),
    "top-right": (1.0, 1.0),
    "center-left": (0.0, 0.5),
    "center": (0.5, 0.5),
    "center-right": (1.0, 0.5),
    "bottom-left": (0.0, 0.0),
    "bottom-center": (0.5, 0.0),
    "bottom-right": (1.0, 0.0),
}


def anchor_offsets(anchor: Anchor) -> tuple[float, float]:
    """Return ``(h_mul, v_mul)`` for ``anchor`` (see :data:`_ANCHOR_OFFSETS`)."""
    return _ANCHOR_OFFSETS[anchor]


def measure_all(elements: Iterable[Element]) -> None:
    """Fill ``_bbox`` for the given elements in a single Typst measurement pass.

    Groups the elements by tree root, dedupes, and runs one
    :class:`~mate.backends.typst.TypstMeasurer` over the unique roots.
    After this call, ``get_bbox`` / ``get_width`` / ``get_height`` on
    any of the given elements are cache hits until the next geometric
    mutation.

    The pass measures inline cursor positions only when one of
    ``elements`` actually needs them (see
    :func:`~mate.backends.typst.needs_inline_x`); a request for fixed
    elements alone runs the cheaper size-only pass, leaving inline
    descendants to be measured on demand.

    Useful before any layout helper that would otherwise pay one Typst
    query per element with a distinct tree root.
    """
    elements = list(elements)
    seen: dict[int, Element] = {}
    for el in elements:
        root = el._tree_root()
        seen.setdefault(id(root), root)
    if not seen:
        return
    from ..backends.typst import TypstMeasurer, needs_inline_x

    TypstMeasurer(list(seen.values())).measure(with_inline_x=needs_inline_x(elements))


class Element:
    """Base class of every visual node that can appear on a slide.

    Every element exposes a uniform ``(x, y, w, h)`` bounding box in
    cm, where ``(x, y)`` is the geometric **centre** of the element and
    ``w``, ``h`` are positive extents. The four edges are derived as
    ``left = x - w/2``, ``right = x + w/2``, ``bottom = y - h/2``,
    ``top = y + h/2``. Elements form a tree via ``children``;
    measurement is a function of the tree alone — orphan elements (no
    slide membership, no parent) can call :meth:`get_bbox` and the
    measurer runs over their own subtree.

    Coordinate system
    -----------------
    Slide coordinates are in centimetres with origin at the slide's
    visual centre, ``+x`` pointing right and ``+y`` pointing up
    (mathematical convention). A slide of size ``(W, H)`` spans
    ``x ∈ [-W/2, +W/2]`` and ``y ∈ [-H/2, +H/2]``. The renderer
    translates this to Typst's native page coordinates (origin
    top-left, ``+y`` down) at emission time.

    Anchor model
    ------------
    Every element stores a single position ``_pos: Vec`` in slide
    coordinates together with an :data:`Anchor` mode ``_anchor`` that
    names which point of the bbox sits at ``_pos``. Nine anchors are
    supported — all combinations of vertical (``top``/``center``/
    ``bottom``) and horizontal (``left``/``center``/``right``) — written
    as hyphenated strings (``"top-left"``, ``"center"``,
    ``"bottom-right"``, ...). The renderer emits a ``#place`` block
    that shifts the body so its ``_anchor`` point lands at ``_pos``.

    With ``anchor="top-left"`` the renderer needs no inline measurement
    (the body's top edge sits at ``_pos.y`` directly, so the placement
    constants are known from ``_pos`` alone). Every other anchor uses
    Typst's ``measure(...)`` at compile time to subtract a fraction of
    the body's height/width; Python still doesn't measure for
    rendering, but the measurer fills ``_bbox`` for geometric queries.

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
    align : HAlign or None, optional
        Horizontal alignment within the region that arranges this
        element: ``"left"``, ``"center"``, or ``"right"``. ``None``
        (default) inherits the region's horizontal half. Read by
        :func:`~mate.composition.arrange.arrange`; has no effect on a
        free element until it is arranged.
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
    align : HAlign or None
        See ``align`` parameter.
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
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        self._pos: Vec = Vec(pos) if pos is not None else Vec(0, 0)
        self._anchor: Anchor = anchor
        self.align: HAlign | None = align
        self.indent: float = 0.0
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

    def _repr_fields(self) -> str:
        """Concrete intrinsic fields for ``repr``; the base contributes none."""
        return ""

    def __repr__(self) -> str:
        parts = [f"#{self._mid}"]
        if self.id:
            parts.append(f"id={self.id!r}")
        fields = self._repr_fields()
        if fields:
            parts.append(fields)
        return f"{type(self).__name__}({', '.join(parts)})"

    @property
    def pos(self) -> Vec:
        """Return the stored anchor point. Never measures."""
        return self._pos

    @pos.setter
    def pos(self, value: VecLike) -> None:
        self._pos = Vec(value)

    @property
    def anchor(self) -> Anchor:
        return self._anchor

    @property
    def center(self) -> Vec:
        """Return the current visual center in slide coordinates.

        Fast path when ``placement != "inline"`` *and* ``_anchor ==
        "center"``: returns ``_pos`` directly. Otherwise measures the
        bbox (one Typst query on cache miss) and returns its
        centre — which under the centre-storage bbox convention is
        ``(bbox[0], bbox[1])``.
        """
        if self.placement != "inline" and self._anchor == "center":
            return self._pos
        cx, cy, _, _ = self.get_bbox()
        return Vec(cx, cy)

    def get_anchor_point(self, anchor: Anchor) -> Vec:
        """Return the position of ``anchor`` on this element's bbox.

        Measures the bbox on cache miss (one Typst query), then offsets
        from its centre by the anchor's multipliers.
        """
        cx, cy, w, h = self.get_bbox()
        h_mul, v_mul = _ANCHOR_OFFSETS[anchor]
        return Vec(cx + (h_mul - 0.5) * w, cy + (v_mul - 0.5) * h)

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
            cx, cy, w, h = self.get_bbox()
            h_mul, v_mul = _ANCHOR_OFFSETS[self._anchor]
            return Vec(cx + (h_mul - 0.5) * w, cy + (v_mul - 0.5) * h)
        return self._pos

    def move_to(self, p: VecLike) -> Element:
        """Anchor the element at slide coordinates ``p`` and translate descendants.

        Sets ``_pos = p`` and forces ``placement = "fixed"``.
        Computes the visual delta against the current anchor point
        (which measures for inline/Group) and applies it to every fixed
        descendant, so the subtree translates as a unit.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        new_pos = Vec(p)
        was_inline = self.placement == "inline"
        old_anchor = self._current_anchor_point()
        self._pos = new_pos
        self.placement = "fixed"
        delta = new_pos - old_anchor
        self._translate_children(delta)
        if was_inline:
            self._invalidate_tree()
        else:
            self._apply_translation_to_bbox_cache(delta)
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
        """
        delta = Vec(d)
        was_inline = self.placement == "inline"
        if was_inline:
            self._pos = self._current_anchor_point()
        self._pos = self._pos + delta
        self.placement = "fixed"
        self._translate_children(delta)
        if was_inline:
            self._invalidate_tree()
        else:
            self._apply_translation_to_bbox_cache(delta)
        return self

    def set_anchor(self, anchor: Anchor) -> Element:
        """Change the anchor mode in place.

        The stored ``_pos`` is not modified, so the visual position
        shifts to put the new anchor point at the same coordinate.
        Geometric mutator: invalidates the bbox cache of this element's
        tree (the bbox corners move).
        """
        self._anchor = anchor
        self._invalidate_subtree_and_ancestors()
        return self

    def set_align(self, align: HAlign | None) -> Element:
        """Set the horizontal alignment within the arranging region.

        Takes effect at the next :meth:`Region.arrange`; it does not
        move an already-placed element, so the bbox cache is untouched.
        """
        self.align = align
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
        return self.placement

    def get_anchor(self) -> Anchor:
        return self._anchor

    def get_pos(self) -> Vec:
        """Return the stored anchor point. Never measures."""
        return self._pos

    def get_parent(self) -> Element | None:
        """Return the owning :class:`Element`, or ``None`` for tree roots."""
        return self.parent

    def get_children(self) -> list[Element]:
        """Return ``children`` list; mutate via ``add``/``_take_children``."""
        return self.children

    def get_id(self) -> list[IDKey]:
        """Return the user-facing ids assigned at construction (empty when none)."""
        return self.id

    def set_id(self, id: IDKey | list[IDKey]) -> Element:
        """Register one or more ids for this element in the id registry."""
        for key in id if isinstance(id, list) else [id]:
            self.id.append(key)
            id_registry.register(self, key)
        return self

    def get_effective_hidden(self) -> bool:
        """Return ``True`` if this element or any ancestor has ``hidden=True``."""
        el: Element | None = self
        while el is not None:
            if el.hidden:
                return True
            el = el.parent
        return False

    def set_hidden(self, hidden: bool, propagate: bool = True) -> Element:
        """Set ``hidden``; ``propagate`` (default) rewrites every descendant.

        Visual-only — does not invalidate the bbox cache. Walks every
        descendant regardless of type, since ``hidden`` is an
        :class:`Element` field (not gated by :class:`Drawable`).
        """
        self._set_field("hidden", hidden, propagate)
        return self

    def resolve_prop(self, name: str):
        """Return ``set_<name>`` if defined, else ``<name>``, else ``None``.

        Resolves a property name to the method that applies it: ``color``
        resolves to ``set_color``, ``shift`` to ``shift`` (which has no
        ``set_shift``).
        """
        return getattr(self, f"set_{name}", None) or getattr(self, name, None)

    def apply_prop(self, name: str, value: object) -> None:
        """Resolve ``name`` via :meth:`resolve_prop` and call it with ``value``.

        Raises :class:`ValueError` naming ``name`` when the element has neither
        a ``set_<name>`` nor a ``<name>`` method.
        """
        method = self.resolve_prop(name)
        if not callable(method):
            raise ValueError(
                f"{type(self).__name__} has no 'set_{name}' or '{name}' method "
                f"to apply property {name!r}"
            )
        method(value)

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

        On cache miss, batches the measurement via :func:`measure_all`,
        which walks to the tree root and runs the backend measurer
        over that subtree. Membership in a :class:`Slide` is
        irrelevant — measurement is a function of the tree alone.
        """
        if self._bbox is None:
            measure_all([self])
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
        cx, cy, _, _ = self.get_bbox()
        return Vec(cx, cy)

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

    def _apply_translation_to_bbox_cache(self, delta: Vec) -> None:
        """Shift the cached bbox of this subtree by ``delta`` in place.

        A pure translation (this element stays ``"fixed"`` while its
        anchor point moves by ``delta``) moves every descendant's bbox
        by exactly ``delta`` and leaves all extents unchanged, so the
        cache can be updated instead of dropped and re-measured. The
        bbox of every strict ancestor is a function of this subtree
        (a :class:`~mate.elements.group.Group` union, or inline-flow
        geometry threaded from a fixed ancestor) and is dropped so the
        next :meth:`get_bbox` recomputes it.
        """
        if delta.x == 0 and delta.y == 0:
            return

        def translate(el: Element) -> None:
            if el._bbox is not None:
                x, y, w, h = el._bbox
                el._bbox = (x + delta.x, y + delta.y, w, h)
            for c in el.children:
                translate(c)

        translate(self)
        self._invalidate_ancestors()

    def _invalidate_subtree_and_ancestors(self) -> None:
        """Drop the bbox cache on this subtree and every strict ancestor.

        For a geometric change that is not a pure translation (an anchor
        flip moves the bbox corners by a content-dependent amount), the
        subtree must be re-measured. Ancestors depend on the subtree and
        are dropped too.
        """

        def clear(el: Element) -> None:
            el._bbox = None
            for c in el.children:
                clear(c)

        clear(self)
        self._invalidate_ancestors()

    def _invalidate_ancestors(self) -> None:
        """Drop the bbox cache on every strict ancestor up to the root."""
        p = self.parent
        while p is not None:
            p._bbox = None
            p = p.parent

    def _invalidate_tree(self) -> None:
        """Drop the bbox cache for every node in this element's tree.

        Walks to the tree root and clears ``_bbox`` on every descendant.
        Used when an element leaves its parent's inline flow (an
        ``"inline"`` to ``"fixed"`` transition): the flowed position of
        the remaining inline siblings shifts, so the whole tree's cache
        must be re-measured on the next :meth:`get_bbox` call.
        """
        root = self._tree_root()

        def clear(el: Element) -> None:
            el._bbox = None
            for c in el.children:
                clear(c)

        clear(root)
