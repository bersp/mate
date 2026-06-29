from __future__ import annotations

from ..config import config

# A stop is ``(hex_color, position)`` where position is a fraction in [0, 1]
# or ``None`` to let the backend space the stops evenly.
Stop = tuple[str, "float | None"]
StopArg = "str | tuple[str, float | str]"


def _normalize_position(pos: float | str) -> float:
    """Resolve a stop position (``0..1`` float or ``"N%"`` string) to a fraction."""
    if isinstance(pos, str) and pos.endswith("%"):
        pos = float(pos[:-1]) / 100.0
    if not isinstance(pos, (int, float)) or isinstance(pos, bool) or not (0.0 <= pos <= 1.0):
        raise ValueError(
            f"gradient stop position must be a number in 0..1 or an 'N%' "
            f"string, got {pos!r}"
        )
    return float(pos)


def _resolve_stops(stops: tuple[StopArg, ...]) -> list[Stop]:
    """Resolve each stop's colour via ``config.colors`` and its position.

    A stop is a colour (palette name or hex) or a ``(colour, position)`` pair.
    At least two stops are required.
    """
    if len(stops) < 2:
        raise ValueError(f"a gradient needs at least 2 stops, got {len(stops)}")
    resolved: list[Stop] = []
    for stop in stops:
        if isinstance(stop, (tuple, list)):
            if len(stop) != 2:
                raise ValueError(
                    f"a gradient stop pair must be (colour, position), got {stop!r}"
                )
            colour, pos = stop[0], _normalize_position(stop[1])
        else:
            colour, pos = stop, None
        if not isinstance(colour, str):
            raise ValueError(f"gradient stop colour must be a string, got {colour!r}")
        resolved.append((config.colors.get(colour), pos))
    return resolved


class Gradient:
    """A colour gradient usable wherever a solid ``fill_color``/``stroke_color`` is.

    Build one with the :meth:`linear` or :meth:`radial` factories rather than
    the constructor. Each stop is a palette name or hex string, optionally
    paired with a position (a fraction in ``0..1`` or an ``"N%"`` string);
    bare stops are spaced evenly by the backend. Stop colours are resolved
    against ``config.colors`` at construction, like a solid colour.

    Attributes
    ----------
    kind : str
        ``"linear"`` or ``"radial"``.
    stops : list of (str, float or None)
        Resolved ``(hex, position)`` stops.
    angle : float
        Direction in degrees, for a linear gradient.
    center : tuple of float
        ``(x, y)`` in ``0..1`` of the bounding box, for a radial gradient.
    radius : float
        Radius as a fraction of the bounding box, for a radial gradient.
    """

    def __init__(
        self,
        kind: str,
        stops: list[Stop],
        *,
        angle: float = 0.0,
        center: tuple[float, float] = (0.5, 0.5),
        radius: float = 0.5,
    ) -> None:
        self.kind = kind
        self.stops = stops
        self.angle = angle
        self.center = center
        self.radius = radius

    @classmethod
    def linear(cls, *stops: StopArg, angle: float = 0.0) -> Gradient:
        """Build a linear gradient running at ``angle`` degrees (0 = left to right)."""
        return cls("linear", _resolve_stops(stops), angle=angle)

    @classmethod
    def radial(
        cls,
        *stops: StopArg,
        center: tuple[float, float] = (0.5, 0.5),
        radius: float = 0.5,
    ) -> Gradient:
        """Build a radial gradient centred at ``center`` with fractional ``radius``."""
        cx, cy = center
        if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0):
            raise ValueError(f"gradient center must be in 0..1, got {center!r}")
        if radius <= 0.0:
            raise ValueError(f"gradient radius must be positive, got {radius!r}")
        return cls("radial", _resolve_stops(stops), center=center, radius=radius)

    def __repr__(self) -> str:
        return f"Gradient(kind={self.kind!r}, stops={self.stops!r})"
