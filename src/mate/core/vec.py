from __future__ import annotations

from typing import TypeAlias

import numpy as np


VecLike: TypeAlias = "Vec | tuple[float, float] | list[float] | np.ndarray"
"""Anything that ``Vec(...)`` can ingest as a single positional argument."""


class Vec(np.ndarray):
    """2D vector backed by ``np.ndarray`` of shape ``(2,)``.

    Inherits numpy arithmetic and broadcasting; use it whenever something has
    "two coordinates" (position, size, center). Construct either from two
    scalars (``Vec(x, y)``) or from any 2-element array-like (``Vec((x, y))``,
    ``Vec([x, y])``, ``Vec(other_vec)``).

    Parameters
    ----------
    x : float or VecLike
        Either the first coordinate (when ``y`` is given) or the full
        2-element array-like.
    y : float, optional
        Second coordinate. Omit when ``x`` already carries both.
    """

    def __new__(cls, x: float | VecLike, y: float | None = None) -> Vec:
        data = np.asarray([x, y] if y is not None else x, dtype=float)
        if data.shape != (2,):
            raise ValueError(f"Vec must be 2D, got shape {data.shape}")
        return data.view(cls)

    @property
    def x(self) -> float:
        return float(self[0])

    @property
    def y(self) -> float:
        return float(self[1])

    def __repr__(self) -> str:
        return f"Vec({self.x}, {self.y})"

    __str__ = __repr__
