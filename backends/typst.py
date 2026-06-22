from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import typst

from ..config import config
from ..core.element import anchor_offsets
from ..elements.group import Group
from ..elements.image import Image
from ..elements.shapes import Circle, Ellipse, Line, Rectangle
from ..elements.spacing import HSpace, VSpace
from ..elements.text import Text

if TYPE_CHECKING:
    from ..core.element import Element

# Font directory bundled with the package, always on the Typst font path.
_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"


def _font_paths() -> list[str]:
    """Font directories handed to Typst: the project ``fonts/`` dir then
    every extra directory in ``config.font_paths``."""
    return [str(_FONTS_DIR), *config.font_paths]


# Resolvable family names per ``font_paths`` set, cached.
_FONT_FAMILIES: dict[tuple[str, ...], frozenset[str]] = {}


def _available_font_families() -> frozenset[str]:
    """Family names Typst resolves from embedded faces and ``_font_paths()``."""
    key = tuple(_font_paths())
    families = _FONT_FAMILIES.get(key)
    if families is None:
        enumerated = typst.Fonts(
            include_system_fonts=False,
            include_embedded_fonts=True,
            font_paths=list(key),
        )
        families = frozenset(enumerated.families())
        _FONT_FAMILIES[key] = families
    return families


def _assert_fonts_available(fonts: set[str]) -> None:
    """Raise if any of ``fonts`` is not a resolvable family.

    Matching is case-insensitive, like Typst's font lookup.
    """
    families = _available_font_families()
    available_lower = {f.lower() for f in families}
    missing = sorted(f for f in fonts if f.lower() not in available_lower)
    if missing:
        available = ", ".join(sorted(families))
        raise ValueError(
            f"Font(s) not found: {missing}. Add the directory holding the font "
            f"file(s) to config.font_paths (or the front-matter 'font_paths:' "
            f"list). Available families: {available}."
        )


_CACHE_MEASURE = Path(".mate_cache/measure.typ")

# Function that turns an element into its rendered Typst string. The
# `placeholder` flag means "still take space but emit `#hide[...]`": used
# for fixed children whose content is re-emitted at the top level via
# `#place` and must not double-count in the parent's flow.
RenderNode = Callable[["Element", bool], str]


_TYPST_SPECIAL = set("\\`*_$#[]")


def _escape_char(c: str) -> str:
    """Backslash-escape ``c`` if it has special meaning in Typst markup."""
    return f"\\{c}" if c in _TYPST_SPECIAL else c


def _markdown_to_typst(s: str) -> str:
    """Translate the Markdown markup of ``s`` into Typst markup.

    Handles the constructs the parser emits — ``**bold**``, ``*italic*`` /
    ``_italic_``, ``` `code` ```, inline ``$math$`` and display ``$$math$$`` —
    plus backslash escapes; every other character is emitted as a Typst
    literal. Code and math span bodies are passed through verbatim. A
    deliberately simple scanner, not a full CommonMark engine.
    """
    return _scan_markdown(s, 0, len(s))


def _scan_markdown(s: str, i: int, end: int) -> str:
    out: list[str] = []
    while i < end:
        c = s[i]
        if c == "\\" and i + 1 < end:
            out.append(_escape_char(s[i + 1]))
            i += 2
        elif c == "`":
            j = s.find("`", i + 1, end)
            if j == -1:
                out.append(_escape_char(c))
                i += 1
            else:
                out.append(f"`{s[i + 1 : j]}`")
                i = j + 1
        elif c == "$":
            if s.startswith("$$", i):
                j = s.find("$$", i + 2, end)
                if j == -1:
                    out.append(_escape_char(c))
                    i += 1
                else:
                    out.append(f"$ {s[i + 2 : j].strip()} $")
                    i = j + 2
            else:
                j = s.find("$", i + 1, end)
                if j == -1:
                    out.append(_escape_char(c))
                    i += 1
                else:
                    out.append(f"${s[i + 1 : j]}$")
                    i = j + 1
        elif s.startswith("**", i):
            j = _find_delim(s, i + 2, end, "**")
            if j == -1:
                out.append(_escape_char(c))
                i += 1
            else:
                out.append(f"*{_scan_markdown(s, i + 2, j)}*")
                i = j + 2
        elif c in "*_":
            j = _find_delim(s, i + 1, end, c)
            if j == -1:
                out.append(_escape_char(c))
                i += 1
            else:
                out.append(f"_{_scan_markdown(s, i + 1, j)}_")
                i = j + 1
        else:
            out.append(_escape_char(c))
            i += 1
    return "".join(out)


