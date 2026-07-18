from __future__ import annotations

import atexit
import hashlib
import json
import string
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import typst

from ..config import config
from ..core.element import anchor_offsets
from ..core.gradient import Gradient
from ..elements.group import Group
from ..elements.image import Image
from ..elements.shapes import (
    Circle,
    Close,
    CubicTo,
    Curve,
    Ellipse,
    Line,
    LineTo,
    MoveTo,
    Polygon,
    QuadTo,
    Rectangle,
)
from ..elements.spacing import HSpace, VSpace
from ..elements.text import Text
from ..parser.ir import Bold, Code, Italic, LineBreak, Math, TextRun
from ..parser.markup import parse_markup

if TYPE_CHECKING:
    from ..core.drawable import Drawable
    from ..core.element import Element
    from ..parser.ir import Inline


class TypstError(RuntimeError):
    """The Typst compiler rejected generated markup.

    Carries the offending markup snippet (when one could be isolated) and the
    de-duplicated compiler diagnostics.
    """


def _typst_diagnostics(exc: Exception) -> str:
    """Return a typst-py error's diagnostics, de-duplicated, preserving order.

    The binding raises with ``failed to compile document: <diag>, <diag>, ...``
    that repeats the same diagnostic once per occurrence in the generated
    source. Strip the prefix and drop repeats.
    """
    message = str(exc)
    prefix = "failed to compile document: "
    body = message[len(prefix) :] if message.startswith(prefix) else message
    seen: list[str] = []
    for diagnostic in body.split(", "):
        if diagnostic not in seen:
            seen.append(diagnostic)
    return ", ".join(seen)


def _format_typst_error(markup: str | None, diagnostics: str) -> str:
    """Build the message for a :class:`TypstError` from the culprit and error."""
    if markup is None:
        return f"Typst rejected the generated markup.\nTypst error: {diagnostics}"
    return f"Typst rejected this markup:\n\n{markup}\n\nTypst error: {diagnostics}"


# Font directory bundled with the package, always on the Typst font path.
_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"


def _font_paths() -> list[str]:
    """Font directories handed to Typst: the project ``fonts/`` dir then
    every extra directory in ``config.font_paths``."""
    return [str(_FONTS_DIR), *config.font_paths]


def _user_preamble() -> str:
    """Return the ``typst.preamble`` config value, terminated with a newline.

    The block sits at the top of every measure and render document, ahead of
    the page setup; its imports and definitions are visible to all markup.
    Empty by default, yielding an empty string.
    """
    text = str(config.get("typst.preamble"))
    return text + "\n" if text else ""


# Resolvable family names per ``font_paths`` set, cached.
_FONT_FAMILIES: dict[tuple[str, ...], frozenset[str]] = {}

# Content signature of the font files per ``font_paths`` set, cached.
_FONT_SIGNATURES: dict[tuple[str, ...], str] = {}


def _font_signature() -> str:
    """Hash the font files reachable from ``_font_paths()`` by path, size and mtime.

    Two runs share a measurement only when they typeset against the same fonts;
    this catches an added, removed, or re-saved face (even a metric-only edit
    that leaves the family name unchanged). Typst's embedded faces are covered
    by the compiler version folded into the cache key separately.
    """
    key = tuple(_font_paths())
    signature = _FONT_SIGNATURES.get(key)
    if signature is None:
        h = hashlib.sha256()
        for directory in key:
            base = Path(directory)
            if not base.is_dir():
                continue
            for file in sorted(base.rglob("*")):
                if file.is_file():
                    stat = file.stat()
                    h.update(str(file).encode("utf-8"))
                    h.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\0".encode())
        signature = h.hexdigest()
        _FONT_SIGNATURES[key] = signature
    return signature


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
_CACHE_MEASURE_DB = Path(".mate_cache/measure_cache.json")

# Bumped whenever the measurement markup emitted for a size record changes, so
# entries written by an older emission scheme are not read back.
_CACHE_FORMAT_VERSION = "1"

try:
    _TYPST_VERSION = version("typst")
except PackageNotFoundError:
    _TYPST_VERSION = "unknown"


