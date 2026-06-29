from __future__ import annotations

import re

from ..config import config
from ..core.element import Anchor, Element, HAlign, Placement
from ..core.registry import IDKey
from ..core.drawable import Drawable
from ..core.vec import VecLike

_BLOCK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


class Text(Drawable):
    """Textual element: either a leaf with ``content`` or a tree of ``Text``.

    Markup ``[...][<props>]`` parses balanced brackets into a sub-element
    and applies each ``name=value`` of ``<props>`` to it as ``set_<name>``
    (e.g. ``set_id``, ``set_color``); a property with no matching setter
    raises. Each sub is appended to its parent's :attr:`subs` (in source
    order); a sub with an ``id`` is also registered in
    :data:`~mate.core.registry.id_registry`, so the same key can address
    every element tagged with it.

    Markup ``[[<props>]]`` anywhere in the source applies its properties to
    the whole text block (this node), with the same ``set_<name>`` rule.

    A ``||`` marker splits the text into reveal segments: the part before the
    first ``||`` shows immediately, and each following segment appears on a
    later reveal step while reserving its space from the start. In running text
    the split acts only at bracket depth 0, outside ``code`` and ``$math$``
    spans, and sits between complete inline spans — a ``||`` inside a
    ``**bold**`` or ``*italic*`` pair leaves an unbalanced marker in each
    segment.

    When the whole source is a single math span (``$...$`` or ``$$...$$``), a
    ``||`` inside it splits the one equation into reveal segments instead: the
    equation renders as a single math run with each later segment wrapped in
    Typst's ``hide`` until its step, keeping the visible part's math spacing
    while the tail holds its place.

    ``subs`` only holds the spans that appear at this node's immediate
    bracket level — nesting is preserved:
    ``Text("foo [bar [baz][id=1]][id=2]")`` exposes ``text.subs[0]`` as
    the wrapper for ``bar [baz]``, and ``text.subs[0].subs[0]`` as the
    inner ``baz`` node.

    Parameters
    ----------
    source : str or None, optional
        Source string with optional ``[...][<props>]`` and ``[[<props>]]``
        markup. ``None`` builds an empty Text (typically for internal
        cloning). Positional.
    font : str or None, optional
        Typst font family name. ``None`` (default) reads ``text.font``
        from the config.
    fontsize : float or None, optional
        Font size in points. ``None`` (default) reads ``text.fontsize``
        from the config.
    weight : str or int or None, optional
        Font weight: a Typst weight name (``"regular"``, ``"bold"``,
        ``"light"``, ``"medium"``, ``"semibold"``, ``"black"``, ...) or an
        integer 100-900. ``None`` (default) uses Typst's default weight.
    style : str or None, optional
        Font style: ``"normal"``, ``"italic"``, or ``"oblique"``. ``None``
        (default) uses Typst's default (``"normal"``).
    letter_spacing : float or None, optional
        Extra spacing between letters, in em (relative to ``fontsize``).
        ``None`` (default) adds none.
    max_width : float or None, optional
        Maximum line width in cm. When set, the text wraps to stay
        within it and the bbox width shrinks to fit the content
        (``min(natural width, max_width)``); ``None`` (default) lets
        the text run on a single line. Applies to the node it is set
        on, not propagated to ``subs``.
    text_align : HAlign or None, optional
        Alignment of the wrapped lines within the text's own box:
        ``"left"``, ``"center"``, or ``"right"``. Only visible when
        ``max_width`` makes the text wrap (otherwise the box hugs a
        single line). ``None`` (default) leaves the lines ragged-left.
        Distinct from :attr:`~mate.core.element.Element.align`, which
        places the whole box within the region.
    line_gap : float or None, optional
        Gap in cm between consecutive line boxes of the wrapped text
        (Typst's paragraph leading). Visible only when ``max_width``
        makes the text wrap. ``None`` (default) reads ``text.line_gap``
        from the config. Matching it to a region's ``arrange_gap`` makes
        a multi-line paragraph share the region's inter-element rhythm.
    fill_color : str or None, optional
        Palette name or literal hex for the glyph fill. ``None`` (default)
        reads ``text.color`` from the config.
    pos, anchor, align, placement, id, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

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
    weight : str or int or None
        See ``weight`` parameter.
    style : str or None
        See ``style`` parameter.
    letter_spacing : float or None
        See ``letter_spacing`` parameter.
    max_width : float or None
        Wrap width in cm, or ``None`` for no wrapping.
    text_align : HAlign or None
        See ``text_align`` parameter.
    line_gap : float
        Inter-line gap in cm for the wrapped text.
    """

    def __init__(
        self,
        source: str | None = None,
        *,
        font: str | None = None,
        fontsize: float | None = None,
        weight: str | int | None = None,
        style: str | None = None,
        letter_spacing: float | None = None,
        max_width: float | None = None,
        text_align: HAlign | None = None,
        line_gap: float | None = None,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
        stroke_dash: str | list[float] | None = None,
        stroke_cap: str | None = None,
        stroke_join: str | None = None,
        stroke_opacity: float | None = None,
    ) -> None:
        super().__init__(
            pos=pos,
            anchor=anchor,
            align=align,
            placement=placement,
            id=id,
            fill_color=config.get("text.color") if fill_color is None else fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.content: str = ""
        self.subs: list[Text] = []
        self.reveal_segments: list[list[Text]] = []
        self.is_math_run: bool = False
        self.math_display: bool = False
        font = config.get("text.font") if font is None else font
        fontsize = config.get("text.fontsize") if fontsize is None else fontsize
        self.font: str = font
        self.fontsize: float = fontsize
        self.weight: str | int | None = weight
        self.style: str | None = style
        self.letter_spacing: float | None = letter_spacing
        self.max_width: float | None = max_width
        self.text_align: HAlign | None = text_align
        self.line_gap: float = (
            config.get("text.line_gap") if line_gap is None else line_gap
        )
        if source is not None:
            block_props: list[str] = []

            def _strip(match: re.Match) -> str:
                block_props.append(match.group(1))
                return ""

            source = _BLOCK_RE.sub(_strip, source)
            pending: list[tuple[Text, str]] = []
            math = _whole_math_span(source)
            if math is not None and "||" in math[1]:
                # A single equation with ``||`` reveals piece by piece: keep one
                # math run whose fragments the backend hides until their step.
                self.is_math_run = True
                self.math_display = math[0]
                fragments = [_leaf(frag) for frag in math[1].split("||")]
                for frag in fragments:
                    self.reveal_segments.append([frag])
                self._take_children(fragments)
            else:
                segments = _split_pauses(source)
                paused = len(segments) > 1
                children: list[Text] = []
                for piece in segments:
                    seg_children = _parse_segment(piece, self.subs, pending)
                    if paused:
                        self.reveal_segments.append(seg_children)
                    children.extend(seg_children)
                # Collapse to a leaf when parsing yields a single childless node
                # with no sub spans; a paused text always keeps its segment tree.
                if (
                    not paused
                    and len(children) == 1
                    and not children[0].children
                    and not self.subs
                ):
                    self.content = children[0].content
                else:
                    self._take_children(children)
                    # Parser-built subs are constructed with the config
                    # defaults; propagate this node's fields so they inherit
                    # explicitly.
                    self._set_field("font", font, propagate=True)
                    self._set_field("fontsize", fontsize, propagate=True)
                    self._set_field("weight", weight, propagate=True)
                    self._set_field("style", style, propagate=True)
                    self._set_field("letter_spacing", letter_spacing, propagate=True)
            # Block props affect the whole node first; sub props apply parent
            # before child (reversed source order) so a child override wins.
            for props in block_props:
                _apply_markup_props(self, props)
            for sub, props in reversed(pending):
                _apply_markup_props(sub, props)

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

    def get_weight(self) -> str | int | None:
        return self.weight

    def get_style(self) -> str | None:
        return self.style

    def get_letter_spacing(self) -> float | None:
        return self.letter_spacing

    def get_max_width(self) -> float | None:
        return self.max_width

    def get_line_gap(self) -> float:
        return self.line_gap

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

    def set_weight(self, weight: str | int | None, propagate: bool = True) -> Text:
        """Set ``weight``; ``propagate`` (default) rewrites every Text descendant.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("weight", weight, propagate)
        self._invalidate_tree()
        return self

    def set_style(self, style: str | None, propagate: bool = True) -> Text:
        """Set ``style``; ``propagate`` (default) rewrites every Text descendant.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("style", style, propagate)
        self._invalidate_tree()
        return self

    def set_letter_spacing(
        self, letter_spacing: float | None, propagate: bool = True
    ) -> Text:
        """Set ``letter_spacing`` (em); ``propagate`` (default) rewrites Text descendants.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("letter_spacing", letter_spacing, propagate)
        self._invalidate_tree()
        return self

    def set_max_width(self, max_width: float | None) -> Text:
        """Set the wrap width in cm, or ``None`` for no wrapping.

        Applies to this node only. Geometric mutator: invalidates the bbox
        cache of this element's tree.
        """
        self.max_width = max_width
        self._invalidate_tree()
        return self

    def set_line_gap(self, line_gap: float) -> Text:
        """Set the inter-line gap in cm for the wrapped text.

        Applies to this node only. Geometric mutator: invalidates the bbox
        cache of this element's tree.
        """
        self.line_gap = line_gap
        self._invalidate_tree()
        return self

    def set_text_align(self, text_align: HAlign | None) -> Text:
        """Set the line alignment within the text box.

        Visual-only: line alignment leaves the box size unchanged, so the
        bbox cache is untouched.
        """
        self.text_align = text_align
        return self

    def get_text_align(self) -> HAlign | None:
        """Return the line alignment, falling back to ``align`` when unset.

        So ``align`` drives both the box placement and the wrapped lines, while
        an explicit ``text_align`` overrides only the lines.
        """
        return self.text_align if self.text_align is not None else self.align

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
        new.reveal_segments = [
            [mapping[id(n)] for n in seg] for seg in self.reveal_segments
        ]
        return new


def _leaf(content: str) -> Text:
    """Build a childless inline :class:`Text` carrying ``content``."""
    t = Text(placement="inline")
    t.content = content
    return t


def _apply_markup_props(element: Element, props: str) -> None:
    """Apply each ``name=value`` of ``props`` to ``element``.

    ``props`` is the keyword text of a ``[...][<props>]`` or ``[[<props>]]``
    markup, evaluated as ``dict(<props>)`` after stripping backslash escapes.
    Each pair goes through :meth:`~mate.core.element.Element.apply_prop`, so
    ``color="red"`` calls ``set_color`` and ``shift=(1, 0)`` calls ``shift``; a
    name matching neither raises.
    """
    props = re.sub(r"\\([\\*_`$])", r"\1", props)
    for name, value in eval(f"dict({props})", {"dict": dict}).items():
        element.apply_prop(name, value)


def _split_pauses(raw: str) -> list[str]:
    """Split ``raw`` on top-level ``||`` reveal markers.

    A ``||`` splits only at bracket depth 0 and outside ``code`` and math
    spans, so markup like ``[a||b][id=1]``, inline ``$||x||$`` and display
    ``$$ ... || ... $$`` stays intact. A run of ``$`` or backticks toggles its
    span as one delimiter: the double markers of display math and fenced code
    count as one toggle. Returns the segment strings in source order (one entry
    when no marker is present).
    """
    pieces: list[str] = []
    buf: list[str] = []
    depth = 0
    in_code = False
    in_math = False
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == "`" and not in_math:
            j = i
            while j < n and raw[j] == "`":
                j += 1
            in_code = not in_code
            buf.append(raw[i:j])
            i = j
            continue
        if c == "$" and not in_code:
            j = i
            while j < n and raw[j] == "$":
                j += 1
            in_math = not in_math
            buf.append(raw[i:j])
            i = j
            continue
        if not in_code and not in_math:
            if c == "[":
                depth += 1
            elif c == "]":
                depth = max(0, depth - 1)
            elif depth == 0 and c == "|" and i + 1 < n and raw[i + 1] == "|":
                pieces.append("".join(buf))
                buf = []
                i += 2
                continue
        buf.append(c)
        i += 1
    pieces.append("".join(buf))
    return pieces


def _whole_math_span(raw: str) -> tuple[bool, str] | None:
    """Return ``(display, body)`` when ``raw`` is a single math span, else ``None``.

    ``raw`` qualifies when, ignoring surrounding whitespace, it is wrapped in a
    single pair of ``$$`` (display) or ``$`` (inline) delimiters with no further
    delimiter of that kind inside. ``body`` is the text between the delimiters.
    """
    s = raw.strip()
    if s.startswith("$$") and s.endswith("$$") and len(s) >= 4:
        inner = s[2:-2]
        if "$$" not in inner:
            return True, inner
    if s.startswith("$") and s.endswith("$") and len(s) >= 2:
        inner = s[1:-1]
        if "$" not in inner:
            return False, inner
    return None


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


def _parse_segment(
    raw: str, subs: list[Text], pending: list[tuple[Text, str]]
) -> list[Text]:
    """Parse ``raw`` into a flat list of :class:`Text` segments.

    Walks ``raw`` once, accumulating plain runs into ``buf`` and splitting on
    ``[...][<props>]`` patterns. Each such block becomes a :class:`Text` span
    appended to the parent's ``subs`` list (source order); the pair
    ``(span, props)`` is queued in ``pending`` so the caller applies the
    properties after field propagation. A ``[...]`` not followed by a
    ``[<props>]`` bracket stays literal text in ``buf``.

    Recurses into the bracket body with a fresh ``subs`` list, so nesting like
    ``[outer [inner][id=1]][id=2]`` puts ``1`` inside the sub for ``2`` rather
    than flattening both at the root. Repeated ids at the same level
    (``[a][id=1][b][id=1]``) are allowed: both spans end up in ``subs`` and
    share a registry bucket.

    Parameters
    ----------
    raw : str
        Source fragment to parse.
    subs : list[Text]
        Accumulator for sub spans found at this level, mutated in place.
    pending : list[tuple[Text, str]]
        Accumulator of ``(span, props)`` to apply after the tree is built.

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
            if j is not None and j + 1 < n and raw[j + 1] == "[":
                k = _match_bracket(raw, j + 1)
                if k is not None:
                    # Flush any pending plain text before emitting the sub.
                    if buf:
                        result.append(_leaf("".join(buf)))
                        buf = []
                    inner_subs: list[Text] = []
                    children = _parse_segment(raw[i + 1 : j], inner_subs, pending)
                    # Wrap eagerly when the body holds nested subs: reusing the
                    # lone child as the outer sub would alias them and corrupt
                    # `subs` ownership.
                    if inner_subs or len(children) != 1 or children[0].children:
                        sub = Text(placement="inline")
                        sub._take_children(children)
                    else:
                        sub = children[0]
                    sub.subs = inner_subs
                    subs.append(sub)
                    pending.append((sub, raw[j + 2 : k]))
                    result.append(sub)
                    i = k + 1
                    continue
            # Unbalanced bracket or no `[<props>]` suffix: fall through and
            # keep the `[` as a literal character.
        buf.append(raw[i])
        i += 1
    if buf:
        result.append(_leaf("".join(buf)))
    return result
