from __future__ import annotations

from typing import NoReturn

from ..config import config
from .element import Anchor, Element, HAlign, Placement
from .gradient import Gradient
from .registry import IDKey
from .vec import VecLike


def _resolve_paint(color: str | Gradient | None) -> str | Gradient | None:
    """Resolve a paint argument: a palette name to hex, a Gradient/None as is."""
    if color is None or isinstance(color, Gradient):
        return color
    return config.colors.get(color)


_STROKE_CAPS = ("butt", "round", "square")
_STROKE_JOINS = ("miter", "round", "bevel")
_STROKE_DASH_PRESETS = (
    "solid",
    "dotted",
    "densely-dotted",
    "loosely-dotted",
    "dashed",
    "densely-dashed",
    "loosely-dashed",
    "dash-dotted",
    "densely-dash-dotted",
    "loosely-dash-dotted",
)


def _validate_stroke_cap(cap: str | None) -> None:
    if cap is not None and cap not in _STROKE_CAPS:
        raise ValueError(f"stroke_cap must be one of {_STROKE_CAPS}, got {cap!r}")


def _validate_stroke_join(join: str | None) -> None:
    if join is not None and join not in _STROKE_JOINS:
        raise ValueError(f"stroke_join must be one of {_STROKE_JOINS}, got {join!r}")


def _validate_stroke_dash(dash: str | list[float] | None) -> None:
    if dash is None:
        return
    if isinstance(dash, str):
        if dash not in _STROKE_DASH_PRESETS:
            raise ValueError(
                f"stroke_dash preset must be one of {_STROKE_DASH_PRESETS}, "
                f"got {dash!r}"
            )
        return
    if isinstance(dash, (list, tuple)) and dash and all(
        isinstance(x, (int, float)) and x > 0 for x in dash
    ):
        return
    raise ValueError(
        "stroke_dash must be a preset name or a non-empty list of positive "
        f"cm lengths, got {dash!r}"
    )


