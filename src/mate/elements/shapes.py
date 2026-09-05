from __future__ import annotations

import math

from ..config import config
from ..core.element import Anchor, Element, HAlign, Placement
from ..core.registry import IDKey
from ..core.drawable import Drawable
from ..core.vec import Vec, VecLike
from .group import Group

CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")


def _check_corner_radius(corner_radius: float | dict) -> float | dict:
    """Return ``corner_radius`` after checking a dict's keys name corners."""
    if not isinstance(corner_radius, dict):
        return corner_radius
    unknown = sorted(set(corner_radius) - set(CORNERS))
    if unknown:
        names = ", ".join(repr(name) for name in unknown)
        raise ValueError(
            f"unknown corner_radius corner(s) {names}; "
            f"valid: {', '.join(CORNERS)}"
        )
    return corner_radius


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
    corner_radius : float or dict, optional
        Corner rounding radius in cm. A float rounds the four corners by the
        same amount; a dict rounds each named corner on its own, keyed by
        ``"top-left"``, ``"top-right"``, ``"bottom-left"``, ``"bottom-right"``,
        with the corners left out staying sharp. ``0`` (default) keeps every
        corner sharp. The rounding is visual-only: the bbox stays
        ``(width, height)``.
    pos, anchor, align, placement, z_order, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    width, height : float
        See ``width`` / ``height`` parameters.
    corner_radius : float or dict
        See ``corner_radius`` parameter.
    """

    def __init__(
        self,
        width: float,
        height: float,
        *,
        corner_radius: float | dict[str, float] = 0.0,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        z_order: float | None = None,
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
            z_order=z_order,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.width: float = width
        self.height: float = height
        self.corner_radius: float | dict[str, float] = _check_corner_radius(
            corner_radius
        )

    def get_width(self) -> float:
        return self._transformed_extents(self.width, self.height)[0]

    def get_height(self) -> float:
        return self._transformed_extents(self.width, self.height)[1]

    def get_corner_radius(self) -> float | dict[str, float]:
        return self.corner_radius

    def set_corner_radius(self, corner_radius: float | dict[str, float]) -> Rectangle:
        """Set the corner rounding radius in cm, as a float or a per-corner dict.

        Visual-only: the bbox stays ``(width, height)``, so the bbox cache is
        untouched.
        """
        self.corner_radius = _check_corner_radius(corner_radius)
        return self

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
    pos, anchor, align, placement, z_order, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
        z_order: float | None = None,
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
            z_order=z_order,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.radius: float = radius

    def get_radius(self) -> float:
        return self.radius

    def _repr_fields(self) -> str:
        return f"radius={self.radius:.4g}"

    def get_width(self) -> float:
        """Return the circle's bbox width: ``2 * radius`` under its transforms."""
        return self._transformed_extents(2 * self.radius, 2 * self.radius)[0]

    def get_height(self) -> float:
        """Return the circle's bbox height: ``2 * radius`` under its transforms."""
        return self._transformed_extents(2 * self.radius, 2 * self.radius)[1]

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
    pos, anchor, align, placement, z_order, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
        z_order: float | None = None,
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
            z_order=z_order,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.width: float = width
        self.height: float = height

    def get_width(self) -> float:
        return self._transformed_extents(self.width, self.height)[0]

    def get_height(self) -> float:
        return self._transformed_extents(self.width, self.height)[1]

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
    """Straight segment drawn between two endpoints ``start`` and ``end``.

    The segment runs from one endpoint to the other. ``_pos`` is the
    midpoint of the two, so the line moves rigidly under
    :meth:`~mate.core.element.Element.move_to`,
    :meth:`~mate.core.element.Element.shift`, and region arrangement.
    The bbox is the axis-aligned box bounding the endpoints, so a
    horizontal line has zero height and a vertical one zero width. Only
    the stroke is drawn (``stroke_color`` / ``stroke_width``); a line
    carries no fill.

    Parameters
    ----------
    start, end : VecLike
        Endpoints in cm. Positional.
    stroke_width : float or None, optional
        Stroke thickness in cm. ``None`` (default) reads
        ``line.stroke_width`` from the config.
    placement, z_order, id, stroke_color, stroke_dash, stroke_cap, stroke_join, stroke_opacity
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    start, end : Vec
        The endpoints relative to the segment's midpoint (``_pos``);
        :meth:`get_start` / :meth:`get_end` return the endpoints themselves.
    """

    def __init__(
        self,
        start: VecLike,
        end: VecLike,
        *,
        placement: Placement = "fixed",
        z_order: float | None = None,
        id: IDKey | list[IDKey] | None = None,
        stroke_color: str | None = None,
        stroke_width: float | None = None,
        stroke_dash: str | list[float] | None = None,
        stroke_cap: str | None = None,
        stroke_join: str | None = None,
        stroke_opacity: float | None = None,
    ) -> None:
        start = Vec(start)
        end = Vec(end)
        center = Vec((start + end) / 2)
        super().__init__(
            pos=center,
            anchor="center",
            placement=placement,
            z_order=z_order,
            id=id,
            stroke_color=stroke_color,
            stroke_width=(
                config.get("line.stroke_width")
                if stroke_width is None
                else stroke_width
            ),
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.start: Vec = Vec(start - center)
        self.end: Vec = Vec(end - center)

    def get_start(self) -> Vec:
        """Return the start endpoint."""
        return Vec(self._pos + self.start)

    def get_end(self) -> Vec:
        """Return the end endpoint."""
        return Vec(self._pos + self.end)

    def get_width(self) -> float:
        return self._transformed_extents(
            abs(self.end.x - self.start.x), abs(self.end.y - self.start.y)
        )[0]

    def get_height(self) -> float:
        return self._transformed_extents(
            abs(self.end.x - self.start.x), abs(self.end.y - self.start.y)
        )[1]

    def _repr_fields(self) -> str:
        s, e = self.get_start(), self.get_end()
        return f"start=({s.x:.4g}, {s.y:.4g}), end=({e.x:.4g}, {e.y:.4g})"

    def set_start(self, start: VecLike) -> Line:
        """Set the start endpoint, keeping ``end`` fixed.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._reseat(Vec(start), self.get_end())
        return self

    def set_end(self, end: VecLike) -> Line:
        """Set the end endpoint, keeping ``start`` fixed.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._reseat(self.get_start(), Vec(end))
        return self

    def _reseat(self, start: Vec, end: Vec) -> None:
        """Re-anchor on the new endpoints: recenter ``_pos`` and re-store offsets."""
        center = Vec((start + end) / 2)
        self._pos = center
        self.start = Vec(start - center)
        self.end = Vec(end - center)
        self._invalidate_tree()


def _points_bounding_center(points: list[Vec]) -> Vec:
    """Return the centre of the axis-aligned box bounding ``points``."""
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return Vec(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))


