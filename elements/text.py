from __future__ import annotations

import re

from ..config import config
from ..core.element import Anchor, Element, Placement
from ..core.registry import IDKey, id_registry
from ..core.drawable import Drawable
from ..core.vec import VecLike

_ID_RE = re.compile(r"\(id=([^)]+)\)")


class Text(Drawable):
    """Textual element: either a leaf with ``content`` or a tree of ``Text``.

    Markup ``[...](id=K)`` parses balanced brackets into sub-elements
    tagged with id ``K`` (an int, float, or string). Each id'd sub is
    appended to its parent's :attr:`subs` (in source order) and also
    registered in :data:`~mate.core.registry.id_registry`, so the same
    key can address every element tagged with it.

    ``subs`` only holds the ids that appear at this node's immediate
    bracket level — nesting is preserved:
    ``Text("foo [bar [baz](id=1)](id=2)")`` exposes ``text.subs[0]`` as
    the wrapper for ``bar [baz]``, and ``text.subs[0].subs[0]`` as the
    inner ``baz`` node.

    Parameters
    ----------
    source : str or None, optional
        Source string with optional ``[...](id=K)`` markup. ``None``
        builds an empty Text (typically for internal cloning). Positional.
    font : str or None, optional
        Typst font family name. ``None`` (default) reads ``text.font``
        from the config.
    fontsize : float or None, optional
        Font size in points. ``None`` (default) reads ``text.fontsize``
        from the config.
    max_width : float or None, optional
        Maximum line width in cm. When set, the text wraps to stay
        within it and the bbox width shrinks to fit the content
        (``min(natural width, max_width)``); ``None`` (default) lets
        the text run on a single line. Applies to the node it is set
        on, not propagated to ``subs``.
    fill_color : str or None, optional
        Palette name or literal hex for the glyph fill. ``None`` (default)
        reads ``text.color`` from the config.
    pos, anchor, placement, id, stroke_color, fill_opacity, stroke_width
        Keyword-only. See :class:`~mate.core.drawable.Drawable`. ``stroke_*``
        fields are currently ignored for text rendering.

    Attributes
    ----------
    content : str
        Raw text for leaves; empty string when this node has children.
    subs : list[Text]
        Id'd sub-Texts at this immediate level, in source order.
    font : str
        Typst font family used to render and measure this node.
    fontsize : float
        Font size in points.
    max_width : float or None
        Wrap width in cm, or ``None`` for no wrapping.
    """

    def __init__(
        self,
        source: str | None = None,
        *,
        font: str | None = None,
        fontsize: float | None = None,
        max_width: float | None = None,
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
            fill_color=config.get("text.color") if fill_color is None else fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
        )
        self.content: str = ""
        self.subs: list[Text] = []
        font = config.get("text.font") if font is None else font
        fontsize = config.get("text.fontsize") if fontsize is None else fontsize
        self.font: str = font
        self.fontsize: float = fontsize
        self.max_width: float | None = max_width
        if source is not None:
            children = _parse_segment(source, self.subs)
            # Collapse to a leaf when parsing yields a single childless node;
            # otherwise keep the tree in self.children.
            if len(children) == 1 and not children[0].children:
                self.content = children[0].content
            else:
                self._take_children(children)
                # Parser-built subs are constructed with the config defaults;
                # propagate this node's font/size so they inherit explicitly.
                self._set_field("font", font, propagate=True)
                self._set_field("fontsize", fontsize, propagate=True)

    def get_content(self) -> str:
        """Return this node's own raw text (empty when the node has children)."""
        return self.content

    def get_subs(self) -> list[Text]:
        """Return the live list of id'd sub-Texts at this immediate bracket level."""
        return self.subs

    def get_text(self) -> str:
        """Return the concatenated plain text of this node and all its descendants."""
        if self.children:
            return "".join(s.get_text() for s in self.children)
        return self.content

    def get_font(self) -> str:
        return self.font

    def get_fontsize(self) -> float:
        return self.fontsize

    def _repr_fields(self) -> str:
        return f"text={self.get_text()!r}"

    def set_font(self, font: str, propagate: bool = True) -> Text:
        """Set ``font``; ``propagate`` (default) rewrites every Text descendant.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("font", font, propagate)
        self._invalidate_tree()
        return self

    def set_fontsize(self, fontsize: float, propagate: bool = True) -> Text:
        """Set ``fontsize`` (points); ``propagate`` (default) rewrites Text descendants.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("fontsize", fontsize, propagate)
        self._invalidate_tree()
        return self

    def _copy(self, mapping: dict[int, Element]) -> Text:
        # Only the `subs` cross-references need fixing up: ``content`` and
        # every other intrinsic field are already copied by the
        # ``copy.copy`` in ``Element._copy``. ``mapping`` was populated by
        # the superclass walk over ``self.children``, so every sub already
        # has its clone registered — we only need to look it up. Clones
        # inherit the structural ``subs`` references but carry no ids of
        # their own.
        new = super()._copy(mapping)
        new.subs = [mapping[id(s)] for s in self.subs]
        return new