def _find_delim(s: str, i: int, end: int, delim: str) -> int:
    """Index of the closing ``delim`` run, or ``-1``.

    Skips backslash escapes and steps over code and math spans so a
    delimiter character inside them does not close the emphasis. When
    looking for a single ``*``/``_``, a doubled run is stepped over rather
    than matched, so it stays available to close an enclosing bold span.
    """
    while i < end:
        c = s[i]
        if c == "\\":
            i += 2
        elif c == "`":
            j = s.find("`", i + 1, end)
            i = end if j == -1 else j + 1
        elif c == "$":
            close = "$$" if s.startswith("$$", i) else "$"
            j = s.find(close, i + len(close), end)
            i = end if j == -1 else j + len(close)
        elif len(delim) == 1 and s.startswith(delim * 2, i):
            i += 2
        elif s.startswith(delim, i):
            return i
        else:
            i += 1
    return -1


_DEFAULT_FILL_COLOR = "black"
_DEFAULT_STROKE_COLOR = "black"


def _bare(el: Element) -> str:
    """Render ``el`` without `#place`/`#hide` wrappers (size-measurement form).

    Used by the measurer to ask Typst for the *isolated* size of each
    element via ``measure(...)``. Fill is dropped (it does not affect
    glyph metrics); positioning and visibility are not represented either.
    ``"omitted"`` children contribute nothing to the parent's size.
    """
    if isinstance(el, Text):
        if el.children:
            inner = "".join(_bare(c) for c in el.children if c.placement != "omitted")
        else:
            inner = _markdown_to_typst(el.content)
        body = _wrap_text_attrs(el, inner, with_fill=False)
        if el.max_width is not None:
            # Width is measured from the leading-free body (leading does
            # not affect width); height from the leading-carrying body so
            # the recorded bbox reflects the wrapped line spacing.
            body = _wrap_max_width(body, _wrap_line_gap(body, el.line_gap), el.max_width)
        return body
    if isinstance(el, (Rectangle, Circle, Ellipse)):
        return _shape_markup(el)
    if isinstance(el, Line):
        return _line_markup(el)
    if isinstance(el, Image):
        return _image_markup(el)
    if isinstance(el, (VSpace, HSpace)):
        return _spacer_markup(el)
    # Groups (and any unknown leaf) contribute nothing to size: the
    # group's bbox is computed as the union of children in `_assign`,
    # so the per-element measurement record is intentionally empty.
    return ""


def _typst_fill(color: str | None, opacity: float | None) -> str:
    """Resolve ``(fill_color, fill_opacity)`` into a Typst ``fill:`` value.

    Returns ``"none"`` for ``opacity == 0`` (the canonical "no fill"
    case for shapes). For non-zero opacity, falls back to ``"black"``
    when ``color`` is ``None`` and wraps with ``.transparentize(...)``
    when ``opacity < 1``.
    """
    op = 1.0 if opacity is None else opacity
    if op == 0:
        return "none"
    c = f'rgb("{color}")' if color is not None else _DEFAULT_FILL_COLOR
    if op == 1:
        return c
    return f"{c}.transparentize({(1.0 - op) * 100}%)"


def _typst_stroke(color: str | None, width: float | None) -> str:
    """Resolve ``(stroke_color, stroke_width)`` into a Typst ``stroke:`` value.

    Returns ``"none"`` when ``width`` is ``None`` or ``0`` (the
    canonical "no stroke" case). Otherwise emits ``"<width>cm + <color>"``,
    falling back to ``"black"`` when ``color`` is ``None``.
    """
    w = 0.0 if width is None else width
    if w == 0:
        return "none"
    c = f'rgb("{color}")' if color is not None else _DEFAULT_STROKE_COLOR
    return f"{w}cm + {c}"