class Drawable(Element):
    """Element with a visible body that carries fill/stroke styling.

    Adds optional visual properties on top of :class:`Element`:

    - ``fill_color``    — hex string or :class:`Gradient` for the fill. A
      palette name or literal hex is resolved via ``config.colors`` at
      construction and on ``set_fill_color``. Renders as ``"black"`` when
      ``None``.
    - ``stroke_color``  — hex string or :class:`Gradient` for the stroke,
      resolved the same way. Renders as ``"black"`` when ``None``
      (irrelevant when ``stroke_width == 0``).
    - ``fill_opacity``  — Float in ``[0, 1]``. Renders as ``1`` when
      ``None``. Setting ``0`` is the conventional way to ask for "no
      fill" (the renderer emits ``fill: none`` for shapes).
    - ``stroke_width``  — Stroke thickness in cm. Renders as ``0`` when
      ``None``, i.e. **no stroke** (the renderer emits
      ``stroke: none``).
    - ``stroke_dash``   — Dash pattern: a preset name (``"dashed"``,
      ``"dotted"``, ...) or a list of positive cm lengths. ``None`` is a
      solid line.
    - ``stroke_cap``    — Line-end shape: ``"butt"``, ``"round"``, or
      ``"square"``. ``None`` uses the backend default.
    - ``stroke_join``   — Corner shape: ``"miter"``, ``"round"``, or
      ``"bevel"``. ``None`` uses the backend default.
    - ``stroke_opacity``— Float in ``[0, 1]`` for the stroke paint.
      Renders as ``1`` when ``None``.

    Resolution and propagation
    --------------------------
    Each element carries its own concrete values; the backend resolves
    ``None`` to its defaults locally at render time. The ``set_*`` methods
    are the only way to change a field: with the default ``propagate=True``
    they walk the subtree and overwrite the chosen field on every
    :class:`Drawable` descendant (plain :class:`Element` descendants are
    skipped); with ``propagate=False`` they touch only the receiver.

    Parameters
    ----------
    fill_color, stroke_color : str or Gradient or None, optional
        A palette name (e.g. ``"red"``), a literal hex string (resolved to
        hex via ``config.colors``), or a :class:`Gradient`. Default ``None``
        → resolved to ``"black"`` at render time.
    fill_opacity : float or None, optional
        Default ``None`` → ``1``. Set to ``0`` for no fill.
    stroke_width : float or None, optional
        Default ``None`` → ``0`` (no stroke).
    stroke_dash : str or list of float or None, optional
        Dash preset name or a list of positive cm lengths. Default
        ``None`` → solid.
    stroke_cap : str or None, optional
        ``"butt"``, ``"round"``, or ``"square"``. Default ``None``.
    stroke_join : str or None, optional
        ``"miter"``, ``"round"``, or ``"bevel"``. Default ``None``.
    stroke_opacity : float or None, optional
        Default ``None`` → ``1``.
    pos, anchor, align, placement, id
        See :class:`Element`.
    """

    def __init__(
        self,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | Gradient | None = None,
        stroke_color: str | Gradient | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
        stroke_dash: str | list[float] | None = None,
        stroke_cap: str | None = None,
        stroke_join: str | None = None,
        stroke_opacity: float | None = None,
    ) -> None:
        super().__init__(pos=pos, anchor=anchor, align=align, placement=placement, id=id)
        _validate_stroke_cap(stroke_cap)
        _validate_stroke_join(stroke_join)
        _validate_stroke_dash(stroke_dash)
        self.fill_color: str | Gradient | None = _resolve_paint(fill_color)
        self.stroke_color: str | Gradient | None = _resolve_paint(stroke_color)
        self.fill_opacity: float | None = fill_opacity
        self.stroke_width: float | None = stroke_width
        self.stroke_dash: str | list[float] | None = stroke_dash
        self.stroke_cap: str | None = stroke_cap
        self.stroke_join: str | None = stroke_join
        self.stroke_opacity: float | None = stroke_opacity

    def get_fill_color(self) -> str | Gradient | None:
        """Return ``fill_color`` (hex or Gradient); ``None`` renders as ``"black"``."""
        return self.fill_color

    def get_stroke_color(self) -> str | Gradient | None:
        """Return ``stroke_color`` (hex or Gradient); ``None`` renders as ``"black"``."""
        return self.stroke_color

    def get_color(self) -> NoReturn:
        """Raise: a Drawable has two colors; use ``get_fill_color`` or ``get_stroke_color``."""
        raise AttributeError(
            "Drawable has no single color; use get_fill_color() or get_stroke_color()."
        )

    def get_fill_opacity(self) -> float | None:
        """Return ``fill_opacity``; ``None`` renders as ``1``."""
        return self.fill_opacity

    def get_opacity(self) -> float | None:
        """Return ``fill_opacity``; ``None`` renders as ``1``."""
        return self.fill_opacity

    def get_stroke_width(self) -> float | None:
        """Return ``stroke_width``; ``None`` renders as ``0``."""
        return self.stroke_width

    def get_stroke_dash(self) -> str | list[float] | None:
        """Return ``stroke_dash``; ``None`` renders as a solid line."""
        return self.stroke_dash

    def get_stroke_cap(self) -> str | None:
        """Return ``stroke_cap``; ``None`` uses the backend default."""
        return self.stroke_cap

    def get_stroke_join(self) -> str | None:
        """Return ``stroke_join``; ``None`` uses the backend default."""
        return self.stroke_join

    def get_stroke_opacity(self) -> float | None:
        """Return ``stroke_opacity``; ``None`` renders as ``1``."""
        return self.stroke_opacity

    def set_fill_color(
        self, color: str | Gradient | None, propagate: bool = True
    ) -> Drawable:
        """Set ``fill_color``; ``propagate`` cascades to Drawable descendants."""
        self._set_field("fill_color", _resolve_paint(color), propagate)
        return self

    def set_stroke_color(
        self, color: str | Gradient | None, propagate: bool = True
    ) -> Drawable:
        """Set ``stroke_color``; ``propagate`` cascades to Drawable descendants."""
        self._set_field("stroke_color", _resolve_paint(color), propagate)
        return self

    def set_color(
        self, color: str | Gradient | None, propagate: bool = True
    ) -> Drawable:
        """Set both ``fill_color`` and ``stroke_color``; ``propagate`` cascades."""
        self.set_fill_color(color, propagate)
        self.set_stroke_color(color, propagate)
        return self

    def set_opacity(self, opacity: float | None, propagate: bool = True) -> Drawable:
        """Set ``fill_opacity``; ``propagate`` cascades to Drawable descendants."""
        return self.set_fill_opacity(opacity, propagate)

    def set_stroke_dash(
        self, dash: str | list[float] | None, propagate: bool = True
    ) -> Drawable:
        """Set ``stroke_dash``; ``propagate`` cascades to Drawable descendants."""
        _validate_stroke_dash(dash)
        self._set_field("stroke_dash", dash, propagate)
        return self

    def set_stroke_cap(self, cap: str | None, propagate: bool = True) -> Drawable:
        """Set ``stroke_cap``; ``propagate`` cascades to Drawable descendants."""
        _validate_stroke_cap(cap)
        self._set_field("stroke_cap", cap, propagate)
        return self

    def set_stroke_join(self, join: str | None, propagate: bool = True) -> Drawable:
        """Set ``stroke_join``; ``propagate`` cascades to Drawable descendants."""
        _validate_stroke_join(join)
        self._set_field("stroke_join", join, propagate)
        return self

    def set_stroke_opacity(
        self, opacity: float | None, propagate: bool = True
    ) -> Drawable:
        """Set ``stroke_opacity``; ``propagate`` cascades to Drawable descendants."""
        self._set_field("stroke_opacity", opacity, propagate)
        return self

    def set_fill_opacity(
        self, opacity: float | None, propagate: bool = True
    ) -> Drawable:
        """Set ``fill_opacity``; ``propagate`` cascades to Drawable descendants."""
        self._set_field("fill_opacity", opacity, propagate)
        return self

    def set_stroke_width(self, width: float | None, propagate: bool = True) -> Drawable:
        """Set ``stroke_width``; ``propagate`` cascades to Drawable descendants."""
        self._set_field("stroke_width", width, propagate)
        return self
