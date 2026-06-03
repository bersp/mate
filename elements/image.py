from __future__ import annotations

from ..core.element import Anchor, Element, HAlign, Placement
from ..core.registry import IDKey
from ..core.vec import VecLike


class Image(Element):
    """Image loaded from a file, sized by the backend.

    With neither ``width`` nor ``height`` the image renders at the file's
    natural size; with one set the other follows the file's aspect ratio;
    with both set the image is forced into that box.

    Parameters
    ----------
    path : str
        Filesystem path to the image file. Positional.
    width : float or None, optional
        Rendered width in cm, or ``None`` (default) to leave it free.
    height : float or None, optional
        Rendered height in cm, or ``None`` (default) to leave it free.
    pos, anchor, align, placement, id
        Keyword-only. See :class:`~mate.core.element.Element`.

    Attributes
    ----------
    path : str
        See ``path`` parameter.
    width : float or None
        Width constraint in cm, or ``None``.
    height : float or None
        Height constraint in cm, or ``None``.
    """

    def __init__(
        self,
        path: str,
        *,
        width: float | None = None,
        height: float | None = None,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        super().__init__(pos=pos, anchor=anchor, align=align, placement=placement, id=id)
        self.path: str = path
        self.width: float | None = width
        self.height: float | None = height

    def _repr_fields(self) -> str:
        return f"path={self.path!r}"
