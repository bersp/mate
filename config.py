"""Process-global configuration singleton: slide size and the color palette."""
from __future__ import annotations

import re

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")

_DEFAULT_PALETTE: dict[str, str] = {
    "BLACK": "#2b3339",
    "DARKEST_GRAY": "#323B41",
    "DARKER_GRAY": "#3A454A",
    "DARK_GRAY": "#4C5B6A",
    "GRAY": "#ADBCC1",
    "LIGHTER_GRAY": "#D8E2E9",
    "LIGHTEST_GRAY": "#E5EAF0",
    "WHITE": "#ECF0F4",
    "RED": "#C95E61",
    "ORANGE": "#E69875",
    "YELLOW": "#DBBC7F",
    "GREEN": "#689C6E",
    "AQUA": "#73AD9C",
    "BLUE": "#6F8AA6",
    "PURPLE": "#B891B0",
}


class Colors:
    """Named color palette mapping logical names to hex strings."""

    def __init__(self) -> None:
        self._palette: dict[str, str] = {}
        self.set_multiple(_DEFAULT_PALETTE)

    def get(self, name: str) -> str:
        """Return the hex string for ``name``.

        A palette name resolves to its hex; a literal hex string passes
        through unchanged. Anything else raises :class:`ValueError`.
        """
        if name in self._palette:
            return self._palette[name]
        if _HEX_RE.fullmatch(name):
            return name
        defined = ", ".join(sorted(self._palette))
        raise ValueError(
            f"{name!r} is not a defined color nor a hex string. "
            f"Defined colors: {defined}."
        )

    def set(self, name: str, hex_value: str) -> None:
        """Set ``name`` to ``hex_value``."""
        self._palette[name] = hex_value

    def set_multiple(self, colors: dict[str, str]) -> None:
        """Set each ``name``/``hex_value`` entry of ``colors``."""
        self._palette.update(colors)


class Config:
    """Process-global configuration knobs."""

    def __init__(self) -> None:
        self.slide_width: float = 0.0
        self.slide_height: float = 0.0
        self.colors: Colors = Colors()

    def set_slide_size(self, width: float, height: float) -> None:
        self.slide_width = float(width)
        self.slide_height = float(height)


config = Config()
