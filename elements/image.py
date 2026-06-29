from __future__ import annotations

from ..core.element import Anchor, Element, HAlign, Placement
from ..core.registry import IDKey
from ..core.vec import VecLike


class Image(Element):
    """Image loaded from a file, sized by the backend.

    With neither ``width`` nor ``height`` the image renders at the file's
    natural size; with one set the other follows the file's aspect ratio;
    with both set the image is forced into that box.

    :meth:`crop` shows only a sub-rectangle of the image, given as
    fractions of the image, shrinking the element's measured size to that
    window.

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
    crop_window : tuple of float or None
        ``(x, y, width, height)`` in image fractions naming the visible
        sub-rectangle, or ``None`` for the whole image.
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
        self.crop_window: tuple[float, float, float, float] | None = None

    def crop(
        self,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 1.0,
        height: float = 1.0,
    ) -> Image:
        """Show only the ``(x, y, width, height)`` sub-rectangle of the image.

        All four values are fractions of the image with the origin at its
        top-left corner: ``x`` and ``width`` run along the width, ``y`` and
        ``height`` down the height. The defaults name the whole image, so a
        single axis can be cropped alone (``crop(y=0.2, height=0.6)``).
        Returns ``self`` for chaining.
        """
        self.set_crop((x, y, width, height))
        return self

    def set_crop(self, window: tuple[float, float, float, float] | None) -> None:
        """Set the visible sub-rectangle, or clear it with ``None``.

        ``window`` is ``(x, y, width, height)`` in image fractions; the
        whole-image window collapses to ``None``. Shrinks the element's
        measured size; invalidates the bbox cache of its tree.
        """
        if window is not None:
            x, y, width, height = window
            if not (
                0.0 <= x <= 1.0
                and 0.0 <= y <= 1.0
                and 0.0 < width <= 1.0
                and 0.0 < height <= 1.0
                and x + width <= 1.0 + 1e-9
                and y + height <= 1.0 + 1e-9
            ):
                raise ValueError(
                    "crop window must be fractions with 0 <= x, y, "
                    "0 < width, height <= 1, x + width <= 1 and "
                    f"y + height <= 1, got {window!r}"
                )
            if (x, y, width, height) == (0.0, 0.0, 1.0, 1.0):
                window = None
        self.crop_window = window
        self._invalidate_subtree_and_ancestors()

    def _repr_fields(self) -> str:
        return f"path={self.path!r}"
