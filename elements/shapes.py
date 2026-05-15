from __future__ import annotations

from ..core.element import Placement
from ..core.registry import IDKey
from ..core.drawable import Drawable
from ..core.vec import VecLike


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
    center, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
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
        center: VecLike | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
    ) -> None:
        super().__init__(
            center=center,
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
        """Return the rectangle's width in cm."""
        return self.width

    def get_height(self) -> float:
        """Return the rectangle's height in cm."""
        return self.height

    def set_width(self, width: float, propagate: bool = True) -> Rectangle:
        """Set ``width``; with ``propagate=True`` (default) also rewrites every descendant that has ``width``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("width", width, propagate)
        self._invalidate_tree()
        return self

    def set_height(self, height: float, propagate: bool = True) -> Rectangle:
        """Set ``height``; with ``propagate=True`` (default) also rewrites every descendant that has ``height``.

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
    center, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
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
        center: VecLike | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
    ) -> None:
        super().__init__(
            center=center,
            placement=placement,
            id=id,
            fill_color=fill_color,
            stroke_color=stroke_color,
            fill_opacity=fill_opacity,
            stroke_width=stroke_width,
        )
        self.radius: float = radius

    def get_radius(self) -> float:
        """Return the circle's radius in cm."""
        return self.radius

    def set_radius(self, radius: float, propagate: bool = True) -> Circle:
        """Set ``radius``; with ``propagate=True`` (default) also rewrites every descendant that has ``radius``.

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
    center, placement, id, fill_color, stroke_color, fill_opacity, stroke_width
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
        center: VecLike | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
        fill_color: str | None = None,
        stroke_color: str | None = None,
        fill_opacity: float | None = None,
        stroke_width: float | None = None,
    ) -> None:
        super().__init__(
            center=center,
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
        """Return the ellipse's bounding-box width in cm."""
        return self.width

    def get_height(self) -> float:
        """Return the ellipse's bounding-box height in cm."""
        return self.height

    def set_width(self, width: float, propagate: bool = True) -> "Ellipse":
        """Set ``width``; with ``propagate=True`` (default) also rewrites every descendant that has ``width``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("width", width, propagate)
        self._invalidate_tree()
        return self

    def set_height(self, height: float, propagate: bool = True) -> "Ellipse":
        """Set ``height``; with ``propagate=True`` (default) also rewrites every descendant that has ``height``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("height", height, propagate)
        self._invalidate_tree()
        return self