def _wrap_text_attrs(el: Text, inner: str, *, with_fill: bool = True) -> str:
    """Wrap ``inner`` in a ``#text(...)`` call with the element's font and
    size, plus ``weight``/``style``/``tracking`` when set and ``fill`` when
    present.

    ``font`` and ``size`` are always emitted — every :class:`Text` carries
    them explicitly so the rendered output never relies on Typst's
    implicit fallback. ``fill:`` is added only when the element has
    explicit fill state, otherwise the body inherits Typst's lexical
    default (black, matching :class:`~mate.core.drawable.Drawable`'s
    visual default). ``with_fill=False`` drops it entirely: fill does not
    affect glyph metrics, so the measurement form omits it to keep the
    aux document small.
    """
    attrs = [f'font: "{el.font}"', f"size: {el.fontsize}pt"]
    if el.weight is not None:
        weight = f'"{el.weight}"' if isinstance(el.weight, str) else el.weight
        attrs.append(f"weight: {weight}")
    if el.style is not None:
        attrs.append(f'style: "{el.style}"')
    if el.letter_spacing is not None:
        attrs.append(f"tracking: {el.letter_spacing}em")
    if with_fill and not (el.fill_color is None and el.fill_opacity is None):
        attrs.append(f"fill: {_typst_fill(el.fill_color, el.fill_opacity)}")
    return f'#text({", ".join(attrs)})[{inner}]'


def _wrap_max_width(measure_body: str, render_body: str, max_width: float) -> str:
    """Box ``render_body`` at ``min(natural width, max_width)`` cm.

    The box width is resolved at Typst's ``#context`` time from the
    natural width of ``measure_body`` (probe-free, so it measures the
    plain glyphs), giving shrink-to-fit wrapping: the body keeps its
    natural width until it would exceed ``max_width``, then wraps.
    ``render_body`` is what actually flows inside the box; it may carry
    the measurer's inline x-probes, which are zero-width and so must be
    kept out of the width measurement.
    """
    return (
        f"#context {{ let __w = calc.min(measure([{measure_body}]).width, "
        f"{max_width}cm); box(width: __w)[{render_body}] }}"
    )


def _wrap_line_gap(body: str, line_gap: float) -> str:
    """Prefix ``body`` with a ``#set par(leading: ...)`` rule.

    ``leading`` is the gap between the bottom edge of one line box and
    the top edge of the next, so this fixes a wrapped paragraph's
    inter-line gap at ``line_gap`` cm. Meaningful only inside the
    width-constrained box where the text wraps; on a single line it has
    no visible effect. The rule scopes to the enclosing content block.
    """
    return f"#set par(leading: {line_gap}cm); {body}"


def _wrap_align(body: str, text_align: str | None) -> str:
    """Wrap ``body`` in ``#align(...)`` to align its lines, or return it as is.

    Only meaningful inside a width-constrained box (the wrapped text);
    the alignment value (``"left"``/``"center"``/``"right"``) is a valid
    Typst alignment keyword.
    """
    if text_align is None:
        return body
    return f"#align({text_align})[{body}]"


def _shape_markup(el: Rectangle | Circle | Ellipse) -> str:
    """Emit the Typst body for a filled shape primitive.

    Dispatches on the concrete type to ``#rect`` / ``#circle`` /
    ``#ellipse``. The fill/stroke pair comes from the element's own
    ``fill_color``/``fill_opacity``/``stroke_color``/``stroke_width``
    fields, resolved locally — no parent walk.
    """
    fill = _typst_fill(el.fill_color, el.fill_opacity)
    stroke = _typst_stroke(el.stroke_color, el.stroke_width)
    if isinstance(el, Rectangle):
        return (
            f"#rect(width: {el.width}cm, height: {el.height}cm, "
            f"fill: {fill}, stroke: {stroke})"
        )
    if isinstance(el, Circle):
        return f"#circle(radius: {el.radius}cm, " f"fill: {fill}, stroke: {stroke})"
    return (
        f"#ellipse(width: {el.width}cm, height: {el.height}cm, "
        f"fill: {fill}, stroke: {stroke})"
    )


def _line_markup(el: Line) -> str:
    """Emit the Typst body for a :class:`Line`.

    The endpoints are normalized to the bbox's top-left in Typst's
    y-down local frame, so the segment draws inside its own bounding
    box and ``measure(...)`` returns ``(|dx|, |dy|)`` — matching the
    element's intrinsic width/height.
    """
    sx, sy = el.start.x, el.start.y
    ex, ey = el.end.x, el.end.y
    left = min(sx, ex)
    top = max(sy, ey)
    stroke = _typst_stroke(el.stroke_color, el.stroke_width)
    return (
        f"#line(start: ({sx - left}cm, {top - sy}cm), "
        f"end: ({ex - left}cm, {top - ey}cm), stroke: {stroke})"
    )


def _spacer_markup(el: VSpace | HSpace) -> str:
    """Emit an invisible box matching a spacer's intrinsic size."""
    return f"#box(width: {el.get_width()}cm, height: {el.get_height()}cm)"


