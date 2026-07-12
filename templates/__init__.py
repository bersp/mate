"""Template stack: theme classes a presentation inherits from.

Each entry in ``config.templates`` resolves to a module holding a
``PresentationTemplate`` class: a path to a ``.py`` file is loaded directly,
and any other name maps to the built-in ``mate.templates.<name>``.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from ..config import _DEFAULTS


def load_template(name: str) -> type:
    """Return the ``PresentationTemplate`` class of the template ``name``.

    ``name`` is either a path to a ``.py`` file or a built-in template name
    (a module under ``mate.templates``). The template's name (the file stem
    for a path) claims the ``<template>.<prop>`` config namespace, so it must
    not collide with a core configuration namespace.
    """
    path = Path(name)
    template_name = path.stem if path.suffix == ".py" else name
    reserved = {key.split(".", 1)[0] for key in _DEFAULTS}
    if template_name in reserved:
        raise ValueError(
            f"Template name {template_name!r} collides with the "
            f"{template_name!r} configuration namespace; rename the template."
        )
    if path.suffix == ".py" and path.is_file():
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(f"mate.templates.{name}")
    return module.PresentationTemplate
