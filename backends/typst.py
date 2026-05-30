from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..core.element import anchor_offsets
from ..elements.group import Group
from ..elements.shapes import Circle, Ellipse, Rectangle
from ..elements.text import Text

if TYPE_CHECKING:
    from ..core.element import Element
    from ..core.presentation import Slide


_CACHE_MEASURE = Path(".cache/measure.typ")

# Function that turns an element into its rendered Typst string. The
# `placeholder` flag means "still take space but emit `#hide[...]`": used
# for fixed children whose content is re-emitted at the top level via
# `#place` and must not double-count in the parent's flow.
RenderNode = Callable[["Element", bool], str]


def _escape(s: str) -> str:
    """Escape characters that have special meaning in Typst markup."""
    return (
        s.replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("#", "\\#")
    )


_DEFAULT_FILL_COLOR = "black"
_DEFAULT_STROKE_COLOR = "black"


def _bare(el: Element) -> str:
    """Render ``el`` without `#place`/`#hide` wrappers (size-measurement form).

    Used by the measurer to ask Typst for the *isolated* size of each
    element via ``measure(...)``. Fill color is preserved since it can
    affect glyph metrics; positioning and visibility are not.
    ``"omitted"`` children contribute nothing to the parent's size.
    """
    if isinstance(el, Text):
        if el.children:
            inner = "".join(_bare(c) for c in el.children if c.placement != "omitted")
        else:
            inner = _escape(el.content)
        return _wrap_text_attrs(el, inner)
    if isinstance(el, (Rectangle, Circle, Ellipse)):
        return _shape_markup(el)
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


def _wrap_text_attrs(el: Text, inner: str) -> str:
    """Wrap ``inner`` in ``#text(font: ..., size: ...pt, fill: ...)``.

    ``font`` and ``size`` are always emitted — every :class:`Text` carries
    them explicitly so the rendered output never relies on Typst's
    implicit fallback. ``fill:`` is added only when the element has
    explicit fill state, otherwise the body inherits Typst's lexical
    default (black, matching :class:`~mate.core.drawable.Drawable`'s
    visual default).
    """
    attrs = [f'font: "{el.font}"', f"size: {el.size}pt"]
    if not (el.fill_color is None and el.fill_opacity is None):
        attrs.append(f"fill: {_typst_fill(el.fill_color, el.fill_opacity)}")
    return f'#text({", ".join(attrs)})[{inner}]'


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


class TypstRenderer:
    """Backend writer that emits the final Typst source for compilation.

    Knows nothing about measurement: it only places elements via
    ``#place`` and styles them via ``#text(fill:)`` / ``#hide``.
    """

    def render_slide(self, slide: Slide, canvas: tuple[float, float]) -> str:
        """Render a slide's fixed root elements to a Typst fragment.

        Top-level elements with ``placement != "fixed"`` are skipped (their
        semantics is "do not draw at the slide root"). The fragment carries
        no page preamble or pagebreak — those belong to the document.
        """
        lines: list[str] = []
        for el in slide.elements:
            if el.placement != "fixed":
                continue
            lines.extend(_render_placed(el, self._render_node, canvas))
        return "\n".join(lines)

    def write_document(
        self, fragments: list[str], canvas: tuple[float, float], path: str | Path
    ) -> None:
        """Assemble per-slide ``fragments`` into one ``.typ`` at ``path``.

        Consecutive fragments are separated by ``#pagebreak()``.
        """
        path = Path(path)
        if not fragments:
            _write(path, "")
            return
        width, height = canvas
        preamble = f"#set page(width: {width}cm, height: {height}cm, margin: 0cm)\n"
        body = "\n#pagebreak()\n".join(fragments)
        _write(path, preamble + "\n" + body + "\n")

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
                inner = _escape(el.content)
            inner = _wrap_text_attrs(el, inner)
        elif isinstance(el, (Rectangle, Circle, Ellipse)):
            inner = _shape_markup(el)
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

    The measurer is independent of :class:`Slide` and
    :class:`Presentation`: it is a pure function of the element tree
    rooted at each entry of ``roots``. Generates an auxiliary ``.typ``
    (at ``.cache/measure.typ`` by default) and runs ``typst query`` on
    it. The auxiliary document contains two complementary regions,
    both labeled ``<bbox>``:

    1. A ``#context [...]`` block with one ``#metadata((id, w, h))``
       per element, used to recover the *isolated* size of each.
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
       baseline rather than the line top, so it cannot be used.

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
        ``.cache/measure.typ``.

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

    def measure(self) -> None:
        """Run a full measurement pass and assign ``_bbox`` on every element.

        Steps
        -----
        1. Walk every root and collect descendants into ``self.elements``.
        2. Emit the auxiliary ``.typ`` (size queries + fixed tree with
           inline ``x`` probes).
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
        """Run ``typst query`` and return the parsed JSON list."""
        result = subprocess.run(
            [
                "typst",
                "query",
                "--ignore-system-fonts",
                str(self.path),
                "<bbox>",
                "--field",
                "value",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

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
                inner = _escape(el.content)
            inner = _wrap_text_attrs(el, inner)
        elif isinstance(el, (Rectangle, Circle, Ellipse)):
            inner = _shape_markup(el)
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
            boxes = [
                c._bbox
                for c in el.children
                if c.placement != "omitted" and c._bbox is not None
            ]
            if boxes:
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
            else:
                el._bbox = (cx, cy, 0.0, 0.0)
        else:
            el._bbox = (cx, cy, w, h)