def _points_spans(points: list[Vec]) -> tuple[float, float]:
    """Return the width and height of the axis-aligned box bounding ``points``."""
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    return max(xs) - min(xs), max(ys) - min(ys)


class Polygon(Drawable):
    """Filled polygon through a list of vertices.

    ``points`` are the vertices (cm) in the element's local frame; the
    polygon is closed automatically, so the edge from the last vertex
    back to the first is drawn. ``_pos`` is the centre of the box
    bounding the vertices, so the polygon moves rigidly under
    :meth:`~mate.core.element.Element.move_to`,
    :meth:`~mate.core.element.Element.shift`, and region arrangement.
    The bbox is the axis-aligned box bounding the vertices. Fill/stroke
    follow the :class:`~mate.core.drawable.Drawable` defaults: solid
    black fill, no stroke.

    Parameters
    ----------
    points : list of VecLike
        Vertices in cm. Positional. At least three are required.
    placement, z_order, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    points : list of Vec
        The vertices relative to the polygon's centre (``_pos``);
        :meth:`get_points` returns them in slide coordinates.
    """

    def __init__(
        self,
        points: list[VecLike],
        *,
        placement: Placement = "fixed",
        z_order: float | None = None,
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
            pos=None,
            anchor="center",
            placement=placement,
            z_order=z_order,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.points: list[Vec] = []
        self.set_points(points)

    def get_points(self) -> list[Vec]:
        """Return the vertices in slide coordinates."""
        return [Vec(self._pos + p) for p in self.points]

    def set_points(self, points: list[VecLike]) -> Polygon:
        """Replace the vertices, re-centering ``_pos`` on their bounding box.

        ``points`` are vertices in slide coordinates; at least three are
        required. Geometric mutator: invalidates the bbox cache of this
        element's tree.
        """
        verts = [Vec(p) for p in points]
        if len(verts) < 3:
            raise ValueError(f"Polygon needs at least 3 vertices, got {len(verts)}.")
        center = _points_bounding_center(verts)
        self._pos = center
        self.points = [Vec(p - center) for p in verts]
        self._invalidate_tree()
        return self

    def get_width(self) -> float:
        return self._transformed_extents(*_points_spans(self.points))[0]

    def get_height(self) -> float:
        return self._transformed_extents(*_points_spans(self.points))[1]

    def _repr_fields(self) -> str:
        return f"points={len(self.points)}"


class CurveSegment:
    """Base class for the path segments of a :class:`Curve`.

    A segment is pure geometry: it carries points in the curve's local
    frame and knows how to enumerate and translate them. Translating a
    Typst form is the backend's job — a segment never references Typst
    syntax.
    """

    def _points(self) -> tuple[Vec, ...]:
        """Return every point this segment defines (for bbox and recentre)."""
        raise NotImplementedError

    def _translated(self, delta: Vec) -> CurveSegment:
        """Return a copy with every point shifted by ``delta``."""
        raise NotImplementedError


class MoveTo(CurveSegment):
    """Start a new subpath at ``point`` without drawing."""

    def __init__(self, point: VecLike) -> None:
        self.point: Vec = Vec(point)

    def _points(self) -> tuple[Vec, ...]:
        return (self.point,)

    def _translated(self, delta: Vec) -> MoveTo:
        return MoveTo(self.point + delta)

    def __repr__(self) -> str:
        return f"MoveTo(({self.point.x:.4g}, {self.point.y:.4g}))"


class LineTo(CurveSegment):
    """Draw a straight segment to ``point``."""

    def __init__(self, point: VecLike) -> None:
        self.point: Vec = Vec(point)

    def _points(self) -> tuple[Vec, ...]:
        return (self.point,)

    def _translated(self, delta: Vec) -> LineTo:
        return LineTo(self.point + delta)

    def __repr__(self) -> str:
        return f"LineTo(({self.point.x:.4g}, {self.point.y:.4g}))"


class CubicTo(CurveSegment):
    """Draw a cubic Bézier to ``point`` via two control points.

    ``control_start`` governs the tangent leaving the previous point,
    ``control_end`` the tangent arriving at ``point``.
    """

    def __init__(
        self, control_start: VecLike, control_end: VecLike, point: VecLike
    ) -> None:
        self.control_start: Vec = Vec(control_start)
        self.control_end: Vec = Vec(control_end)
        self.point: Vec = Vec(point)

    def _points(self) -> tuple[Vec, ...]:
        return (self.control_start, self.control_end, self.point)

    def _translated(self, delta: Vec) -> CubicTo:
        return CubicTo(
            self.control_start + delta,
            self.control_end + delta,
            self.point + delta,
        )

    def __repr__(self) -> str:
        return (
            f"CubicTo(({self.control_start.x:.4g}, {self.control_start.y:.4g}), "
            f"({self.control_end.x:.4g}, {self.control_end.y:.4g}), "
            f"({self.point.x:.4g}, {self.point.y:.4g}))"
        )


class QuadTo(CurveSegment):
    """Draw a quadratic Bézier to ``point`` via a single ``control`` point."""

    def __init__(self, control: VecLike, point: VecLike) -> None:
        self.control: Vec = Vec(control)
        self.point: Vec = Vec(point)

    def _points(self) -> tuple[Vec, ...]:
        return (self.control, self.point)

    def _translated(self, delta: Vec) -> QuadTo:
        return QuadTo(self.control + delta, self.point + delta)

    def __repr__(self) -> str:
        return (
            f"QuadTo(({self.control.x:.4g}, {self.control.y:.4g}), "
            f"({self.point.x:.4g}, {self.point.y:.4g}))"
        )


class Close(CurveSegment):
    """Close the current subpath with a straight segment to its start."""

    def _points(self) -> tuple[Vec, ...]:
        return ()

    def _translated(self, delta: Vec) -> Close:
        return Close()

    def __repr__(self) -> str:
        return "Close()"


class Curve(Drawable):
    """Path of Bézier and line segments.

    ``segments`` is a sequence of :class:`CurveSegment` (``MoveTo``,
    ``LineTo``, ``CubicTo``, ``QuadTo``, ``Close``) whose points are in
    the curve's local frame (cm). The first segment must be a
    :class:`MoveTo`. ``_pos`` is the centre of the box bounding every
    point referenced by the segments — endpoints and control points
    alike — so the curve moves rigidly under
    :meth:`~mate.core.element.Element.move_to`,
    :meth:`~mate.core.element.Element.shift`, and region arrangement.
    The bbox is that same control-point box, a conservative bound that
    always contains the drawn curve. Fill/stroke follow the
    :class:`~mate.core.drawable.Drawable` defaults: solid black fill, no
    stroke. ``fill_opacity=0`` makes a stroke-only path.

    Parameters
    ----------
    segments : list of CurveSegment
        Path segments in draw order. Positional. The first must be a
        :class:`MoveTo`.
    placement, z_order, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    segments : list of CurveSegment
        The segments with points relative to the curve's centre (``_pos``).
    """

    def __init__(
        self,
        segments: list[CurveSegment],
        *,
        placement: Placement = "fixed",
        z_order: float | None = None,
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
            pos=None,
            anchor="center",
            placement=placement,
            z_order=z_order,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.segments: list[CurveSegment] = []
        self.set_segments(segments)

    def set_segments(self, segments: list[CurveSegment]) -> Curve:
        """Replace the path segments, re-centering ``_pos`` on their bounding box.

        ``segments`` are in slide coordinates and the first must be a
        :class:`MoveTo`. Geometric mutator: invalidates the bbox cache of
        this element's tree.
        """
        segments = list(segments)
        if not segments:
            raise ValueError("Curve needs at least one segment.")
        bad = next((s for s in segments if not isinstance(s, CurveSegment)), None)
        if bad is not None:
            raise TypeError(
                f"Curve segments must be MoveTo/LineTo/CubicTo/QuadTo/Close, "
                f"got {bad!r}."
            )
        if not isinstance(segments[0], MoveTo):
            raise ValueError(
                f"Curve must start with a MoveTo segment, got {segments[0]!r}."
            )
        points = [p for s in segments for p in s._points()]
        center = _points_bounding_center(points)
        self._pos = center
        self.segments = [s._translated(Vec(-center)) for s in segments]
        self._invalidate_tree()
        return self

    def get_segments(self) -> list[CurveSegment]:
        """Return the segments in slide coordinates."""
        return [s._translated(self._pos) for s in self.segments]

    def _all_points(self) -> list[Vec]:
        """Return every point referenced by the segments, in local coordinates."""
        return [p for s in self.segments for p in s._points()]

    def get_width(self) -> float:
        return self._transformed_extents(*_points_spans(self._all_points()))[0]

    def get_height(self) -> float:
        return self._transformed_extents(*_points_spans(self._all_points()))[1]

    def _repr_fields(self) -> str:
        return f"segments={len(self.segments)}"


def _unit(delta: Vec) -> Vec:
    """Return ``delta`` scaled to unit length."""
    return Vec(delta / math.hypot(delta.x, delta.y))


def _perpendicular(direction: Vec) -> Vec:
    """Return the vector ``direction`` rotated a quarter turn counterclockwise."""
    return Vec(-direction.y, direction.x)


def _aimed(points: list[Vec], point: Vec, direction: Vec) -> list[Vec]:
    """Map tip points from the canonical frame onto ``point``.

    The canonical frame has the tip's point at the origin aiming along ``+x``.
    ``direction`` is its x axis and the perpendicular its y axis.
    """
    across = _perpendicular(direction)
    return [Vec(point + direction * p.x + across * p.y) for p in points]


def _open_path(points: list[Vec]) -> list[CurveSegment]:
    """Return the segments drawing an open polyline through ``points``."""
    return [MoveTo(points[0]), *(LineTo(p) for p in points[1:])]


class ArrowTip:
    """Base class for the end markers of an :class:`Arrow`.

    A tip is a shape like any other. Each concrete tip pairs this class with
    the shape it draws as, and is built in a canonical frame: its point at the
    origin, aiming along ``+x``. :meth:`_place_at` plants it on an endpoint.

    A tip pins the style fields its look depends on (see
    :attr:`~mate.core.element.Element._pinned_fields`). Restyling an arrow then
    reaches the pieces that follow the arrow's stroke and leaves the rest.
    """

    def _place_at(self, point: Vec, direction: Vec) -> None:
        """Move the tip onto ``point``, aimed along the unit ``direction``."""
        raise NotImplementedError

    def shaft_inset(self) -> float:
        """Return how far the shaft stops short of the tip's point."""
        raise NotImplementedError


class TriangleTip(ArrowTip, Polygon):
    """Solid triangle with its apex on the endpoint.

    The base sits ``length`` back along the shaft and spans ``width`` across
    it. The shaft pulls back the full ``length`` and ends flush with the base.
    The triangle carries no stroke; its stroke color is what fills it.

    Parameters
    ----------
    length : float or None, optional
        Extent along the shaft in cm. ``None`` (default) reads
        ``arrow.triangle.length`` from the config.
    width : float or None, optional
        Extent across the shaft in cm. ``None`` (default) reads
        ``arrow.triangle.width`` from the config.
    """

    _pinned_fields = frozenset({"stroke_width", "width"})

    def __init__(
        self, length: float | None = None, width: float | None = None
    ) -> None:
        self.length: float = (
            config.get("arrow.triangle.length") if length is None else length
        )
        self.width: float = (
            config.get("arrow.triangle.width") if width is None else width
        )
        super().__init__(self._canonical_points())

    @property
    def stroke_color(self) -> str | None:
        """The fill. A filled tip draws no stroke; the two are one color."""
        return self.fill_color

    @stroke_color.setter
    def stroke_color(self, color: str | None) -> None:
        self.fill_color = color

    @property
    def stroke_opacity(self) -> float | None:
        """The fill opacity, on the same footing as :attr:`stroke_color`."""
        return self.fill_opacity

    @stroke_opacity.setter
    def stroke_opacity(self, opacity: float | None) -> None:
        self.fill_opacity = opacity

    def _canonical_points(self) -> list[Vec]:
        return [
            Vec(0.0, 0.0),
            Vec(-self.length, self.width / 2),
            Vec(-self.length, -self.width / 2),
        ]

    def _place_at(self, point: Vec, direction: Vec) -> None:
        self.set_points(_aimed(self._canonical_points(), point, direction))

    def shaft_inset(self) -> float:
        return self.length

    def _repr_fields(self) -> str:
        return f"length={self.length:.4g}, width={self.width:.4g}"


class BarTip(ArrowTip, Curve):
    """Open bar across the shaft, centred on the endpoint.

    The bar spans ``width`` across the shaft, and the shaft runs all the way to
    the endpoint, meeting the bar at its middle. The bar is drawn in the
    arrow's stroke and follows its ``stroke_color`` and ``stroke_width``.

    Parameters
    ----------
    width : float or None, optional
        Extent across the shaft in cm. ``None`` (default) reads
        ``arrow.bar.width`` from the config.
    """

    _pinned_fields = frozenset({"fill_opacity", "stroke_dash", "width"})

    def __init__(self, width: float | None = None) -> None:
        self.width: float = config.get("arrow.bar.width") if width is None else width
        super().__init__(_open_path(self._canonical_points()), fill_opacity=0)

    def _canonical_points(self) -> list[Vec]:
        return [Vec(0.0, self.width / 2), Vec(0.0, -self.width / 2)]

    def _place_at(self, point: Vec, direction: Vec) -> None:
        placed = _aimed(self._canonical_points(), point, direction)
        self.set_segments(_open_path(placed))

    def shaft_inset(self) -> float:
        return 0.0

    def _repr_fields(self) -> str:
        return f"width={self.width:.4g}"


class HookTip(ArrowTip, Curve):
    """Open V: two strokes meeting on the endpoint.

    Each wing runs ``length`` back from the endpoint, ``opening_angle`` degrees
    off the shaft. The shaft runs all the way to the endpoint, where the wings
    meet it. The V is drawn in the arrow's stroke and follows its
    ``stroke_color`` and ``stroke_width``. It keeps its own dash, and a dashed
    arrow lands on a solid head.

    Parameters
    ----------
    length : float or None, optional
        Wing length in cm. ``None`` (default) reads ``arrow.hook.length``
        from the config.
    opening_angle : float or None, optional
        Angle between a wing and the shaft, in degrees. ``None`` (default)
        reads ``arrow.hook.opening_angle`` from the config.
    """

    _pinned_fields = frozenset({"fill_opacity", "stroke_dash"})

    def __init__(
        self, length: float | None = None, opening_angle: float | None = None
    ) -> None:
        self.length: float = (
            config.get("arrow.hook.length") if length is None else length
        )
        self.opening_angle: float = (
            config.get("arrow.hook.opening_angle")
            if opening_angle is None
            else opening_angle
        )
        super().__init__(_open_path(self._canonical_points()), fill_opacity=0)

    def _canonical_points(self) -> list[Vec]:
        theta = math.radians(self.opening_angle)
        back = -self.length * math.cos(theta)
        across = self.length * math.sin(theta)
        return [Vec(back, across), Vec(0.0, 0.0), Vec(back, -across)]

    def _place_at(self, point: Vec, direction: Vec) -> None:
        placed = _aimed(self._canonical_points(), point, direction)
        self.set_segments(_open_path(placed))

    def shaft_inset(self) -> float:
        return 0.0

    def _repr_fields(self) -> str:
        return f"length={self.length:.4g}, opening_angle={self.opening_angle:.4g}"


ARROW_TIPS: dict[str, type[ArrowTip]] = {
    "triangle": TriangleTip,
    "hook": HookTip,
    "bar": BarTip,
}
"""The :class:`ArrowTip` subclass each ``arrow.tip`` config name builds."""


def _named_tip(name: str) -> ArrowTip:
    """Build the tip ``name`` stands for, at its config dimensions."""
    if name not in ARROW_TIPS:
        raise ValueError(
            f"unknown arrow tip {name!r}; valid: {', '.join(ARROW_TIPS)}"
        )
    return ARROW_TIPS[name]()


class Arrow(Group):
    """Segment carrying an end marker on one or both endpoints.

    An arrow is the group of the shapes it is drawn from: a :class:`Line`
    shaft and one :class:`ArrowTip` per marked endpoint. The shaft stops short
    of a marker that claims the room. The bbox is the union of the pieces and
    covers the markers. ``_pos`` is the midpoint of the endpoints, and the
    whole thing moves rigidly under
    :meth:`~mate.core.element.Element.move_to`,
    :meth:`~mate.core.element.Element.shift`, and region arrangement.

    The stroke fields reach the pieces that follow them: ``set_stroke_color``
    recolors the shaft and both markers, and ``set_stroke_width`` thickens the
    shaft and the open markers, leaving a filled one unoutlined.

    Parameters
    ----------
    start, end : VecLike
        Two distinct endpoints in cm. Positional.
    tip : ArrowTip or None, optional
        Marker at ``end``. ``None`` (default) builds the one ``arrow.tip``
        names in the config; an arrow always carries a head, a plain segment
        is a :class:`Line`.
    tail : ArrowTip or None, optional
        Marker at ``start``. ``None`` (default) leaves that end bare.
    stroke_width : float or None, optional
        Stroke thickness in cm. ``None`` (default) reads
        ``line.stroke_width`` from the config.
    placement, z_order, id, stroke_color, stroke_dash, stroke_cap, stroke_join, stroke_opacity
        Keyword-only. See :class:`~mate.core.drawable.Drawable`.

    Attributes
    ----------
    start, end : Vec
        The endpoints relative to ``_pos``; :meth:`get_start` / :meth:`get_end`
        return the endpoints themselves.
    shaft : Line
        The segment drawn between the markers.
    tip, tail : ArrowTip or None
        The markers drawn at ``end`` and at ``start``.
    """

    def __init__(
        self,
        start: VecLike,
        end: VecLike,
        *,
        tip: ArrowTip | None = None,
        tail: ArrowTip | None = None,
        placement: Placement = "fixed",
        z_order: float | None = None,
        id: IDKey | list[IDKey] | None = None,
        stroke_color: str | None = None,
        stroke_width: float | None = None,
        stroke_dash: str | list[float] | None = None,
        stroke_cap: str | None = None,
        stroke_join: str | None = None,
        stroke_opacity: float | None = None,
    ) -> None:
        start, end = Vec(start), Vec(end)
        self.shaft: Line = Line(start, end)
        self.tip: ArrowTip = _named_tip(config.get("arrow.tip")) if tip is None else tip
        self.tail: ArrowTip | None = tail
        pieces = [self.shaft, self.tip]
        if self.tail is not None:
            pieces.append(self.tail)
        super().__init__(
            pieces,
            pos=(start + end) / 2,
            placement=placement,
            z_order=z_order,
            id=id,
            stroke_color=stroke_color,
            stroke_width=(
                config.get("line.stroke_width")
                if stroke_width is None
                else stroke_width
            ),
            stroke_dash=stroke_dash,
            stroke_cap=stroke_cap,
            stroke_join=stroke_join,
            stroke_opacity=stroke_opacity,
        )
        self.start: Vec = Vec(start - self._pos)
        self.end: Vec = Vec(end - self._pos)
        self._reseat(start, end)
        self._restyle_pieces()

    def get_start(self) -> Vec:
        """Return the start endpoint."""
        return Vec(self._pos + self.start)

    def get_end(self) -> Vec:
        """Return the end endpoint."""
        return Vec(self._pos + self.end)

    def set_start(self, start: VecLike) -> Arrow:
        """Set the start endpoint, keeping ``end`` fixed.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._reseat(Vec(start), self.get_end())
        return self

    def set_end(self, end: VecLike) -> Arrow:
        """Set the end endpoint, keeping ``start`` fixed.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._reseat(self.get_start(), Vec(end))
        return self

    def set_tip(self, tip: ArrowTip) -> Arrow:
        """Set the marker drawn at the end endpoint.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self.remove(self.tip)
        self.tip = tip
        self.add(tip)
        self._reseat(self.get_start(), self.get_end())
        self._restyle_pieces()
        return self

    def set_tail(self, tail: ArrowTip | None) -> Arrow:
        """Set the marker drawn at the start endpoint; ``None`` leaves it bare.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        if self.tail is not None:
            self.remove(self.tail)
        self.tail = tail
        if tail is not None:
            self.add(tail)
        self._reseat(self.get_start(), self.get_end())
        self._restyle_pieces()
        return self

    def _repr_fields(self) -> str:
        s, e = self.get_start(), self.get_end()
        fields = (
            f"start=({s.x:.4g}, {s.y:.4g}), end=({e.x:.4g}, {e.y:.4g}), "
            f"tip={self.tip!r}"
        )
        if self.tail is not None:
            fields += f", tail={self.tail!r}"
        return fields

    def _copy(self, mapping: dict[int, Element]) -> Arrow:
        # `shaft`, `tip` and `tail` are children: the superclass walk has
        # already cloned them, and only these references need repointing.
        new = super()._copy(mapping)
        new.shaft = mapping[id(self.shaft)]
        new.tip = mapping[id(self.tip)]
        if self.tail is not None:
            new.tail = mapping[id(self.tail)]
        return new

    def _reseat(self, start: Vec, end: Vec) -> None:
        """Re-anchor on the new endpoints: place every piece, recenter ``_pos``."""
        if start.x == end.x and start.y == end.y:
            raise ValueError(
                "Arrow needs distinct endpoints, got both at "
                f"({start.x:.4g}, {start.y:.4g})."
            )
        direction = _unit(Vec(end - start))
        self.tip._place_at(end, direction)
        if self.tail is not None:
            self.tail._place_at(start, Vec(-direction))
        self.shaft.set_start(start + direction * self._tail_inset())
        self.shaft.set_end(end - direction * self.tip.shaft_inset())
        if not self._shaft_runs_forward(direction):
            self.shaft.set_start(self.shaft.get_end())
        center = Vec((start + end) / 2)
        self._pos = center
        self.start = Vec(start - center)
        self.end = Vec(end - center)
        self._invalidate_tree()

    def _tail_inset(self) -> float:
        """Return how far the shaft starts past the start endpoint."""
        return 0.0 if self.tail is None else self.tail.shaft_inset()

    def _shaft_runs_forward(self, direction: Vec) -> bool:
        """Whether the markers left the shaft any room to draw."""
        span = self.shaft.get_end() - self.shaft.get_start()
        return span.x * direction.x + span.y * direction.y > 0

    def _restyle_pieces(self) -> None:
        """Push the arrow's stroke fields onto the pieces it is drawn from."""
        self.set_stroke_color(self.stroke_color)
        self.set_stroke_width(self.stroke_width)
        self.set_stroke_dash(self.stroke_dash)
        self.set_stroke_cap(self.stroke_cap)
        self.set_stroke_join(self.stroke_join)
        self.set_stroke_opacity(self.stroke_opacity)