def _leaf(content: str) -> Text:
    """Build a childless inline :class:`Text` carrying ``content``."""
    t = Text(placement="inline")
    t.content = content
    return t


def _parse_id(raw: str) -> IDKey:
    """Coerce an ``(id=...)`` payload to int, then float, then str."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _match_bracket(raw: str, start: int) -> int | None:
    """Return the index of the ``]`` that closes ``raw[start] == '['``.

    Tracks nesting depth so inner brackets do not terminate the match.
    Returns ``None`` if the opening bracket is unbalanced.
    """
    depth = 1
    i = start + 1
    while i < len(raw):
        if raw[i] == "[":
            depth += 1
        elif raw[i] == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _parse_segment(raw: str, subs: list[Text]) -> list[Text]:
    """Parse ``raw`` into a flat list of :class:`Text` segments.

    Walks ``raw`` once, accumulating plain runs into ``buf`` and
    splitting on ``[...](id=K)`` patterns. Each id'd block becomes a
    :class:`Text` tagged with id ``K``: it is appended to the parent's
    ``subs`` list (source order) and registered in the global
    ``id_registry``. Runs without an ``(id=K)`` suffix are kept as raw
    text in ``buf`` (the bracket characters stay literal).

    Recurses into the bracket body with a fresh ``subs`` list, so
    nesting like ``[outer [inner](id=1)](id=2)`` puts ``1`` inside the
    sub registered under ``2`` rather than flattening both at the root.
    Repeated ids at the same level (``[a](id=1)[b](id=1)``) are allowed:
    both elements end up in ``subs`` and share a registry bucket.

    Parameters
    ----------
    raw : str
        Source fragment to parse.
    subs : list[Text]
        Accumulator for id'd subs found at this level, mutated in place.

    Returns
    -------
    list[Text]
        Sibling segments in source order.
    """
    result: list[Text] = []
    buf: list[str] = []
    i, n = 0, len(raw)
    while i < n:
        if raw[i] == "[":
            j = _match_bracket(raw, i)
            if j is not None:
                m = _ID_RE.match(raw, j + 1)
                if m:
                    # Flush any pending plain text before emitting the sub.
                    if buf:
                        result.append(_leaf("".join(buf)))
                        buf = []
                    id_value = _parse_id(m.group(1))
                    inner_subs: list[Text] = []
                    children = _parse_segment(raw[i + 1 : j], inner_subs)
                    # Wrap eagerly when the body holds nested id'd subs:
                    # reusing the lone child as the outer sub would alias
                    # them and corrupt `subs` ownership.
                    if inner_subs or len(children) != 1 or children[0].children:
                        sub = Text(placement="inline")
                        sub._take_children(children)
                    else:
                        sub = children[0]
                    sub.subs = inner_subs
                    sub.id = [id_value]
                    id_registry.register(sub, id_value)
                    subs.append(sub)
                    result.append(sub)
                    i = m.end()
                    continue
            # Unbalanced bracket or no `(id=K)` suffix: fall through and
            # keep the `[` as a literal character.
        buf.append(raw[i])
        i += 1
    if buf:
        result.append(_leaf("".join(buf)))
    return result
