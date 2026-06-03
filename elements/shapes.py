from __future__ import annotations

from ..config import config
from ..core.element import Anchor, HAlign, Placement
from ..core.registry import IDKey
from ..core.drawable import Drawable
from ..core.vec import Vec, VecLike


class Rectangle(Drawable):
    """Filled axis-aligned rectangle with intrinsic dimensions.

    Geometry is set by the caller via ``width`` and ``height`` (in cm),
    so the element is its own measurement. Fill/stroke follow the
    :class:`~mate.core.drawable.Drawable` defaults: solid black fill, no
    stroke. Use ``fill_opacity=0`` to get an invisible rectangle (a
    layout placeholder).

    Parameters
    ----------
    width, height : float
        Width and height in cm. Positional.
    pos, anchor, align, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    width, height : float
        See ``width`` / ``height`` parameters.
    """

    def __init__(
        self,
        width: float,
        height: float,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
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
            align=align,
            placement=placement,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
        )
        self.width: float = width
        self.height: float = height

    def get_width(self) -> float:
        return self.width

    def get_height(self) -> float:
        return self.height

    def _repr_fields(self) -> str:
        return f"width={self.width:.4g}, height={self.height:.4g}"

    def set_width(self, width: float, propagate: bool = True) -> Rectangle:
        """Set ``width``; ``propagate`` (default) rewrites descendants with ``width``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("width", width, propagate)
        self._invalidate_tree()
        return self

    def set_height(self, height: float, propagate: bool = True) -> Rectangle:
        """Set ``height``; ``propagate`` (default) rewrites descendants with ``height``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("height", height, propagate)
        self._invalidate_tree()
        return self


class Circle(Drawable):
    """Filled circle with intrinsic radius.

    Bbox is ``(2 radius, 2 radius)``. Fill/stroke follow the
    :class:`~mate.core.drawable.Drawable` defaults.

    Parameters
    ----------
    radius : float
        Radius in cm. Positional.
    pos, anchor, align, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    radius : float
        See ``radius`` parameter.
    """

    def __init__(
        self,
        radius: float,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
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
            align=align,
            placement=placement,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
        )
        self.radius: float = radius

    def get_radius(self) -> float:
        return self.radius

    def _repr_fields(self) -> str:
        return f"radius={self.radius:.4g}"

    def get_width(self) -> float:
        """Return the circle's bbox width (``2 * radius``)."""
        return 2 * self.radius

    def get_height(self) -> float:
        """Return the circle's bbox height (``2 * radius``)."""
        return 2 * self.radius

    def set_radius(self, radius: float, propagate: bool = True) -> Circle:
        """Set ``radius``; ``propagate`` (default) rewrites descendants with ``radius``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("radius", radius, propagate)
        self._invalidate_tree()
        return self


class Ellipse(Drawable):
    """Filled axis-aligned ellipse with intrinsic dimensions.

    ``width`` and ``height`` (in cm) are the bounding-box dimensions:
    the semi-axes are ``width/2`` and ``height/2``. Fill/stroke follow
    the :class:`~mate.core.drawable.Drawable` defaults.

    Parameters
    ----------
    width, height : float
        Bounding box width and height in cm. Positional.
    pos, anchor, align, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    width, height : float
        See ``width`` / ``height`` parameters.
    """

    def __init__(
        self,
        width: float,
        height: float,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
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
            align=align,
            placement=placement,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
        )
        self.width: float = width
        self.height: float = height

    def get_width(self) -> float:
        return self.width

    def get_height(self) -> float:
        return self.height

    def _repr_fields(self) -> str:
        return f"width={self.width:.4g}, height={self.height:.4g}"

    def set_width(self, width: float, propagate: bool = True) -> "Ellipse":
        """Set ``width``; ``propagate`` (default) rewrites descendants with ``width``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("width", width, propagate)
        self._invalidate_tree()
        return self

    def set_height(self, height: float, propagate: bool = True) -> "Ellipse":
        """Set ``height``; ``propagate`` (default) rewrites descendants with ``height``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("height", height, propagate)
        self._invalidate_tree()
        return self


class Line(Drawable):
    """Straight line segment from ``start`` to ``end``.

    ``start`` and ``end`` are points in cm in the element's local frame.
    The bbox is the axis-aligned box bounding them, so a horizontal line
    has zero height and a vertical line zero width. The points fix the
    shape and size; ``anchor``/``pos`` place that box on the slide like
    any other element. Only the stroke is drawn (``stroke_color`` /
    ``stroke_width``); ``fill_*`` is inert.

    Parameters
    ----------
    start, end : VecLike
        Endpoints in cm, in the local frame. Positional.
    stroke_width : float or None, optional
        Stroke thickness in cm. ``None`` (default) reads
        ``line.stroke_width`` from the config.
    pos, anchor, align, placement, id, stroke_color, fill_color, fill_opacity
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    start, end : Vec
        The endpoints in the local frame.
    """

    def __init__(
        self,
        start: VecLike,
        end: VecLike,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
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
            align=align,
            placement=placement,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=(
                config.get("line.stroke_width")
                if stroke_width is None
                else stroke_width
            ),
        )
        self.start: Vec = Vec(start)
        self.end: Vec = Vec(end)

    def get_width(self) -> float:
        return abs(self.end.x - self.start.x)

    def get_height(self) -> float:
        return abs(self.end.y - self.start.y)

    def _repr_fields(self) -> str:
        return (
            f"start=({self.start.x:.4g}, {self.start.y:.4g}), "
            f"end=({self.end.x:.4g}, {self.end.y:.4g})"
        )

    def set_start(self, start: VecLike, propagate: bool = False) -> Line:
        """Set ``start``; ``propagate`` rewrites descendants with ``start``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("start", Vec(start), propagate)
        self._invalidate_tree()
        return self

    def set_end(self, end: VecLike, propagate: bool = False) -> Line:
        """Set ``end``; ``propagate`` rewrites descendants with ``end``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("end", Vec(end), propagate)
        self._invalidate_tree()
        return self
