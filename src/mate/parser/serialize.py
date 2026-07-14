"""Serialize the tokenized IR back into Markdown text.

The render pipeline feeds Markdown strings to the template's ``add_*`` methods,
which hand them on to the backend; the backend is the only layer that knows how
to translate Markdown markup into its own syntax. This module is the inverse of
:func:`~mate.parser.markdown.parse_markdown` for inline content.
"""

from __future__ import annotations

from .ir import Bold, Code, Inline, Italic, LineBreak, Math, Pause, TextRun

_TEXT_ESCAPE = str.maketrans({c: f"\\{c}" for c in "\\*_`$|"})


def inlines_to_markdown(inlines: list[Inline]) -> str:
    """Fold a list of :class:`Inline` tokens into a Markdown string.

    Literal text has its Markdown-significant characters backslash-escaped so
    it is not re-read as markup (``|`` included, so a literal pipe never pairs
    into a ``||`` reveal marker); emphasis, code, and math are re-emitted with
    their Markdown delimiters; a reveal marker is re-emitted as ``||``; a hard
    line break is re-emitted as a trailing backslash before the newline.
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
            case Math(raw, display):
                out.append(f"$$ {raw} $$" if display else f"${raw}$")
            case LineBreak():
                out.append("\\\n")
            case Pause():
                out.append("||")
    return "".join(out)