def _escape_typst_string(s: str) -> str:
    """Escape ``s`` for a Typst double-quoted string literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _image_markup(el: Image) -> str:
    """Emit the Typst body for an :class:`Image`.

    The path is resolved to an absolute filesystem path so it loads
    identically from the measurer's aux ``.typ`` and the renderer's
    in-memory source — both compile with the Typst root at ``/``. Only
    the dimensions that are set are emitted, so Typst keeps the file's
    aspect ratio for any left free.

    A ``clip`` crops the image inside a ``#box(clip: true)``. A
    centimetre crop uses a negative inset; a percentage crop measures
    the image's rendered width and removes that fraction of it from all
    four edges, so it tracks the aspect-derived size when a dimension is
    left free.
    """
    path = _escape_typst_string(str(Path(el.path).resolve()))
    attrs = [f'"{path}"']
    if el.width is not None:
        attrs.append(f"width: {el.width}cm")
    if el.height is not None:
        attrs.append(f"height: {el.height}cm")
    image = f"image({', '.join(attrs)})"
    if el.clip is None:
        return f"#{image}"
    if isinstance(el.clip, str):
        frac = float(el.clip.rstrip("%")) / 100.0
        return (
            f"#context {{ let im = {image}; let m = measure(im); "
            f"let c = m.width * {frac}; "
            f"box(clip: true, width: m.width - 2 * c, height: m.height - 2 * c, "
            f"place(dx: -c, dy: -c, im)) }}"
        )
    return f"#box(clip: true, inset: -{el.clip}cm)[#{image}]"


def _collect_fixed(el: Element) -> list[Element]:
    """Gather descendants of ``el`` whose ``placement == "fixed"``.

    Stops descending into a fixed child (it becomes its own ``#place``
    root); inline children are walked through transparently. Omitted
    subtrees are ignored.
    """
    out: list[Element] = []
    for c in el.children:
        if c.placement == "omitted":
            continue
        if c.placement == "fixed":
            out.append(c)
        else:
            out.extend(_collect_fixed(c))
    return out


def _render_placed(
    el: Element,
    render_node: RenderNode,
    canvas: tuple[float, float] | None = None,
) -> list[str]:
    """Emit ``#place`` blocks for ``el`` and every fixed descendant.

    Slide coordinates are y-up with origin at the slide centre; Typst's
    page coordinates are y-down with origin at the page's top-left. The
    body's left edge in user coordinates is ``_pos.x - h_mul * w`` and
    its top edge is ``_pos.y + (1 - v_mul) * h`` where
    ``(h_mul, v_mul)`` are the anchor's offset multipliers. ``canvas``
    controls how those user-coordinate values are mapped onto the
    Typst page:

    - ``canvas=(W, H)`` (renderer mode): apply the full user→Typst
      transform: ``dx = _pos.x + W/2 - h_mul * w`` and
      ``dy = H/2 - _pos.y - (1 - v_mul) * h``. ``anchor="top-left"``
      collapses to constants ``dx = _pos.x + W/2``, ``dy = H/2 - _pos.y``
      with no inline ``measure(...)``.
    - ``canvas=None`` (measurer/aux-doc mode): no centring or y-flip is
      applied. ``dx`` matches the user-coordinate left edge directly
      and ``dy = _pos.y + (1 - v_mul) * h``. The aux doc never needs
      to be visually correct — only the inline ``here().position().x``
      probes are read back, and they recover the user-coordinate x
      because the fixed ancestor's left edge sits at user-x in the aux
      doc too.

    Every other anchor wraps the placement in
    ``#context { let __s = measure(__b); ... }`` so Typst supplies the
    body's measured size at compile time; Python still doesn't measure
    for rendering. Fixed descendants are emitted as siblings (not
    nested) so Typst's flow doesn't stack them inside the parent —
    only the explicit dx/dy decide position.

    Parameters
    ----------
    el : Element
        Fixed root.
    render_node : RenderNode
        Backend-specific body renderer (renderer vs measurer differ
        only in this callable).
    canvas : tuple[float, float] or None
        ``(width, height)`` of the slide in cm for renderer mode, or
        ``None`` for the measurer's aux-doc mode (see above).

    Returns
    -------
    list[str]
        Lines to append to the output buffer.
    """
    body = render_node(el, False)
    # A fixed descendant sits in its own `#place` block, outside any
    # ancestor's `#hide` wrapper. Apply the effective-hidden flag
    # locally so an ancestor's `hidden=True` reaches it.
    if not el.hidden and el.get_effective_hidden():
        body = f"#hide[{body}]"
    h_mul, v_mul = anchor_offsets(el._anchor)
    if canvas is None:
        dx_const = el._pos.x
        dy_const = el._pos.y
        # Aux doc keeps Typst's native y-down within the placed block,
        # so the body's top edge sits `+ (1 - v_mul) * h` below the
        # anchor point (matches the user-coord top edge `_pos.y +
        # (1 - v_mul) * h` because we treat user-y as Typst-y here).
        dy_h_sign = 1.0
    else:
        W, H = canvas
        dx_const = el._pos.x + W / 2
        dy_const = H / 2 - el._pos.y
        # Renderer flips y: a larger (1 - v_mul) * h moves the body's
        # top *up* in user-y, which is *down* in Typst-y, so subtract.
        dy_h_sign = -1.0
    # ``"top-left"`` is the only anchor with both multipliers zero
    # (h_mul == 0 and (1 - v_mul) == 0); skip the contextual measure.
    if h_mul == 0 and v_mul == 1:
        line = f"#place(top + left, dx: {dx_const}cm, dy: {dy_const}cm, " f"[{body}])"
    else:
        dx_expr = f"{dx_const}cm"
        if h_mul != 0:
            dx_expr += f" - {h_mul} * __s.width"
        dy_expr = f"{dy_const}cm"
        if v_mul != 1:
            dy_coef = dy_h_sign * (1.0 - v_mul)
            sign = "-" if dy_coef < 0 else "+"
            dy_expr += f" {sign} {abs(dy_coef)} * __s.height"
        line = (
            "#context { "
            f"let __b = [{body}]; "
            "let __s = measure(__b); "
            f"place(top + left, dx: {dx_expr}, dy: {dy_expr}, __b) "
            "}"
        )
    out = [line]
    for sub in _collect_fixed(el):
        out.extend(_render_placed(sub, render_node, canvas))
    return out


def _write(path: Path, content: str) -> None:
    """Write ``content`` to ``path``, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def needs_inline_x(elements: list[Element]) -> bool:
    """Return whether any of ``elements`` needs the inline-``x`` probe pass.

    A fixed element's bbox is a function of its stored position and
    isolated size, so the cheap size pass places it. An inline
    element's ``bbox.x`` is the flowed cursor position, recovered only
    by the probe pass. A :class:`Group` inherits the need from any of
    its members. Used to pick the measurement tier for a given request.
    """

    def needs(el: Element) -> bool:
        if el.placement == "inline":
            return True
        if isinstance(el, Group):
            return any(needs(c) for c in el.children if c.placement != "omitted")
        return False

    return any(needs(el) for el in elements)


