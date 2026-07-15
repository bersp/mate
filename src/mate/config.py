"""Process-global configuration singleton: slide size, color palette, and template stack."""

from __future__ import annotations

import logging
import re
from pathlib import Path

_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")

_MISSING = object()

# Default values templates may read via ``config.get``. Keys are dotted
# paths; a template either uses the default or hardcodes its own literal.
#
# Typography keys follow ``<role>.<dimension>``: every typographic role
# (``text``, ``title``, ``subtitle``, ``math``) carries the dimensions it needs
# (``font``, ``fontweight``, ``fontsize``, ``color``). The cover splits into
# ``cover.title``, ``cover.subtitle`` and ``cover.author`` roles, each carrying
# the same dimensions. The font/size literals are kept in sync
# with ``typst query`` on a blank doc so the rendered output never relies on
# Typst's implicit fallback; ``color`` is a palette name resolved via
# ``config.colors``.
#
# ``code.*`` styles code blocks. ``code.theme`` maps each syntax role to the
# property dict applied to its tokens (any ``set_<prop>`` of a ``Text`` leaf);
# a role left out inherits ``code.color``. ``code.line_height`` is the
# vertical step between lines in multiples of the font size.
# ``code.header_bg_color`` and ``code.title_color`` style the header bar a
# ``title`` opens above the code.
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
    "cover.title.font": "libertinus serif",
    "cover.title.fontweight": "bold",
    "cover.title.fontsize": 14.0,
    "cover.title.color": "black",
    "cover.subtitle.font": "libertinus serif",
    "cover.subtitle.fontweight": "regular",
    "cover.subtitle.fontsize": 12.0,
    "cover.subtitle.color": "darker_gray",
    "cover.author.font": "libertinus serif",
    "cover.author.fontweight": "regular",
    "cover.author.fontsize": 12.0,
    "cover.author.color": "black",
    "math.font": "libertinus serif",
    "math.fontweight": "regular",
    "math.fontsize": 12.0,
    "math.color": "black",
    "code.font": "DejaVu Sans Mono",
    "code.fontsize": 10.0,
    "code.color": "black",
    "code.bg_color": "lightest_gray",
    "code.padding": 0.35,
    "code.corner_radius": 0.1,
    "code.line_height": 1.25,
    "code.numbers": False,
    "code.numbers_start": 1,
    "code.numbers_color": "gray",
    "code.header_bg_color": "lighter_gray",
    "code.title_color": "dark_gray",
    "code.theme": {
        "keyword": {"color": "purple"},
        "string": {"color": "green"},
        "comment": {"color": "gray", "style": "italic"},
        "number": {"color": "orange"},
        "function": {"color": "blue"},
        "builtin": {"color": "aqua"},
        "decorator": {"color": "red"},
    },
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

        With ``default`` given, return it when ``key`` is unset: the path a
        template uses for its ``<template>.<prop>`` keys, which carry no
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

    def template_names(self) -> set[str]:
        """Return the namespace name of every template in :attr:`templates`.

        A ``.py`` entry is named by its file stem; any other entry is a
        built-in template name.
        """
        return {
            Path(entry).stem if entry.endswith(".py") else entry
            for entry in self.templates
        }

    def apply_overrides(self, values: dict[str, object]) -> None:
        """Set each key in ``values`` after checking it is allowed.

        A key is allowed when it is a defined :data:`_DEFAULTS` key or a
        ``<template>.<prop>`` key of a loaded template; templates own the
        namespace carrying their name and supply their own defaults, so those
        keys have no entry here. Any other key raises :class:`ValueError`
        before any value is set.
        """
        template_names = self.template_names()
        for key in values:
            if key in self._defaults:
                continue
            if "." in key and key.split(".", 1)[0] in template_names:
                continue
            defined = ", ".join(sorted(self._defaults))
            namespaces = ", ".join(sorted(template_names)) or "none"
            raise ValueError(
                f"{key!r} is not a defined config key and is not a "
                f"'<template>.<prop>' key of a loaded template "
                f"(loaded templates: {namespaces}). Defined keys: {defined}."
            )
        self._defaults.update(values)


config = Config()
