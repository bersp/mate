"""Template stack: theme classes a presentation inherits from, addressed by file name.

``config.templates`` lists file names (without extension); each name maps to a module
``mate.templates.<name>`` holding a ``<Name>Template`` class (CamelCase of the file name
plus ``Template``).
"""

from __future__ import annotations

import importlib


def load_template(name: str) -> type:
    """Return the template class defined in ``mate.templates.<name>``.

    The class is named by CamelCasing ``name`` and appending ``Template``:
    ``"nice"`` -> ``NiceTemplate``, ``"my_theme"`` -> ``MyThemeTemplate``.
    """
    module = importlib.import_module(f"mate.templates.{name}")
    class_name = "".join(part.capitalize() for part in name.split("_")) + "Template"
    return getattr(module, class_name)
