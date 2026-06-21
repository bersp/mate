from __future__ import annotations

from ..core.element import Anchor, Element, HAlign, Placement
from ..core.registry import IDKey
from ..core.vec import VecLike


class Image(Element):
    """Image loaded from a file, sized by the backend.

    With neither ``width`` nor ``height`` the image renders at the file's
    natural size; with one set the other follows the file's aspect ratio;
    with both set the image is forced into that box.

    ``clip`` crops the same amount off all four edges, shrinking the
    element's measured size to match.

    Parameters
    ----------
    path : str
        Filesystem path to the image file. Positional.
    width : float or None, optional
        Rendered width in cm, or ``None`` (default) to leave it free.
    height : float or None, optional
        Rendered height in cm, or ``None`` (default) to leave it free.
    clip : float or str or None, optional
        Crop removed from every edge, or ``None`` (default) for no
        cropping. A number is read as centimetres; a ``"N%"`` string is
        read as that percentage of the rendered width and applied
        equally to all four edges.
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
    clip : float or str or None
        Crop in cm (number) or as a percentage of the rendered width
        (``"N%"`` string), or ``None``.
    """

    def __init__(
        self,
        path: str,
        *,
        width: float | None = None,
        height: float | None = None,
        clip: float | str | None = None,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        super().__init__(pos=pos, anchor=anchor, align=align, placement=placement, id=id)
        if not (
            clip is None
            or (isinstance(clip, (int, float)) and clip >= 0)
            or (
                isinstance(clip, str)
                and clip.endswith("%")
                and clip[:-1].replace(".", "", 1).isdigit()
            )
        ):
            raise ValueError(
                f'clip must be a non-negative number (cm) or an "N%" string, got {clip!r}'
            )
        self.path: str = path
        self.width: float | None = width
        self.height: float | None = height
        self.clip: float | str | None = clip

    def _repr_fields(self) -> str:
        return f"path={self.path!r}"
