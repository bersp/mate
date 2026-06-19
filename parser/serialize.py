"""Serialize the tokenized IR back into Markdown text.

The render pipeline feeds Markdown strings to the template's ``add_*`` methods,
which hand them on to the backend; the backend is the only layer that knows how
to translate Markdown markup into its own syntax. This module is the inverse of
:func:`~mate.parser.markdown.parse_markdown` for inline content.
"""

from __future__ import annotations

from .ir import Bold, Code, Inline, Italic, Math, TextRun

_TEXT_ESCAPE = str.maketrans({c: f"\\{c}" for c in "\\*_`$"})


def inlines_to_markdown(inlines: list[Inline]) -> str:
    """Fold a list of :class:`Inline` tokens into a Markdown string.

    Literal text has its Markdown-significant characters backslash-escaped so
    it is not re-read as markup; emphasis, code, and math are re-emitted with
    their Markdown delimiters.
    """
    out: list[str] = []
    for node in inlines:
        match node:
            case TextRun(text):
                out.append(text.translate(_TEXT_ESCAPE))
            case Bold(children):
                out.append(f"**{inlines_to_markdown(children)}**")
            case Italic(children):
                out.append(f"*{inlines_to_markdown(children)}*")
            case Code(text):
                out.append(f"`{text}`")
            case Math(raw):
                out.append(f"${raw}$")
    return "".join(out)
