from __future__ import annotations

from .element import Anchor, Element, Placement
from .registry import IDKey
from .vec import VecLike


class Drawable(Element):
    """Element with a visible body that carries fill/stroke styling.

    Adds four optional visual properties on top of :class:`Element`:

    - ``fill_color``    — Typst color string for the fill. Renders as
      ``"black"`` when ``None``.
    - ``stroke_color``  — Typst color string for the stroke. Renders as
      ``"black"`` when ``None`` (irrelevant when ``stroke_width == 0``).
    - ``fill_opacity``  — Float in ``[0, 1]``. Renders as ``1`` when
      ``None``. Setting ``0`` is the conventional way to ask for "no
      fill" (the renderer emits ``fill: none`` for shapes).
    - ``stroke_width``  — Stroke thickness in cm. Renders as ``0`` when
      ``None``, i.e. **no stroke** (the renderer emits
      ``stroke: none``).

    Resolution and propagation
    --------------------------
    Each element carries its own concrete values. The backend resolves
    ``None`` to the BLACK/BLACK/1/0 defaults locally at render time.
    The four ``set_*`` methods are the only way to change a field:
    with the default ``propagate=True`` they walk the subtree and
    overwrite the chosen field on every :class:`Drawable` descendant
    (plain :class:`Element` descendants are skipped); with
    ``propagate=False`` they touch only the receiver.

    Parameters
    ----------
    fill_color, stroke_color : str or None, optional
        Backend-specific color strings (e.g. Typst's ``"red"``).
        Default ``None`` → resolved to ``"black"`` at render time.
    fill_opacity : float or None, optional
        Default ``None`` → ``1``. Set to ``0`` for no fill.
    stroke_width : float or None, optional
        Default ``None`` → ``0`` (no stroke).
    pos, anchor, placement, id
        See :class:`Element`.
    """

    def __init__(
        self,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
    ) -> None:
        super().__init__(pos=pos, anchor=anchor, placement=placement, id=id)
        self.fill_color: str | None = fill_color
        self.stroke_color: str | None = stroke_color
        self.fill_opacity: float | None = fill_opacity
        self.stroke_width: float | None = stroke_width

    def get_fill_color(self) -> str | None:
        """Return the stored ``fill_color`` (``None`` resolves to ``"black"`` at render time)."""
        return self.fill_color

    def get_stroke_color(self) -> str | None:
        """Return the stored ``stroke_color`` (``None`` resolves to ``"black"`` at render time)."""
        return self.stroke_color

    def get_fill_opacity(self) -> float | None:
        """Return the stored ``fill_opacity`` (``None`` resolves to ``1`` at render time)."""
        return self.fill_opacity

    def get_stroke_width(self) -> float | None:
        """Return the stored ``stroke_width`` (``None`` resolves to ``0`` at render time)."""
        return self.stroke_width

    def set_fill_color(self, color: str | None, propagate: bool = True) -> Drawable:
        """Set ``fill_color``; with ``propagate=True`` (default) also rewrites every Drawable descendant."""
        self._set_field("fill_color", color, propagate)
        return self

    def set_stroke_color(self, color: str | None, propagate: bool = True) -> Drawable:
        """Set ``stroke_color``; with ``propagate=True`` (default) also rewrites every Drawable descendant."""
        self._set_field("stroke_color", color, propagate)
        return self

    def set_fill_opacity(self, opacity: float | None, propagate: bool = True) -> Drawable:
        """Set ``fill_opacity``; with ``propagate=True`` (default) also rewrites every Drawable descendant."""
        self._set_field("fill_opacity", opacity, propagate)
        return self

    def set_stroke_width(self, width: float | None, propagate: bool = True) -> Drawable:
        """Set ``stroke_width``; with ``propagate=True`` (default) also rewrites every Drawable descendant."""
        self._set_field("stroke_width", width, propagate)
        return self
