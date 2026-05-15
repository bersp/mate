from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ..elements.group import Group
from ..elements.shapes import Circle, Ellipse, Rectangle
from ..elements.text import Text

if TYPE_CHECKING:
    from ..core.element import Element
    from ..core.presentation import Presentation


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
            inner = "".join(
                _bare(c) for c in el.children if c.placement != "omitted"
            )
        else:
            inner = _escape(el.content)
        return _wrap_text_fill(el, inner)
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
    c = color if color is not None else _DEFAULT_FILL_COLOR
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
    c = color if color is not None else _DEFAULT_STROKE_COLOR
    return f"{w}cm + {c}"


def _wrap_text_fill(el: Text, inner: str) -> str:
    """Wrap ``inner`` in ``#text(fill: ...)`` when the element has explicit fill.

    Skipped entirely when both ``fill_color`` and ``fill_opacity`` are
    ``None`` so the body inherits Typst's lexical default (which is
    black, matching :class:`~mate.core.drawable.Drawable`'s visual default).
    """
    if el.fill_color is None and el.fill_opacity is None:
        return inner
    return f'#text(fill: {_typst_fill(el.fill_color, el.fill_opacity)})[{inner}]'


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
            f'#rect(width: {el.width}cm, height: {el.height}cm, '
            f'fill: {fill}, stroke: {stroke})'
        )
    if isinstance(el, Circle):
        return (
            f'#circle(radius: {el.radius}cm, '
            f'fill: {fill}, stroke: {stroke})'
        )
    return (
        f'#ellipse(width: {el.width}cm, height: {el.height}cm, '
        f'fill: {fill}, stroke: {stroke})'
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


def _render_placed(el: Element, render_node: RenderNode) -> list[str]:
    """Emit ``#place`` blocks for ``el`` and every fixed descendant.

    Each fixed element becomes a top-level ``#context { ... place(top + left, ...) }``
    block whose ``dx``/``dy`` shift the body's measured center to
    ``_center``. Typst's ``measure(...)`` is called inline so the
    renderer does not need a Python pre-measure pass. Fixed descendants
    are emitted as siblings (not nested), so Typst's flow does not
    stack them inside the parent — only the explicit dx/dy decides
    position.

    Parameters
    ----------
    el : Element
        Fixed root.
    render_node : RenderNode
        Backend-specific body renderer (renderer vs measurer differ
        only in this callable).

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
        body = f'#hide[{body}]'
    out = [
        '#context { '
        f'let __b = [{body}]; '
        'let __s = measure(__b); '
        f'place(top + left, dx: {el._center.x}cm - __s.width/2, '
        f'dy: {el._center.y}cm - __s.height/2, __b) '
        '}'
    ]
    for sub in _collect_fixed(el):
        out.extend(_render_placed(sub, render_node))
    return out


def _write(path: Path, content: str) -> None:
    """Write ``content`` to ``path``, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TypstRenderer:
    """Backend writer that emits the final Typst source for compilation.

    Knows nothing about measurement: it only places elements via
    ``#place`` and styles them via ``#text(fill:)`` / ``#hide``.

    Parameters
    ----------
    path : str or Path
        Destination ``.typ`` file.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def render(self, presentation: Presentation) -> None:
        """Serialize ``presentation`` to ``self.path``.

        Each slide becomes a page; consecutive slides are separated by
        ``#pagebreak()``. Top-level elements with ``placement != "fixed"``
        are skipped (their semantics is "do not draw at the slide root").
        """
        if not presentation.slides:
            _write(self.path, "")
            return
        lines = [
            f'#set page(width: {presentation.width}cm, '
            f'height: {presentation.height}cm, margin: 0cm)',
            '',
        ]
        for i, slide in enumerate(presentation.slides):
            if i > 0:
                lines.append('#pagebreak()')
            for el in slide.elements:
                if el.placement != "fixed":
                    continue
                lines.extend(_render_placed(el, self._render_node))
        _write(self.path, "\n".join(lines) + "\n")

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
            inner = _wrap_text_fill(el, inner)
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
            inner = f'#hide[{inner}]'
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
    2. The same ``#place`` tree the renderer would emit, but with
       ``here().position()`` probes injected before every inline child,
       used to recover the actual ``x`` after parent flow. The ``y`` of
       an inline child is taken by convention to be the top-left ``y``
       of the nearest fixed ancestor's rendered body (= the line top
       under top-aligned placement) — Typst's ``here().y`` returns the
       cursor baseline rather than the line top, so it cannot be used
       directly to make ``#place(center + horizon, dx, dy)`` overlap
       the inline visual.

    A single ``typst query`` call returns both kinds of records; we
    tell them apart by which keys are present (``w``/``h`` vs ``x``).
    The aux document opens with ``#set page(margin: 0cm)`` — page
    width/height are intentionally left at Typst's default since
    neither ``measure(...)`` of isolated content nor fixed-position
    placement depends on page size, but the margin must be zero so
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
            '#set page(margin: 0cm)',
            '',
            '#context [',
        ]
        # One metadata record per element, asking Typst for its isolated
        # (w, h) via `measure(...)`. Wrapped once in `#context [...]` so
        # the call is valid in template scope.
        for mid, el in self.elements.items():
            c = '[' + _bare(el) + ']'
            lines.append(
                f'  #metadata((id: {mid}, '
                f'w: measure({c}).width/1cm, '
                f'h: measure({c}).height/1cm))<bbox>'
            )
        lines.append(']')
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
            if 'w' in e:
                self.sizes[e['id']] = (e['w'], e['h'])
            else:
                self.xs[e['id']] = e['x']

        # Inline-at-root is unusual but tolerated: y=0 by convention.
        # Fixed roots seed `ancestor_y` from their own center.y.
        for el in self.roots:
            if el.placement == "omitted":
                continue
            ay = el._center.y if el.placement == "fixed" else 0.0
            self._assign(el, ancestor_y=ay)

    def _query(self) -> list[dict[str, Any]]:
        """Run ``typst query`` and return the parsed JSON list."""
        result = subprocess.run(
            ['typst', 'query', '--ignore-system-fonts',
             str(self.path), '<bbox>', '--field', 'value'],
            capture_output=True, text=True, check=True,
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
            inner = _wrap_text_fill(el, inner)
        elif isinstance(el, (Rectangle, Circle, Ellipse)):
            inner = _shape_markup(el)
        elif isinstance(el, Group):
            inner = self._render_children_with_probes(el)
        else:
            inner = ""
        if el.hidden or placeholder:
            inner = f'#hide[{inner}]'
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
            '#context { let p = here().position(); '
            f'[#metadata((id: {mid}, x: p.x/1cm))<bbox>] '
            '}'
        )

    def _assign(self, el: Element, ancestor_y: float) -> None:
        """Write ``el._bbox`` and recurse, threading the fixed-ancestor y.

        Convention: bbox is always ``(x, y, w, h)`` with ``(x, y)`` the
        top-left in slide coordinates. For *fixed* elements the body is
        rendered with ``#place(top + left, dx, dy)`` shifted so the
        body's measured center lands at ``_center``, so the top-left is
        ``(_center.x - w/2, _center.y - h/2)``. For *inline* elements
        ``bbox.x`` is the flowed cursor x recovered via the
        ``here().position()`` probe; ``bbox.y`` is the ``ancestor_y``
        threaded down — the top-left of the rendered body of the
        nearest fixed ancestor (= line top under top-aligned
        placement). This is what makes ``shift((0, 0))`` on an inline
        element a true visual no-op: freezing the element's
        ``_center`` to the bbox center and re-emitting via the same
        ``#place`` formula overlaps the inline rendering.
        :class:`Group` is special: its bbox is computed *after* the
        children are assigned, as the union of their bboxes; its own
        ``_center`` has no rendered body to anchor.
        """
        w, h = self.sizes.get(el._mid, (0.0, 0.0))
        if el.placement == "fixed":
            x = el._center.x - w / 2
            y = el._center.y - h / 2
            child_y = y
        else:
            x = self.xs.get(el._mid, 0.0)
            y = ancestor_y
            child_y = ancestor_y
        for c in el.children:
            if c.placement == "omitted":
                continue
            self._assign(c, child_y)
        if isinstance(el, Group):
            boxes = [
                c._bbox for c in el.children
                if c.placement != "omitted" and c._bbox is not None
            ]
            if boxes:
                x0 = min(b[0] for b in boxes)
                y0 = min(b[1] for b in boxes)
                x1 = max(b[0] + b[2] for b in boxes)
                y1 = max(b[1] + b[3] for b in boxes)
                el._bbox = (x0, y0, x1 - x0, y1 - y0)
            else:
                el._bbox = (x, y, 0.0, 0.0)
        else:
            el._bbox = (x, y, w, h)
