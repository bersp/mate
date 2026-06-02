from __future__ import annotations

import numpy as np

from ..config import config
from ..core.element import Anchor, Element, anchor_offsets
from ..core.vec import Vec, VecLike
from ..log import logger
from .arrange import arrange as _arrange_elements


class Region:
    """A rectangle with placement helpers.

    Parameters
    ----------
    center : VecLike
    width, height : float
    anchor : Anchor, optional
        Default anchor for :meth:`arrange`, inherited by sub-regions of
        :meth:`grid`. Defaults to ``"top-left"``.
    arrange_gap : float or None, optional
        Default vertical gap for :meth:`arrange`. ``None`` (default) reads
        ``arrange.gap`` from the config.
    """

    def __init__(
        self,
        center: VecLike,
        width: float,
        height: float,
        *,
        anchor: Anchor = "top-left",
        arrange_gap: float | None = None,
    ) -> None:
        self._center: Vec = Vec(center)
        self._width: float = float(width)
        self._height: float = float(height)
        self._anchor: Anchor = anchor
        self._arrange_gap: float = (
            config.get("arrange.gap") if arrange_gap is None else float(arrange_gap)
        )
        self.elements: list[Element] = []

    @classmethod
    def from_vertices(
        cls,
        top_left: VecLike,
        bottom_right: VecLike,
        **kw,
    ) -> Region:
        tl = Vec(top_left)
        br = Vec(bottom_right)
        return cls(
            ((tl.x + br.x) / 2, (tl.y + br.y) / 2),
            br.x - tl.x,
            tl.y - br.y,
            **kw,
        )

    @classmethod
    def create_full(cls, **kw) -> Region:
        """Region covering the whole slide."""
        return cls((0.0, 0.0), config.slide_width, config.slide_height, **kw)

    @classmethod
    def create_left(cls, width: float, **kw) -> Region:
        """Full-height column flush with the slide's left edge."""
        cx = -config.slide_width / 2 + width / 2
        return cls((cx, 0.0), width, config.slide_height, **kw)

    @classmethod
    def create_right(cls, width: float, **kw) -> Region:
        """Full-height column flush with the slide's right edge."""
        cx = config.slide_width / 2 - width / 2
        return cls((cx, 0.0), width, config.slide_height, **kw)

    @classmethod
    def create_top(cls, height: float, **kw) -> Region:
        """Full-width band flush with the slide's top edge."""
        cy = config.slide_height / 2 - height / 2
        return cls((0.0, cy), config.slide_width, height, **kw)

    @classmethod
    def create_bottom(cls, height: float, **kw) -> Region:
        """Full-width band flush with the slide's bottom edge."""
        cy = -config.slide_height / 2 + height / 2
        return cls((0.0, cy), config.slide_width, height, **kw)

    @classmethod
    def create_inner(
        cls,
        *,
        left: Region | None = None,
        right: Region | None = None,
        top: Region | None = None,
        bottom: Region | None = None,
        **kw,
    ) -> Region:
        """Region of the slide not covered by the given side regions."""
        half_w = config.slide_width / 2
        half_h = config.slide_height / 2
        lg = (left.right.x + half_w) if left else 0.0
        rg = (half_w - right.left.x) if right else 0.0
        tg = (half_h - top.bottom.y) if top else 0.0
        bg = (bottom.top.y + half_h) if bottom else 0.0

        region = cls.create_full(**kw)
        region.adjust_borders(left=-lg, right=-rg, top=-tg, bottom=-bg)
        return region

    @property
    def center(self) -> Vec:
        return self._center

    @property
    def width(self) -> float:
        return self._width

    @property
    def height(self) -> float:
        return self._height

    @property
    def anchor(self) -> Anchor:
        return self._anchor

    @property
    def arrange_gap(self) -> float:
        return self._arrange_gap

    @property
    def left(self) -> Vec:
        """Midpoint of the left edge."""
        return Vec(self._center.x - self._width / 2, self._center.y)

    @property
    def right(self) -> Vec:
        """Midpoint of the right edge."""
        return Vec(self._center.x + self._width / 2, self._center.y)

    @property
    def top(self) -> Vec:
        """Midpoint of the top edge."""
        return Vec(self._center.x, self._center.y + self._height / 2)

    @property
    def bottom(self) -> Vec:
        """Midpoint of the bottom edge."""
        return Vec(self._center.x, self._center.y - self._height / 2)

    def get_anchor_point(self, anchor: Anchor) -> Vec:
        """Return the position of the given anchor on this region."""
        h_mul, v_mul = anchor_offsets(anchor)
        left_x = self._center.x - self._width / 2
        bottom_y = self._center.y - self._height / 2
        return Vec(left_x + h_mul * self._width, bottom_y + v_mul * self._height)

    def set_width(self, value: float) -> Region:
        self._width = float(value)
        return self

    def set_height(self, value: float) -> Region:
        self._height = float(value)
        return self

    def set_center(self, value: VecLike) -> Region:
        self._center = Vec(value)
        return self

    def set_arrange_gap(self, value: float) -> Region:
        self._arrange_gap = float(value)
        return self

    @staticmethod
    def merge_regions(regions: list[Region]) -> Region:
        """Return a region whose bbox encloses every region in ``regions``."""
        lefts = [r.left.x for r in regions]
        rights = [r.right.x for r in regions]
        tops = [r.top.y for r in regions]
        bottoms = [r.bottom.y for r in regions]
        left, r = min(lefts), max(rights)
        b, t = min(bottoms), max(tops)
        return Region(((left + r) / 2, (t + b) / 2), r - left, t - b)

    def adjust_borders(
        self,
        *,
        left: float = 0.0,
        right: float = 0.0,
        top: float = 0.0,
        bottom: float = 0.0,
    ) -> Region:
        """Move each border outward (positive) or inward (negative), in place.

        Each kwarg is the signed displacement of the corresponding edge
        along its outward normal. ``left=+1`` pushes the left border 1
        unit further left (the region grows); ``left=-1`` brings it
        inward (the region shrinks). Returns ``self`` for chaining.
        """
        self._width = self._width + left + right
        self._height = self._height + top + bottom
        self._center = Vec(
            self._center.x + (right - left) / 2,
            self._center.y + (top - bottom) / 2,
        )
        return self

    def grid(
        self,
        template: list[list[str]] | np.ndarray,
        *,
        hgap: float = 0.0,
        vgap: float = 0.0,
        width_ratios: list[float] | None = None,
        height_ratios: list[float] | None = None,
    ) -> dict[str, Region]:
        """Split into a grid; cells sharing a label merge into one region.

        ``template`` is a ``rows × cols`` array of labels with row 0 on
        top. Each unique label produces one :class:`Region` covering the
        bounding box of its cells (non-contiguous labels yield the
        enclosing box). ``width_ratios`` and ``height_ratios`` set
        relative cell sizes and default to uniform. Output regions
        inherit ``anchor`` and ``arrange_gap`` from this region.

        Example
        -------
        A header spanning two columns over a left/right body::

            region.grid([["head", "head"],
                         ["left", "right"]],
                        vgap=0.3, height_ratios=[1, 3])
            # -> {"head": Region(...), "left": Region(...), "right": Region(...)}
        """
        grid = np.asarray(template)
        if grid.ndim != 2:
            raise ValueError(f"grid template must be 2D, got shape {grid.shape}")
        nrows, ncols = grid.shape

        wr = (
            np.full(ncols, 1.0 / ncols)
            if width_ratios is None
            else np.asarray(width_ratios, dtype=float) / float(np.sum(width_ratios))
        )
        hr = (
            np.full(nrows, 1.0 / nrows)
            if height_ratios is None
            else np.asarray(height_ratios, dtype=float) / float(np.sum(height_ratios))
        )

        cell_w = wr * (self._width - hgap * (ncols - 1))
        cell_h = hr * (self._height - vgap * (nrows - 1))

        left_edges = np.empty(ncols)
        x = self._center.x - self._width / 2
        for j, w in enumerate(cell_w):
            left_edges[j] = x
            x += w + hgap
        top_edges = np.empty(nrows)
        y = self._center.y + self._height / 2
        for i, h in enumerate(cell_h):
            top_edges[i] = y
            y -= h + vgap

        out: dict[str, Region] = {}
        for label in np.unique(grid):
            rows, cols = np.where(grid == label)
            cmin, cmax = int(cols.min()), int(cols.max())
            rmin, rmax = int(rows.min()), int(rows.max())
            left = left_edges[cmin]
            r = left_edges[cmax] + cell_w[cmax]
            t = top_edges[rmin]
            b = top_edges[rmax] - cell_h[rmax]
            out[str(label)] = Region(
                ((left + r) / 2, (t + b) / 2),
                r - left,
                t - b,
                anchor=self._anchor,
                arrange_gap=self._arrange_gap,
            )
        return out

    def add(self, element: Element) -> Element:
        """Append ``element`` to :attr:`elements` and return it."""
        self.elements.append(element)
        logger.debug(
            rf"[yellow]REGION ADD ::[/yellow] {element!r} -> {self!r}",
            extra={"markup": True, "highlighter": None},
        )
        return element

    def remove(self, element: Element) -> None:
        """Remove ``element`` from :attr:`elements`."""
        self.elements.remove(element)
        logger.debug(
            rf"[yellow]REGION REMOVE ::[/yellow] {element!r}",
            extra={"markup": True, "highlighter": None},
        )

    def replace(self, old: Element, new: Element) -> None:
        """Replace ``old`` with ``new`` in :attr:`elements`, preserving order."""
        self.elements[self.elements.index(old)] = new
        logger.debug(
            rf"[yellow]REGION REPLACE ::[/yellow] {old!r} -> {new!r}",
            extra={"markup": True, "highlighter": None},
        )

    def remove_all(self) -> None:
        """Empty :attr:`elements`."""
        self.elements.clear()

    def arrange(self) -> None:
        """Stack :attr:`elements` using :attr:`anchor` and :attr:`arrange_gap`."""
        if self.elements:
            logger.debug(
                rf"[yellow]REGION ARRANGE ::[/yellow] {self!r}",
                extra={"markup": True, "highlighter": None},
            )
        _arrange_elements(
            self.elements,
            pos=self.get_anchor_point(self._anchor),
            anchor=self._anchor,
            gap=self._arrange_gap,
        )

    def __repr__(self) -> str:
        return (
            f"Region(center={self._center!r}, width={self._width:.4g}, "
            f"height={self._height:.4g}, anchor={self._anchor!r}, "
            f"arrange_gap={self._arrange_gap:.4g})"
        )


