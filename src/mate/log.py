"""Process-global logging: the rich-backed ``mate`` logger.

One logger named ``mate`` carries both output layers: user-facing progress at
INFO and developer narration at DEBUG. "Debug mode" is the logger sitting at
DEBUG level, set through ``config.set_debug``.

Messages opt into rich markup per call with
``extra={"markup": True, "highlighter": None}``; the handler leaves markup off
by default so message data containing brackets is not mangled. Narration is
hand-placed ``logger.debug(...)`` at the lifecycle points worth watching, in
library code, so the same presentation script run with debug on streams them.
Guard an expensive debug payload with ``if logger.isEnabledFor(logging.DEBUG)``
before building it.
"""

from __future__ import annotations

import logging

from rich.logging import RichHandler

logger = logging.getLogger("mate")
logger.addHandler(RichHandler(show_path=False, keywords=[], log_time_format="%X"))
logger.setLevel(logging.INFO)
logger.propagate = False
