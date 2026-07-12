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
    pos, anchor, align, placement, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
    pos, anchor, align, placement, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
    pos, anchor, align, placement, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
    placement, id, stroke_color, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
        return abs(self.end.x - self.start.x)

    def get_height(self) -> float:
        return abs(self.end.y - self.start.y)

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
    placement, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
        xs = [p.x for p in self.points]
        return max(xs) - min(xs)

    def get_height(self) -> float:
        ys = [p.y for p in self.points]
        return max(ys) - min(ys)

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
    placement, id, fill_color, stroke_color, fill_opacity, stroke_width, stroke_dash, stroke_cap, stroke_join, stroke_opacity
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
        xs = [p.x for p in self._all_points()]
        return max(xs) - min(xs)

    def get_height(self) -> float:
        ys = [p.y for p in self._all_points()]
        return max(ys) - min(ys)

    def _repr_fields(self) -> str:
        return f"segments={len(self.segments)}"
