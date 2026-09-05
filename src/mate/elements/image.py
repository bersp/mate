from __future__ import annotations

from ..core.element import Anchor, Element, HAlign, Placement
from ..core.registry import IDKey
from ..core.vec import VecLike

Window = tuple[float, float, float, float]


def _checked_window(window: Window | None, name: str) -> Window | None:
    """Validate ``(x, y, width, height)`` as fractions of an image.

    Returns the window with the whole-image one collapsed to ``None``. ``name``
    opens the message of the :class:`ValueError` raised for a window reaching
    outside the image.
    """
    if window is None:
        return None
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
            f"{name} window must be fractions with 0 <= x, y, "
            "0 < width, height <= 1, x + width <= 1 and "
            f"y + height <= 1, got {window!r}"
        )
    if (x, y, width, height) == (0.0, 0.0, 1.0, 1.0):
        return None
    return window


class Image(Element):
    """Image loaded from a file, sized by the backend.

    ``crop`` names the sub-rectangle of the file the element draws. The
    element is that piece and the rest of the file takes no part in the
    layout: ``width`` and ``height`` are the piece's rendered dimensions.
    With neither set the piece renders at the file's natural scale; with one
    set the other follows the file's aspect ratio; with both set the piece is
    forced into that box.

    :meth:`mask` covers the piece with a window, holding the rendered picture
    where it is and shrinking the measured size to the visible part.

    Parameters
    ----------
    path : str
        Filesystem path to the image file. Positional.
    width : float or None, optional
        Rendered width in cm, or ``None`` (default) to leave it free.
    height : float or None, optional
        Rendered height in cm, or ``None`` (default) to leave it free.
    crop : tuple of float or None, optional
        ``(x, y, width, height)`` in file fractions naming the sub-rectangle
        to draw, or ``None`` (default) for the whole file.
    pos, anchor, align, placement, z_order, id
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
        ``(x, y, width, height)`` in file fractions naming the drawn
        sub-rectangle, or ``None`` for the whole file.
    mask_window : tuple of float or None
        ``(x, y, width, height)`` in fractions of the drawn piece naming the
        visible part of it, or ``None`` for all of it.
    """

    def __init__(
        self,
        path: str,
        *,
        width: float | None = None,
        height: float | None = None,
        crop: Window | None = None,
        pos: VecLike | None = None,
        anchor: Anchor = "center",
        align: HAlign | None = None,
        placement: Placement = "fixed",
        z_order: float | None = None,
        id: IDKey | list[IDKey] | None = None,
    ) -> None:
        super().__init__(
            pos=pos,
            anchor=anchor,
            align=align,
            placement=placement,
            z_order=z_order,
            id=id,
        )
        self.path: str = path
        self.width: float | None = width
        self.height: float | None = height
        self.crop_window: Window | None = _checked_window(crop, "crop")
        self.mask_window: Window | None = None

    def crop(
        self,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 1.0,
        height: float = 1.0,
    ) -> Image:
        """Draw only the ``(x, y, width, height)`` sub-rectangle of the file.

        All four values are fractions of the file with the origin at its
        top-left corner: ``x`` and ``width`` run along the width, ``y`` and
        ``height`` down the height. The defaults name the whole file, so a
        single axis can be cropped alone (``crop(y=0.2, height=0.6)``).
        Returns ``self`` for chaining.
        """
        self.set_crop((x, y, width, height))
        return self

    def mask(
        self,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 1.0,
        height: float = 1.0,
    ) -> Image:
        """Show only the ``(x, y, width, height)`` window of the drawn piece.

        The four values are fractions of the piece :meth:`crop` selected, on
        the same axes. The picture keeps the size and the position it has and
        the element measures the window alone. Returns ``self`` for chaining.
        """
        self.set_mask((x, y, width, height))
        return self

    def get_crop(self) -> Window | None:
        """Return the drawn sub-rectangle ``(x, y, width, height)``, or ``None``."""
        return self.crop_window

    def get_mask(self) -> Window | None:
        """Return the visible window ``(x, y, width, height)``, or ``None``."""
        return self.mask_window

    def set_width(self, width: float | None) -> Image:
        """Set the rendered width constraint in cm, or ``None`` to leave it free.

        ``get_width`` reports the measured bbox width, not this constraint.
        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self.width = width
        self._invalidate_tree()
        return self

    def set_height(self, height: float | None) -> Image:
        """Set the rendered height constraint in cm, or ``None`` to leave it free.

        ``get_height`` reports the measured bbox height, not this constraint.
        Geometric mutator: invalidates the bbox cache of this element's tree.
        """
        self.height = height
        self._invalidate_tree()
        return self

    def set_crop(self, window: Window | None) -> None:
        """Set the drawn sub-rectangle, or clear it with ``None``.

        ``window`` is ``(x, y, width, height)`` in file fractions; the
        whole-file window collapses to ``None``. ``width`` and ``height`` size
        the piece it names; invalidates the bbox cache of this element's tree.
        """
        self.crop_window = _checked_window(window, "crop")
        self._invalidate_tree()

    def set_mask(self, window: Window | None) -> None:
        """Set the visible window of the drawn piece, or clear it with ``None``.

        ``window`` is ``(x, y, width, height)`` in fractions of the piece; the
        whole-piece window collapses to ``None``. Shrinks the element's
        measured size; invalidates the bbox cache of this element's tree.
        """
        self.mask_window = _checked_window(window, "mask")
        self._invalidate_tree()

    def _repr_fields(self) -> str:
        return f"path={self.path!r}"
