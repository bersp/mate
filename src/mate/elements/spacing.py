from __future__ import annotations

from ..core.element import Anchor, Element, HAlign, Placement
from ..core.registry import IDKey
from ..core.vec import VecLike


class VSpace(Element):
    """Invisible vertical spacer: a fixed height in cm, zero width.

    Inserts vertical space between stacked elements in
    :func:`~mate.composition.arrange.arrange`. Reports its size
    intrinsically (no measurement) and draws nothing.

    Parameters
    ----------
    height : float
        Spacer height in cm. Positional.
    pos, anchor, align, placement, id
        Keyword-only. See :class:`~mate.core.element.Element`.

    Attributes
    ----------
    height : float
        See ``height`` parameter.
    """

    def __init__(
        self,
        height: float,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        super().__init__(pos=pos, anchor=anchor, align=align, placement=placement, id=id)
        self.height: float = height

    def get_width(self) -> float:
        return 0.0

    def get_height(self) -> float:
        return self.height * self.scale_factor

    def _repr_fields(self) -> str:
        return f"height={self.height:.4g}"

    def set_height(self, height: float, propagate: bool = True) -> VSpace:
        """Set ``height``; ``propagate`` (default) rewrites descendants with ``height``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("height", height, propagate)
        self._invalidate_tree()
        return self


class HSpace(Element):
    """Invisible horizontal spacer: a fixed width in cm, zero height.

    The horizontal counterpart of :class:`VSpace`. Reports its size
    intrinsically (no measurement) and draws nothing.

    Parameters
    ----------
    width : float
        Spacer width in cm. Positional.
    pos, anchor, align, placement, id
        Keyword-only. See :class:`~mate.core.element.Element`.

    Attributes
    ----------
    width : float
        See ``width`` parameter.
    """

    def __init__(
        self,
        width: float,
        *,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        super().__init__(pos=pos, anchor=anchor, align=align, placement=placement, id=id)
        self.width: float = width

    def get_width(self) -> float:
        return self.width * self.scale_factor

    def get_height(self) -> float:
        return 0.0

    def _repr_fields(self) -> str:
        return f"width={self.width:.4g}"

    def set_width(self, width: float, propagate: bool = True) -> HSpace:
        """Set ``width``; ``propagate`` (default) rewrites descendants with ``width``.

        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self._set_field("width", width, propagate)
        self._invalidate_tree()
        return self