class Layout:
    r"""A named container of :class:`Region`\ s, keyed by name."""

    def __init__(self) -> None:
        self.regions: dict[str, Region] = {}
        self._active: Region | None = None

    @property
    def active(self) -> Region | None:
        return self._active

    def add(self, name: str, region: Region) -> Region:
        """Attach ``region`` to this layout under ``name`` and return it."""
        self.regions[name] = region
        return region

    def get(self, name: str) -> Region:
        """Return the region under ``name``, or the active one for ``"active"``.

        Raises :class:`ValueError` listing the defined names if ``name`` is
        neither ``"active"`` nor a region in this layout.
        """
        if name == "active":
            return self._active
        if name not in self.regions:
            defined = ", ".join(self.regions)
            raise ValueError(
                f"{name!r} is not a region in this layout. Defined regions: {defined}."
            )
        return self.regions[name]

    def set_active(self, name: str) -> Region:
        """Set the active region to the one under ``name`` and return it."""
        self._active = self.get(name)
        return self._active

    def remove_all_elements(self) -> None:
        """Clear :attr:`Region.elements` on every region in this layout."""
        for region in self.regions.values():
            region.remove_all()

    def __repr__(self) -> str:
        body = ", ".join(f"{k}={v!r}" for k, v in self.regions.items())
        return f"Layout({body})"