def _size_cache_key(body: str, font_signature: str) -> str:
    """Content key for the isolated size of an element measured as ``body``.

    The isolated ``(w, h)`` is a pure function of the Typst ``body`` handed to
    ``measure(...)``, the fonts it resolves against, and the compiler version;
    the format version guards against a change in how the record is emitted.
    """
    h = hashlib.sha256()
    h.update(_CACHE_FORMAT_VERSION.encode())
    h.update(b"\0")
    h.update(_TYPST_VERSION.encode())
    h.update(b"\0")
    h.update(font_signature.encode())
    h.update(b"\0")
    h.update(body.encode("utf-8"))
    return h.hexdigest()


class MeasureCache:
    """Persistent content-addressed store of isolated element sizes.

    Maps a :func:`_size_cache_key` to a measured ``(w, h)``. A hit lets the
    measurer skip emitting that element's ``measure(...)`` record, and when no
    record is left to emit, the whole Typst query is skipped. The file is
    rewritten on interpreter exit with exactly the keys touched this run, so it
    stays scoped to the current deck instead of accumulating stale entries.
    """

    def __init__(self, path: str | Path = _CACHE_MEASURE_DB) -> None:
        self.path = Path(path)
        self._store = self._load()
        self._live: dict[str, tuple[float, float]] = {}
        atexit.register(self.save)

    def _load(self) -> dict[str, tuple[float, float]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return {}
        return {key: (value[0], value[1]) for key, value in raw.items()}

    def get(self, key: str) -> tuple[float, float] | None:
        """Return the cached size for ``key``, promoting a hit into the live set."""
        if key in self._live:
            return self._live[key]
        value = self._store.get(key)
        if value is not None:
            self._live[key] = value
        return value

    def put(self, key: str, size: tuple[float, float]) -> None:
        """Record a freshly measured ``size`` for ``key``."""
        self._live[key] = (size[0], size[1])

    def save(self) -> None:
        """Write the keys touched this run, replacing the file atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {key: [w, h] for key, (w, h) in self._live.items()}
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self.path)


_MEASURE_CACHE: MeasureCache | None = None


def _measure_cache() -> MeasureCache:
    """Return the process-wide measurement cache, loading it on first use."""
    global _MEASURE_CACHE
    if _MEASURE_CACHE is None:
        _MEASURE_CACHE = MeasureCache()
    return _MEASURE_CACHE

# Function that turns an element into its rendered Typst string. The
# `placeholder` flag means "still take space but emit `#hide[...]`": used
# for fixed children whose content is re-emitted at the top level via
# `#place` and must not double-count in the parent's flow.
RenderNode = Callable[["Element", bool], str]


_TYPST_SPECIAL = set("\\`*_$#[]")


def _escape_char(c: str) -> str:
    """Backslash-escape ``c`` if it has special meaning in Typst markup."""
    return f"\\{c}" if c in _TYPST_SPECIAL else c


# Verbatim emission: every ASCII punctuation character is backslash-escaped
# (Typst renders any escaped punctuation literally) and every space becomes a
# no-break space, which Typst never collapses. This shuts off all markup-mode
# processing: smart quotes and dashes, comments, references, labels, lists.
_VERBATIM_ESCAPE = {ord(c): f"\\{c}" for c in string.punctuation} | {
    ord(" "): " "
}


def _verbatim_to_typst(s: str) -> str:
    """Emit ``s`` as literal Typst markup, exact characters and spacing."""
    return s.translate(_VERBATIM_ESCAPE)


def _leaf_text_markup(el: Text) -> str:
    """Emit the Typst markup for a leaf ``Text``'s own content.

    A ``verbatim`` leaf renders its content literally; any other leaf carries
    Markdown markup, translated via :func:`_markdown_to_typst`.
    """
    if el.verbatim:
        return _verbatim_to_typst(el.content)
    return _markdown_to_typst(el.content)


def _markdown_to_typst(s: str) -> str:
    r"""Translate the Markdown markup of ``s`` into Typst markup.

    Parses ``s`` into inline tokens and emits the Typst form of each:
    ``**bold**`` / ``*italic*`` / ``_italic_`` become ``*...*`` / ``_..._``,
    ``` `code` ``` and ``$math$`` keep their verbatim bodies, a hard line break
    becomes Typst's ``\`` line break, and every literal character is
    Typst-escaped when special.
    """
    return _inline_to_typst(parse_markup(s))


def _inline_to_typst(nodes: list[Inline]) -> str:
    """Emit the Typst markup for a list of inline tokens."""
    out: list[str] = []
    for node in nodes:
        if isinstance(node, TextRun):
            out.append("".join(_escape_char(c) for c in node.text))
        elif isinstance(node, Bold):
            out.append(f"*{_inline_to_typst(node.children)}*")
        elif isinstance(node, Italic):
            out.append(f"_{_inline_to_typst(node.children)}_")
        elif isinstance(node, Code):
            out.append(f"`{node.text}`")
        elif isinstance(node, Math):
            out.append(f"$ {node.raw} $" if node.display else f"${node.raw}$")
        elif isinstance(node, LineBreak):
            out.append("\\\n")
    return "".join(out)


def _math_node_attrs(node: Text) -> str:
    """Typst ``#text`` attributes for a math fragment's explicit style overrides.

    A math fragment inherits font, size and fill from its equation; only the
    fields it overrides (via markup or ``modify``) are non-``None``, and each
    becomes one ``#text`` attribute. An empty result means "inherit everything".
    """
    attrs: list[str] = []
    if node.fill_color is not None or node.fill_opacity is not None:
        attrs.append(
            f"fill: {_typst_fill(node.fill_color, node.fill_opacity, zero_is_none=False)}"
        )
    stroke = _typst_stroke(node)
    if stroke != "none":
        attrs.append(f"stroke: {stroke}")
    if node.weight is not None:
        weight = f'"{node.weight}"' if isinstance(node.weight, str) else node.weight
        attrs.append(f"weight: {weight}")
    if node.style is not None:
        attrs.append(f'style: "{node.style}"')
    if node.letter_spacing is not None:
        attrs.append(f"tracking: {node.letter_spacing}em")
    if node.font is not None:
        attrs.append(f'font: "{node.font}"')
    if node.fontsize is not None:
        attrs.append(f"size: {node.fontsize}pt")
    return ", ".join(attrs)


def _math_fragment_markup(node: Text, hidden_ids: set[int]) -> str:
    """Render one math fragment as inner equation markup (no outer ``$``).

    A fragment with style overrides wraps its body in ``#text(...)[$ ... $]``,
    keeping one outer equation so math spacing is preserved; a plain fragment
    contributes its raw math source. A fragment that is ``hidden`` or whose
    ``id()`` is in ``hidden_ids`` is wrapped in ``hide`` to hold its place.
    """
    if node.children:
        inner = "".join(_math_fragment_markup(c, hidden_ids) for c in node.children)
    else:
        inner = node.content
    attrs = _math_node_attrs(node)
    has_move = node.offset.x != 0 or node.offset.y != 0
    if attrs:
        frag = f"#text({attrs})[$ {inner} $]"
    elif node.angle or has_move:
        # `_wrap_rotate` and the `#move` embed the body as content; re-enter
        # math to keep the fragment's equation typesetting inside them.
        frag = f"$ {inner} $"
    else:
        frag = inner
    frag = _wrap_rotate(node, frag)
    if has_move:
        # Slide coordinates are y-up, Typst's y-down: a positive shift on y
        # takes a negative dy. `#move` offsets in place with no reflow,
        # leaving the fragment's original slot in the equation.
        frag = f"#box(move(dx: {node.offset.x}cm, dy: {-node.offset.y}cm)[{frag}])"
    if node.hidden or id(node) in hidden_ids:
        return f"#hide($ {frag} $)"
    return frag


def _math_run_markup(el: Text, hidden_ids: set[int] = frozenset()) -> str:
    """Render a math-run ``Text`` as one ``$...$`` equation.

    Fragments render in source order inside one equation: a plain fragment
    contributes its raw math source, a styled fragment wraps its body in a
    ``#text`` call, and a hidden or not-yet-revealed fragment is wrapped in
    ``hide`` to hold its place without drawing.
    """
    body = "".join(_math_fragment_markup(c, hidden_ids) for c in el.children)
    return f"$ {body} $" if el.math_display else f"${body}$"


_DEFAULT_FILL_COLOR = "black"
_DEFAULT_STROKE_COLOR = "black"


def _wrap_rotate(el: Element, body: str) -> str:
    """Wrap ``body`` in a centred ``#rotate`` when ``el`` carries an angle.

    ``el.angle`` is in degrees counterclockwise (slide coordinates are
    y-up); Typst's ``#rotate`` turns clockwise, and the emitted sign is
    negated. ``reflow: true`` grows the layout box to the rotated
    content's bounding box; ``measure(...)`` then reports the rotated
    axis-aligned extents and the element's bbox reflects the rotation.
    The ``#box`` keeps the rotation inline: a bare ``#rotate`` is a block
    that breaks the surrounding paragraph. An inline run spins in place
    within its line.
    """
    if not body or not el.angle:
        return body
    return (
        f"#box(rotate({-el.angle}deg, origin: center + horizon, "
        f"reflow: true)[{body}])"
    )


def _bare(el: Element) -> str:
    """Render ``el`` without `#place`/`#hide` wrappers (size-measurement form).

    Used by the measurer to ask Typst for the *isolated* size of each
    element via ``measure(...)``. Fill is dropped (it does not affect
    glyph metrics); positioning and visibility are not represented either.
    ``"omitted"`` children contribute nothing to the parent's size.
    """
    if isinstance(el, Text):
        if el.is_math_run:
            inner = _math_run_markup(el)
        elif el.children:
            inner = "".join(_bare(c) for c in el.children if c.placement != "omitted")
        else:
            inner = _leaf_text_markup(el)
        body = _wrap_text_attrs(el, inner, with_paint=False)
        if el.max_width is not None:
            # Width is measured from the leading-free body (leading does
            # not affect width); height from the leading-carrying body so
            # the recorded bbox reflects the wrapped line spacing.
            body = _wrap_max_width(body, _wrap_line_gap(body, el.line_gap), el.max_width)
        return _wrap_rotate(el, body)
    leaf = _leaf_markup(el)
    if leaf is not None:
        return _wrap_rotate(el, leaf)
    # Groups (and any unknown leaf) contribute nothing to size: the
    # group's bbox is computed as the union of children in `_assign`,
    # so the per-element measurement record is intentionally empty.
    return ""


def _transparentize(value: str, opacity: float) -> str:
    """Wrap a Typst colour ``value`` in ``.transparentize(...)`` when ``opacity < 1``."""
    if opacity == 1:
        return value
    return f"{value}.transparentize({(1.0 - opacity) * 100}%)"


def _typst_gradient(grad: Gradient, opacity: float) -> str:
    """Emit a Typst ``gradient.linear``/``gradient.radial`` for ``grad``.

    ``opacity`` is applied per stop; a Typst gradient carries no
    transparency of its own. A stop with an explicit position becomes
    ``(colour, N%)``; a positionless stop is emitted bare for even spacing.
    """
    stops = []
    for hex_color, pos in grad.stops:
        c = _transparentize(f'rgb("{hex_color}")', opacity)
        stops.append(c if pos is None else f"({c}, {pos * 100}%)")
    body = ", ".join(stops)
    if grad.kind == "linear":
        angle = f", angle: {grad.angle}deg" if grad.angle else ""
        return f"gradient.linear({body}{angle})"
    cx, cy = grad.center
    return (
        f"gradient.radial({body}, center: ({cx * 100}%, {cy * 100}%), "
        f"radius: {grad.radius * 100}%)"
    )


def _typst_paint(color: str | Gradient | None, opacity: float, default: str) -> str:
    """Resolve a paint (hex, :class:`Gradient`, or ``None``) to a Typst value.

    ``None`` falls back to ``default``. ``opacity`` transparentizes a solid
    colour, or each stop of a gradient.
    """
    if isinstance(color, Gradient):
        return _typst_gradient(color, opacity)
    c = f'rgb("{color}")' if color is not None else default
    return _transparentize(c, opacity)


def _typst_fill(
    color: str | Gradient | None, opacity: float | None, *, zero_is_none: bool = True
) -> str:
    """Resolve ``(fill_color, fill_opacity)`` into a Typst ``fill:`` value.

    With ``zero_is_none`` (the default), ``opacity == 0`` returns ``"none"`` —
    the "no fill" value. With ``zero_is_none=False``, ``opacity == 0`` is a
    fully transparent paint instead, for contexts where Typst rejects
    ``fill: none`` (such as ``#text``). ``color`` is a hex string, a
    :class:`Gradient`, or ``None`` (falling back to ``"black"``).
    """
    op = 1.0 if opacity is None else opacity
    if op == 0 and zero_is_none:
        return "none"
    return _typst_paint(color, op, _DEFAULT_FILL_COLOR)


def _typst_dash(dash: str | list[float]) -> str:
    """Translate a dash preset name or a list of cm lengths to a Typst dash value.

    A string is a Typst preset (``"dashed"``, ...); a list becomes a length
    array (``(0.2cm, 0.1cm)``).
    """
    if isinstance(dash, str):
        return f'"{dash}"'
    inner = ", ".join(f"{x}cm" for x in dash)
    return f"({inner},)" if len(dash) == 1 else f"({inner})"


def _typst_stroke(el: Drawable) -> str:
    """Resolve an element's stroke fields into a Typst ``stroke:`` value.

    Returns ``"none"`` when ``stroke_width`` is ``None`` or ``0`` (the
    canonical "no stroke" case). With only width and colour set, emits the
    compact ``"<width>cm + <paint>"``; when ``stroke_dash``/``stroke_cap``/
    ``stroke_join`` are present, emits a ``stroke(...)`` call carrying them.
    ``stroke_opacity`` transparentizes the paint; the paint falls back to
    ``"black"`` when ``stroke_color`` is ``None``.
    """
    w = 0.0 if el.stroke_width is None else el.stroke_width
    if w == 0:
        return "none"
    op = 1.0 if el.stroke_opacity is None else el.stroke_opacity
    paint = _typst_paint(el.stroke_color, op, _DEFAULT_STROKE_COLOR)
    if el.stroke_dash is None and el.stroke_cap is None and el.stroke_join is None:
        return f"{w}cm + {paint}"
    parts = [f"paint: {paint}", f"thickness: {w}cm"]
    if el.stroke_cap is not None:
        parts.append(f'cap: "{el.stroke_cap}"')
    if el.stroke_join is not None:
        parts.append(f'join: "{el.stroke_join}"')
    if el.stroke_dash is not None:
        parts.append(f"dash: {_typst_dash(el.stroke_dash)}")
    return f"stroke({', '.join(parts)})"


def _wrap_text_attrs(el: Text, inner: str, *, with_paint: bool = True) -> str:
    """Wrap ``inner`` in a ``#text(...)`` call with the element's font and
    size, plus ``weight``/``style``/``tracking`` when set and ``fill``/``stroke``
    when present.

    ``font`` and ``size`` are always emitted — every :class:`Text` carries
    them explicitly so the rendered output never relies on Typst's
    implicit fallback. ``fill:`` and ``stroke:`` are added only when the
    element has explicit fill/stroke state, otherwise the body inherits
    Typst's lexical defaults (black fill, no stroke, matching
    :class:`~mate.core.drawable.Drawable`'s visual defaults).
    ``with_paint=False`` drops both: neither affects glyph metrics, so the
    measurement form omits them to keep the aux document small.
    """
    attrs = [f'font: "{el.font}"', f"size: {el.fontsize}pt"]
    if el.weight is not None:
        weight = f'"{el.weight}"' if isinstance(el.weight, str) else el.weight
        attrs.append(f"weight: {weight}")
    if el.style is not None:
        attrs.append(f'style: "{el.style}"')
    if el.letter_spacing is not None:
        attrs.append(f"tracking: {el.letter_spacing}em")
    if with_paint and not (el.fill_color is None and el.fill_opacity is None):
        attrs.append(
            f"fill: {_typst_fill(el.fill_color, el.fill_opacity, zero_is_none=False)}"
        )
    if with_paint and not (el.stroke_color is None and el.stroke_width is None):
        attrs.append(f"stroke: {_typst_stroke(el)}")
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


def _typst_radius(corner_radius: float | dict[str, float]) -> str:
    """Emit the ``radius:`` argument of a ``#rect``, empty when every corner is sharp.

    A float becomes a single length; a dict becomes the per-corner dictionary
    Typst takes, with the corners left out staying sharp.
    """
    if isinstance(corner_radius, dict):
        entries = ", ".join(
            f"{corner}: {radius}cm" for corner, radius in corner_radius.items()
        )
        return f", radius: ({entries})" if entries else ""
    return f", radius: {corner_radius}cm" if corner_radius else ""


def _shape_markup(el: Rectangle | Circle | Ellipse) -> str:
    """Emit the Typst body for a filled shape primitive.

    Dispatches on the concrete type to ``#rect`` / ``#circle`` /
    ``#ellipse``. The fill/stroke pair comes from the element's own
    ``fill_color``/``fill_opacity``/``stroke_color``/``stroke_width``
    fields, resolved locally — no parent walk.
    """
    fill = _typst_fill(el.fill_color, el.fill_opacity)
    stroke = _typst_stroke(el)
    if isinstance(el, Rectangle):
        radius = _typst_radius(el.corner_radius)
        return (
            f"#rect(width: {el.width}cm, height: {el.height}cm, "
            f"fill: {fill}, stroke: {stroke}{radius})"
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
    stroke = _typst_stroke(el)
    return (
        f"#line(start: ({sx - left}cm, {top - sy}cm), "
        f"end: ({ex - left}cm, {top - ey}cm), stroke: {stroke})"
    )


def _local_point(p, left: float, top: float) -> str:
    """Map a local-frame point to Typst's y-down box frame as ``(x cm, y cm)``.

    ``left`` is the minimum x and ``top`` the maximum y over the shape's
    points, so the emitted coordinate is offset to the bbox's top-left
    corner and the y axis is flipped to Typst's downward convention. The
    shape then draws inside its own bounding box and ``measure(...)``
    returns the intrinsic extents.
    """
    return f"({p.x - left}cm, {top - p.y}cm)"


def _polygon_markup(el: Polygon) -> str:
    """Emit the Typst body for a :class:`Polygon`.

    Vertices are normalized to the bbox's top-left in Typst's y-down
    frame; ``#polygon`` closes the path automatically.
    """
    fill = _typst_fill(el.fill_color, el.fill_opacity)
    stroke = _typst_stroke(el)
    left = min(p.x for p in el.points)
    top = max(p.y for p in el.points)
    verts = ", ".join(_local_point(p, left, top) for p in el.points)
    return f"#polygon(fill: {fill}, stroke: {stroke}, {verts})"


def _curve_markup(el: Curve) -> str:
    """Emit the Typst body for a :class:`Curve`.

    Each segment maps to its ``curve.*`` form; all points are normalized
    to the bbox's top-left in Typst's y-down frame. The ``#curve`` sits
    inside a ``#box`` sized to the control-point bbox, which fixes
    ``measure(...)`` to that size for placement and anchoring. (Typst's
    native ``measure`` of a curve pins the box to the curve's origin and
    drops extents on the negative side.) The path lies within the convex
    hull of its control points, the box that bounds it.
    """
    fill = _typst_fill(el.fill_color, el.fill_opacity)
    stroke = _typst_stroke(el)
    points = el._all_points()
    left = min(p.x for p in points)
    top = max(p.y for p in points)

    def loc(p) -> str:
        return _local_point(p, left, top)

    parts: list[str] = [f"fill: {fill}", f"stroke: {stroke}"]
    for seg in el.segments:
        if isinstance(seg, MoveTo):
            parts.append(f"curve.move({loc(seg.point)})")
        elif isinstance(seg, LineTo):
            parts.append(f"curve.line({loc(seg.point)})")
        elif isinstance(seg, CubicTo):
            parts.append(
                f"curve.cubic({loc(seg.control_start)}, "
                f"{loc(seg.control_end)}, {loc(seg.point)})"
            )
        elif isinstance(seg, QuadTo):
            parts.append(f"curve.quad({loc(seg.control)}, {loc(seg.point)})")
        elif isinstance(seg, Close):
            parts.append("curve.close()")
    return (
        f"#box(width: {el.get_width()}cm, height: {el.get_height()}cm)"
        f"[#curve({', '.join(parts)})]"
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

    A crop window measures the rendered image and shows only its
    ``(x, y, width, height)`` fraction inside a ``#box(clip: true)``,
    placing the full image at a negative offset that lands the window's
    top-left at the box origin.
    """
    path = _escape_typst_string(str(Path(el.path).resolve()))
    attrs = [f'"{path}"']
    if el.width is not None:
        attrs.append(f"width: {el.width}cm")
    if el.height is not None:
        attrs.append(f"height: {el.height}cm")
    image = f"image({', '.join(attrs)})"
    if el.crop_window is None:
        return f"#{image}"
    x, y, w, h = el.crop_window
    return (
        f"#context {{ let im = {image}; let m = measure(im); "
        f"box(clip: true, width: m.width * {w}, height: m.height * {h}, "
        f"place(dx: -m.width * {x}, dy: -m.height * {y}, im)) }}"
    )


def _leaf_markup(el: Element) -> str | None:
    """Return the Typst body for a type-uniform leaf, or ``None``.

    Covers the elements whose body is the same in every pass — shapes, lines,
    images, spacers. Returns ``None`` for :class:`Text` and :class:`Group`,
    whose body depends on the pass (fill, hide, inline probes) and is built by
    each caller.
    """
    if isinstance(el, (Rectangle, Circle, Ellipse)):
        return _shape_markup(el)
    if isinstance(el, Line):
        return _line_markup(el)
    if isinstance(el, Polygon):
        return _polygon_markup(el)
    if isinstance(el, Curve):
        return _curve_markup(el)
    if isinstance(el, Image):
        return _image_markup(el)
    if isinstance(el, (VSpace, HSpace)):
        return _spacer_markup(el)
    return None


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


def _isolate_compile_culprit(fragments: list[str], preamble: str) -> str | None:
    """Return the first slide fragment that fails to compile on its own.

    Runs on the render error path: compiles each fragment under ``preamble``
    in isolation and returns the one Typst rejects, or ``None`` when no single
    fragment reproduces the failure.
    """
    for fragment in fragments:
        try:
            typst.compile(
                (preamble + "\n" + fragment + "\n").encode("utf-8"),
                root="/",
                font_paths=_font_paths(),
                ignore_system_fonts=True,
            )
        except RuntimeError:
            return fragment
    return None


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

    _hidden_now: set[int] = frozenset()

    def render_snapshot(
        self,
        elements: list[Element],
        canvas: tuple[float, float],
        hidden_ids: set[int] = frozenset(),
    ) -> str:
        """Render fixed root ``elements`` to a Typst fragment for one page.

        Top-level elements with ``placement != "fixed"`` are skipped (their
        semantics is "do not draw at the slide root"). Nodes whose ``id()`` is
        in ``hidden_ids`` are drawn with ``#hide``, which keeps their layout
        space without drawing them. The fragment carries no page preamble or
        pagebreak — those belong to the document.
        """
        self._hidden_now = hidden_ids
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
        preamble = (
            _user_preamble()
            + f"#set page(width: {width}cm, height: {height}cm, margin: 0cm)\n"
        )
        body = "\n#pagebreak()\n".join(fragments)
        source = preamble + "\n" + body + "\n"
        try:
            typst.compile(
                source.encode("utf-8"),
                output=str(path),
                root="/",
                font_paths=_font_paths(),
                ignore_system_fonts=True,
            )
        except RuntimeError as exc:
            culprit = _isolate_compile_culprit(fragments, preamble)
            raise TypstError(
                _format_typst_error(culprit, _typst_diagnostics(exc))
            ) from None

    def _render_node(self, el: Element, placeholder: bool) -> str:
        """Render an element body (no ``#place`` wrapper).

        ``placeholder=True`` wraps the body in ``#hide[...]`` so the
        element still occupies space for layout purposes but is not
        drawn — used for fixed children whose visible copy lives in
        their own top-level ``#place`` block.
        """
        if isinstance(el, Text):
            if el.is_math_run:
                inner = _math_run_markup(el, self._hidden_now)
            elif el.children:
                inner = "".join(
                    self._render_node(c, placeholder=c.placement == "fixed")
                    for c in el.children
                    if c.placement != "omitted"
                )
            else:
                inner = _leaf_text_markup(el)
            inner = _wrap_text_attrs(el, inner)
            if el.max_width is not None:
                inner = _wrap_max_width(
                    inner,
                    _wrap_line_gap(_wrap_align(inner, el.get_text_align()), el.line_gap),
                    el.max_width,
                )
        elif isinstance(el, Group):
            inner = "".join(
                self._render_node(c, placeholder=c.placement == "fixed")
                for c in el.children
                if c.placement != "omitted"
            )
        else:
            inner = _leaf_markup(el) or ""
        inner = _wrap_rotate(el, inner)
        if el.hidden or placeholder or id(el) in self._hidden_now:
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
       per element whose isolated size is not already in the persistent
       :class:`MeasureCache`, used to recover that size. Sufficient to
       place every fixed element.
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

        The size records (region 1) place every fixed element; each is
        served from the persistent :class:`MeasureCache` when its body
        was measured before, so only cache misses reach Typst. The
        ``#place`` tree with inline ``x`` probes (region 2) is emitted
        only when ``with_inline_x`` is set — it is the expensive part and
        is needed solely to give inline elements their flowed bbox. When
        it is skipped, inline nodes (and any :class:`Group` whose union
        depends on one) are left with ``_bbox = None`` so the next
        :meth:`get_bbox` re-runs with probes.

        Steps
        -----
        1. Walk every root and collect descendants into ``self.elements``.
        2. Resolve each isolated size from the cache; emit the auxiliary
           ``.typ`` only for the missed sizes (plus the probe tree when
           ``with_inline_x``).
        3. Run ``typst query`` when anything was emitted, split the output
           into ``sizes`` / ``xs``, and record the missed sizes.
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

        # Serve isolated sizes from the persistent cache; only elements that
        # miss need a `measure(...)` record. An element with an empty body (a
        # Group, whose bbox is the union of its children) measures to zero
        # without a query and is not cached.
        cache = _measure_cache()
        font_signature = _font_signature()
        bodies: dict[int, str] = {}
        keys: dict[int, str] = {}
        pending: list[int] = []
        for mid, el in self.elements.items():
            body = _bare(el)
            if not body:
                self.sizes[mid] = (0.0, 0.0)
                continue
            key = _size_cache_key(body, font_signature)
            keys[mid] = key
            cached = cache.get(key)
            if cached is not None:
                self.sizes[mid] = cached
            else:
                bodies[mid] = body
                pending.append(mid)

        lines = [_user_preamble() + "#set page(margin: 0cm)", ""]
        if pending:
            # One metadata record per cache-miss element, asking Typst for its
            # isolated (w, h) via `measure(...)`. Wrapped once in `#context
            # [...]` so the call is valid in template scope.
            lines.append("#context [")
            for mid in pending:
                c = "[" + bodies[mid] + "]"
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

        # The query is needed only for missed sizes or for the inline-x probes;
        # a fully cached size-only pass spawns no Typst process.
        if pending or with_inline_x:
            _write(self.path, "\n".join(lines) + "\n")
            # Demux the records by which keys they carry. Size and x
            # records share the same `<bbox>` label because typst-query is
            # invoked once per measurement pass.
            for e in self._query():
                if "w" in e:
                    mid = e["id"]
                    size = (e["w"], e["h"])
                    self.sizes[mid] = size
                    cache.put(keys[mid], size)
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
        try:
            out = typst.query(
                str(self.path),
                "<bbox>",
                field="value",
                ignore_system_fonts=True,
                font_paths=_font_paths(),
                root="/",
            )
        except RuntimeError as exc:
            culprit = self._isolate_measure_culprit()
            raise TypstError(
                _format_typst_error(culprit, _typst_diagnostics(exc))
            ) from None
        return json.loads(out)

    def _isolate_measure_culprit(self) -> str | None:
        """Return the first element's markup that fails to measure on its own.

        Runs on the measurement error path: measures each collected element's
        bare markup in isolation and returns the one Typst rejects, or ``None``
        when no single element reproduces the failure.
        """
        for el in self.elements.values():
            bare = _bare(el)
            if not bare:
                continue
            probe = (
                _user_preamble()
                + "#set page(margin: 0cm)\n"
                + f"#context [ #metadata(measure([{bare}]).width/1cm)<bbox> ]\n"
            )
            _write(self.path, probe)
            try:
                typst.query(
                    str(self.path),
                    "<bbox>",
                    field="value",
                    ignore_system_fonts=True,
                    font_paths=_font_paths(),
                    root="/",
                )
            except RuntimeError:
                return bare
        return None

    def _collect(self, el: Element) -> None:
        """Register ``el`` and its subtree into ``self.elements``.

        Omitted subtrees are pruned: they don't produce metadata
        records and don't get a bbox.
        """
        if el.placement == "omitted":
            return
        self.elements[el._mid] = el
        # A math run is measured as one equation; its fragment children are
        # reveal markers carried inside that equation, not standalone nodes.
        if isinstance(el, Text) and el.is_math_run:
            return
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
            if el.is_math_run:
                inner = _math_run_markup(el)
            elif el.children:
                inner = self._render_children_with_probes(el)
            else:
                inner = _leaf_text_markup(el)
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
        elif isinstance(el, Group):
            inner = self._render_children_with_probes(el)
        else:
            inner = _leaf_markup(el) or ""
        inner = _wrap_rotate(el, inner)
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
        children = [] if isinstance(el, Text) and el.is_math_run else el.children
        for c in children:
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
