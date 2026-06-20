"""Template stack: theme classes a presentation inherits from.

Each entry in ``config.templates`` resolves to a module holding a
``PresentationTemplate`` class: a path to a ``.py`` file is loaded directly,
and any other name maps to the built-in ``mate.templates.<name>``.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path


def load_template(name: str) -> type:
    """Return the ``PresentationTemplate`` class of the template ``name``.

    ``name`` is either a path to a ``.py`` file or a built-in template name
    (a module under ``mate.templates``).
    """
    path = Path(name)
    if path.suffix == ".py" and path.is_file():
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(f"mate.templates.{name}")
    return module.PresentationTemplate