class TypstRenderer:
    """Backend writer that emits the final Typst source for compilation.

    Knows nothing about measurement: it only places elements via
    ``#place`` and styles them via ``#text(fill:)`` / ``#hide``.
    """

    def render_snapshot(
        self, elements: list[Element], canvas: tuple[float, float]
    ) -> str:
        """Render fixed root ``elements`` to a Typst fragment for one page.

        Top-level elements with ``placement != "fixed"`` are skipped (their
        semantics is "do not draw at the slide root"). The fragment carries
        no page preamble or pagebreak — those belong to the document.
        """
        lines: list[str] = []
        for el in elements:
            if el.placement != "fixed":
                continue
            lines.extend(_render_placed(el, self._render_node, canvas))
        return "\n".join(lines)

    def compile_document(
        self, fragments: list[str], canvas: tuple[float, float], path: str | Path
    ) -> None:
        """Assemble per-slide ``fragments`` and compile them to a PDF at ``path``.

        The document source is built in memory and handed to the bundled
        Typst compiler; no intermediate ``.typ`` is written. Consecutive
        fragments are separated by ``#pagebreak()``.
        """
        width, height = canvas
        preamble = f"#set page(width: {width}cm, height: {height}cm, margin: 0cm)\n"
        body = "\n#pagebreak()\n".join(fragments)
        source = preamble + "\n" + body + "\n"
        typst.compile(
            source.encode("utf-8"),
            output=str(path),
            root="/",
            font_paths=_font_paths(),
            ignore_system_fonts=True,
        )

    def _render_node(self, el: Element, placeholder: bool) -> str:
        """Render an element body (no ``#place`` wrapper).

        ``placeholder=True`` wraps the body in ``#hide[...]`` so the
        element still occupies space for layout purposes but is not
        drawn — used for fixed children whose visible copy lives in
        their own top-level ``#place`` block.
        """
        if isinstance(el, Text):
            if el.children:
                inner = "".join(
                    self._render_node(c, placeholder=c.placement == "fixed")
                    for c in el.children
                    if c.placement != "omitted"
                )
            else:
                inner = _markdown_to_typst(el.content)
            inner = _wrap_text_attrs(el, inner)
            if el.max_width is not None:
                inner = _wrap_max_width(
                    inner,
                    _wrap_line_gap(_wrap_align(inner, el.get_text_align()), el.line_gap),
                    el.max_width,
                )
        elif isinstance(el, (Rectangle, Circle, Ellipse)):
            inner = _shape_markup(el)
        elif isinstance(el, Line):
            inner = _line_markup(el)
        elif isinstance(el, Image):
            inner = _image_markup(el)
        elif isinstance(el, (VSpace, HSpace)):
            inner = _spacer_markup(el)
        elif isinstance(el, Group):
            inner = "".join(
                self._render_node(c, placeholder=c.placement == "fixed")
                for c in el.children
                if c.placement != "omitted"
            )
        else:
            inner = ""
        if el.hidden or placeholder:
            inner = f"#hide[{inner}]"
        return inner


