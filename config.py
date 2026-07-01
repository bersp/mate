"""Process-global configuration singleton: slide size, color palette, and template stack."""

from __future__ import annotations

import logging
import re

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")

_MISSING = object()


def _template_namespace(key: str) -> str | None:
    """Return the ``<name>`` of a ``template.<name>.<prop>`` key, else ``None``."""
    parts = key.split(".")
    if len(parts) >= 3 and parts[0] == "template":
        return parts[1]
    return None

# Default values templates may read via ``config.get``. Keys are dotted
# paths; a template either uses the default or hardcodes its own literal.
#
# Typography keys follow ``<role>.<dimension>``: every typographic role
# (``text``, ``title``, ``subtitle``, ``math``) carries the dimensions it needs
# (``font``, ``fontweight``, ``fontsize``, ``color``). The font/size literals are kept in sync
# with ``typst query`` on a blank doc so the rendered output never relies on
# Typst's implicit fallback; ``color`` is a palette name resolved via
# ``config.colors``.
_DEFAULTS: dict[str, object] = {
    "slide.width": 16.0,
    "slide.height": 9.0,
    "region.full_with_margins.margins": 0.7,
    "region.default": "content",
    "region.content.anchor": "top-left",
    "region.content.arrange_gap": 0.25,
    "arrange.gap": 0.2,
    "line.stroke_width": 0.03,
    "image.align": "center",
    "typst.preamble": "",
    "text.font": "libertinus serif",
    "text.fontweight": "regular",
    "text.fontsize": 12.0,
    "text.color": "black",
    "text.line_gap": 0.25,
    "title.font": "libertinus serif",
    "title.fontweight": "bold",
    "title.fontsize": 14.0,
    "title.color": "black",
    "subtitle.font": "libertinus serif",
    "subtitle.fontweight": "regular",
    "subtitle.fontsize": 12.0,
    "subtitle.color": "darker_gray",
    "math.font": "libertinus serif",
    "math.fontweight": "regular",
    "math.fontsize": 12.0,
    "math.color": "black",
    "list.bullet": "square",
    "list.bullet_scale": 0.8,
    "list.bullet_gap": 0.2,
    "list.dash_thickness": 0.06,
    "footer.show": True,
    "footer.show_total": False,
}

_DEFAULT_PALETTE: dict[str, str] = {
    "black": "#2b3339",
    "darkest_gray": "#323B41",
    "darker_gray": "#3A454A",
    "dark_gray": "#4C5B6A",
    "gray": "#ADBCC1",
    "lighter_gray": "#D8E2E9",
    "lightest_gray": "#E5EAF0",
    "white": "#ECF0F4",
    "red": "#C95E61",
    "orange": "#E69875",
    "yellow": "#DBBC7F",
    "green": "#689C6E",
    "aqua": "#73AD9C",
    "blue": "#6F8AA6",
    "purple": "#B891B0",
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
        self.colors: Colors = Colors()
        self.templates: list[str] = []
        self.font_paths: list[str] = []
        self._defaults: dict[str, object] = dict(_DEFAULTS)

    @property
    def slide_width(self) -> float:
        return float(self._defaults["slide.width"])

    @property
    def slide_height(self) -> float:
        return float(self._defaults["slide.height"])

    def set_debug(self, enabled: bool) -> None:
        """Enable or disable DEBUG narration on the ``mate`` logger."""
        logging.getLogger("mate").setLevel(logging.DEBUG if enabled else logging.INFO)

    def get(self, key: str, default: object = _MISSING) -> object:
        """Return the value registered under ``key``.

        With ``default`` given, return it when ``key`` is unset — the path a
        template uses for its ``template.<name>.<prop>`` keys, which carry no
        :data:`_DEFAULTS` entry. Without ``default``, an unset key raises
        :class:`ValueError`.
        """
        if key in self._defaults:
            return self._defaults[key]
        if default is not _MISSING:
            return default
        defined = ", ".join(sorted(self._defaults))
        raise ValueError(
            f"{key!r} is not a defined config key. Defined keys: {defined}."
        )

    def set(self, key: str, value: object) -> None:
        """Override the default for ``key`` process-wide."""
        self._defaults[key] = value

    def apply_overrides(self, values: dict[str, object]) -> None:
        """Set each key in ``values`` after checking it is allowed.

        A key is allowed when it is a defined :data:`_DEFAULTS` key or a
        ``template.<name>.<prop>`` key; templates own that namespace and supply
        their own defaults, and its keys carry no entry here. Any other key
        raises :class:`ValueError` before any value is set.
        """
        for key in values:
            if key in self._defaults:
                continue
            if _template_namespace(key) is not None:
                continue
            defined = ", ".join(sorted(self._defaults))
            raise ValueError(
                f"{key!r} is not a defined config key and is not a "
                f"'template.<name>.<prop>' key. Defined keys: {defined}."
            )
        self._defaults.update(values)


config = Config()
