"""Evaluation of the Python expressions authored inside a Markdown deck:
blockquote method-call arguments, fenced-block property text, and the
properties of a ``[...][...]`` markup span."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from typing import Any


@cache
def author_globals() -> dict:
    """Return the namespace an authored expression evaluates in: the public
    ``mate`` API."""
    import mate

    return {name: getattr(mate, name) for name in mate.__all__}


def eval_props(source: str) -> dict:
    """Evaluate authored keyword text (``color="red", fontsize=9``) into a
    ``name -> value`` mapping."""
    return eval(f"dict({source})", {"dict": dict, **author_globals()})


def eval_call(source: str, target: Callable) -> Any:
    """Call ``target`` with the authored argument text ``source``.

    ``source`` is spliced into a call expression, so it carries positional and
    keyword arguments alike (``"map", x=1``).
    """
    return eval(f"_target({source})", {"_target": target, **author_globals()})