class TypstMeasurer:
    """Backend measurer that fills ``_bbox`` over a list of root elements.

    The measurer is independent of slides and presentations: it is a
    pure function of the element tree rooted at each entry of ``roots``. Generates an auxiliary ``.typ``
    (at ``.mate_cache/measure.typ`` by default) and runs ``typst query`` on
    it. The auxiliary document contains up to two regions, both
    labeled ``<bbox>``:

    1. A ``#context [...]`` block with one ``#metadata((id, w, h))``
       per element, used to recover the *isolated* size of each. Always
       emitted; sufficient to place every fixed element.
    2. The same ``#place`` tree the renderer would emit (with
       ``canvas=None``, so no centring or y-flip is applied), with
       ``here().position()`` probes injected before every inline
       child. The probes recover the inline cursor's user-coordinate
       ``x`` directly — the fixed ancestor's left edge lives at the
       same Typst x in the aux doc as it does in user coordinates, so
       the cursor x flows through unchanged. The ``y`` of an inline
       child is *not* read from the aux doc; instead it is computed as
       ``ancestor_top_y - h`` (the bottom edge under the convention
       that the inline body's top sits at the line top of the nearest
       fixed ancestor). Typst's ``here().y`` returns the cursor
       baseline rather than the line top, so it cannot be used. This
       region — the costly part — is emitted only when the request
       needs an inline element's flowed position (``with_inline_x``).

    A single ``typst query`` call returns both kinds of records; we
    tell them apart by which keys are present (``w``/``h`` vs ``x``).
    The aux document opens with ``#set page(margin: 0cm)`` — page
    width/height are intentionally left at Typst's default since
    neither ``measure(...)`` of isolated content nor inline cursor
    recovery depends on page size, but the margin must be zero so
    that ``#place(top + left, ...)`` (body-relative) and
    ``here().position()`` (page-absolute) share the same coordinate
    system.

    Parameters
    ----------
    roots : list[Element]
        Top-level elements to measure (together with their subtrees).
    path : str or Path, optional
        Where to write the auxiliary document. Defaults to
        ``.mate_cache/measure.typ``.

    Attributes
    ----------
    elements : dict[int, Element]
        Flat ``mid -> element`` map of every node reachable from
        ``roots``; rebuilt at the start of each ``measure``.
    sizes : dict[int, tuple[float, float]]
        ``mid -> (w, h)`` parsed from the typst-query output.
    xs : dict[int, float]
        ``mid -> x`` for inline elements (the flowed cursor x),
        parsed from the same output.
    """

    def __init__(
        self,
        roots: list[Element],
        path: str | Path = _CACHE_MEASURE,
    ) -> None:
        self.roots = roots
        self.path = Path(path)
        self.elements: dict[int, Element] = {}
        self.sizes: dict[int, tuple[float, float]] = {}
        self.xs: dict[int, float] = {}

    def measure(self, with_inline_x: bool = True) -> None:
        """Run a measurement pass and assign ``_bbox`` on the reachable tree.

        The size records (region 1) are always emitted; they suffice to
        place every fixed element. The ``#place`` tree with inline
        ``x`` probes (region 2) is emitted only when ``with_inline_x``
        is set — it is the expensive part and is needed solely to give
        inline elements their flowed bbox. When it is skipped, inline
        nodes (and any :class:`Group` whose union depends on one) are
        left with ``_bbox = None`` so the next :meth:`get_bbox` re-runs
        with probes.

        Steps
        -----
        1. Walk every root and collect descendants into ``self.elements``.
        2. Emit the auxiliary ``.typ`` (size queries, plus the probe
           tree when ``with_inline_x``).
        3. Run ``typst query`` and split the output into ``sizes`` /
           ``xs``.
        4. Walk every root again to assign each element's bbox,
           threading the y of the nearest fixed ancestor.
        """
        self.elements.clear()
        self.sizes.clear()
        self.xs.clear()
        for el in self.roots:
            self._collect(el)

        _assert_fonts_available(
            {el.font for el in self.elements.values() if isinstance(el, Text)}
        )

        lines = [
            "#set page(margin: 0cm)",
            "",
            "#context [",
        ]
        # One metadata record per element, asking Typst for its isolated
        # (w, h) via `measure(...)`. Wrapped once in `#context [...]` so
        # the call is valid in template scope.
        for mid, el in self.elements.items():
            c = "[" + _bare(el) + "]"
            lines.append(
                f"  #metadata((id: {mid}, "
                f"w: measure({c}).width/1cm, "
                f"h: measure({c}).height/1cm))<bbox>"
            )
        lines.append("]")
        if with_inline_x:
            # Mirror the real render so `here().position()` probes see the
            # actual layout flow; fixed roots become `#place` blocks.
            for el in self.roots:
                if el.placement != "fixed":
                    continue
                lines.extend(_render_placed(el, self._render_node))
        _write(self.path, "\n".join(lines) + "\n")

        # Demux the records by which keys they carry. Size and x
        # records share the same `<bbox>` label because typst-query is
        # invoked once per measurement pass.
        for e in self._query():
            if "w" in e:
                self.sizes[e["id"]] = (e["w"], e["h"])
            else:
                self.xs[e["id"]] = e["x"]

        # Inline-at-root is unusual but tolerated: ancestor_top_y=0 by
        # convention, so the inline root's bbox.y collapses to `-h`.
        # Fixed roots recompute their own y from `_pos` and anchor
        # inside `_assign`, so the seed only matters for the inline case.
        for el in self.roots:
            if el.placement == "omitted":
                continue
            self._assign(el, ancestor_top_y=0.0)

    def _query(self) -> list[dict[str, Any]]:
        """Query the auxiliary document for ``<bbox>`` records via typst-py.

        Runs in-process against the bundled Typst compiler with system fonts
        ignored and ``_font_paths()`` on the font path. ``root="/"`` lets the
        absolute image paths emitted by ``_image_markup`` resolve to the
        filesystem.
        """
        out = typst.query(
            str(self.path),
            "<bbox>",
            field="value",
            ignore_system_fonts=True,
            font_paths=_font_paths(),
            root="/",
        )
        return json.loads(out)

    def _collect(self, el: Element) -> None:
        """Register ``el`` and its subtree into ``self.elements``.

        Omitted subtrees are pruned: they don't produce metadata
        records and don't get a bbox.
        """
        if el.placement == "omitted":
            return
        self.elements[el._mid] = el
        for c in el.children:
            self._collect(c)

    def _render_node(self, el: Element, placeholder: bool) -> str:
        """Like :meth:`TypstRenderer._render_node` but injects x-probes.

        Each inline child is preceded by an ``x`` probe so Typst can
        report its flowed cursor x. Fixed children are rendered as
        placeholders (the visible copy is emitted at the top level by
        ``_render_placed``).
        """
        if isinstance(el, Text):
            if el.children:
                inner = self._render_children_with_probes(el)
            else:
                inner = _markdown_to_typst(el.content)
            inner = _wrap_text_attrs(el, inner)
            if el.max_width is not None:
                # Width comes from the probe-free body; probes are
                # zero-width and must not leak into the measurement.
                # Alignment shifts where inline-x probes land, so it wraps
                # the probe-carrying render body to match the renderer.
                inner = _wrap_max_width(
                    _bare(el),
                    _wrap_line_gap(_wrap_align(inner, el.get_text_align()), el.line_gap),
                    el.max_width,
                )
        elif isinstance(el, (Rectangle, Circle, Ellipse)):
            inner = _shape_markup(el)
        elif isinstance(el, Line):
            inner = _line_markup(el)
        elif isinstance(el, Image):
            inner = _image_markup(el)
        elif isinstance(el, (VSpace, HSpace)):
            inner = _spacer_markup(el)
        elif isinstance(el, Group):
            inner = self._render_children_with_probes(el)
        else:
            inner = ""
        if el.hidden or placeholder:
            inner = f"#hide[{inner}]"
        return inner

    def _render_children_with_probes(self, el: Element) -> str:
        """Render ``el.children`` injecting x-probes before inline ones.

        Shared by the :class:`Text`-composite and :class:`Group`
        branches: omitted children are pruned, fixed children are
        rendered as placeholders (their visible copy lives in their
        own top-level ``#place``), and inline children get an x-probe
        so the measurer can recover their flowed cursor x.
        """
        parts = []
        for c in el.children:
            if c.placement == "omitted":
                continue
            c_fixed = c.placement == "fixed"
            rendered = self._render_node(c, placeholder=c_fixed)
            if not c_fixed:
                rendered = self._x_marker(c._mid) + rendered
            parts.append(rendered)
        return "".join(parts)

    @staticmethod
    def _x_marker(mid: int) -> str:
        """Return the Typst snippet that records ``here().position().x`` for ``mid``."""
        return (
            "#context { let p = here().position(); "
            f"[#metadata((id: {mid}, x: p.x/1cm))<bbox>] "
            "}"
        )

    def _assign(self, el: Element, ancestor_top_y: float) -> None:
        """Write ``el._bbox`` and recurse, threading the fixed-ancestor top y.

        Convention: bbox is always ``(x, y, w, h)`` with ``(x, y)`` the
        geometric **centre** in slide coordinates (y-up) and ``w``,
        ``h`` positive extents. The four edges are derived as
        ``left = x - w/2``, ``right = x + w/2``, ``bottom = y - h/2``,
        ``top = y + h/2``. For *fixed* elements the body is rendered
        so its ``_anchor`` point lands at ``_pos``, which means the
        centre offsets from ``_pos`` by ``((0.5 - h_mul) * w,
        (0.5 - v_mul) * h)`` where ``(h_mul, v_mul)`` are the anchor's
        offset multipliers. For *inline* elements ``bbox.x`` is the
        flowed cursor x (recovered via the ``here().position()`` probe)
        shifted by ``+ w/2`` to the centre; ``bbox.y`` is
        ``ancestor_top_y - h/2`` under the convention that the inline
        body's top sits at the line top of the nearest fixed ancestor.
        Typst's ``here().y`` returns the cursor baseline rather than
        the line top, so it cannot be used directly; the line-top y is
        threaded down via ``ancestor_top_y`` instead. This is what
        makes ``shift((0, 0))`` on an inline element a true visual
        no-op: freezing ``_pos`` to the measured anchor point and
        re-emitting via the same ``#place`` formula overlaps the
        inline rendering.
        :class:`Group` is special: its bbox is computed *after* the
        children are assigned, as the union of their bboxes; its own
        ``_pos`` has no rendered body to anchor.

        A sizes-only pass (no inline ``x`` records) cannot place inline
        elements: such a node is left with ``_bbox = None``, and a
        :class:`Group` whose union would include one is left ``None``
        too rather than caching a partial union. The next
        :meth:`get_bbox` then re-measures with probes.
        """
        w, h = self.sizes.get(el._mid, (0.0, 0.0))
        if el.placement == "fixed":
            h_mul, v_mul = anchor_offsets(el._anchor)
            cx = el._pos.x + (0.5 - h_mul) * w
            cy = el._pos.y + (0.5 - v_mul) * h
            child_top_y = cy + h / 2
        else:
            cx = self.xs.get(el._mid, 0.0) + w / 2
            cy = ancestor_top_y - h / 2
            child_top_y = ancestor_top_y
        for c in el.children:
            if c.placement == "omitted":
                continue
            self._assign(c, child_top_y)
        if isinstance(el, Group):
            members = [c for c in el.children if c.placement != "omitted"]
            if not members:
                el._bbox = (cx, cy, 0.0, 0.0)
            elif all(c._bbox is not None for c in members):
                boxes = [c._bbox for c in members]
                lefts = [b[0] - b[2] / 2 for b in boxes]
                rights = [b[0] + b[2] / 2 for b in boxes]
                bottoms = [b[1] - b[3] / 2 for b in boxes]
                tops = [b[1] + b[3] / 2 for b in boxes]
                left, right = min(lefts), max(rights)
                bottom, top = min(bottoms), max(tops)
                el._bbox = (
                    (left + right) / 2,
                    (bottom + top) / 2,
                    right - left,
                    top - bottom,
                )
        elif el.placement == "fixed" or el._mid in self.xs:
            el._bbox = (cx, cy, w, h)
