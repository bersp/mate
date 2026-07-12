"""Parse a Text leaf's inline Markdown markup into :class:`~mate.parser.ir.Inline`.

A deliberately simple scanner — not a full CommonMark engine — covering the
constructs a :class:`~mate.elements.text.Text` leaf carries: ``**bold**``,
``*italic*`` / ``_italic_``, ``` `code` ```, inline ``$math$`` and display
``$$math$$``, a trailing backslash before a newline as a hard line break,
plus backslash escapes. The produced tokens are backend-agnostic;
each backend turns them into its own syntax. This is the inverse of
:func:`~mate.parser.serialize.inlines_to_markdown`.
"""

from __future__ import annotations

from .ir import Bold, Code, Inline, Italic, LineBreak, Math, TextRun


def parse_markup(source: str) -> list[Inline]:
    """Scan ``source`` into a list of inline tokens."""
    return _scan(source, 0, len(source))


def _scan(s: str, i: int, end: int) -> list[Inline]:
    out: list[Inline] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            out.append(TextRun("".join(buf)))
            buf.clear()

    while i < end:
        c = s[i]
        if c == "\\" and i + 1 < end and s[i + 1] == "\n":
            flush()
            out.append(LineBreak())
            i += 2
        elif c == "\\" and i + 1 < end:
            buf.append(s[i + 1])
            i += 2
        elif c == "`":
            j = s.find("`", i + 1, end)
            if j == -1:
                buf.append(c)
                i += 1
            else:
                flush()
                out.append(Code(s[i + 1 : j]))
                i = j + 1
        elif c == "$":
            if s.startswith("$$", i):
                j = s.find("$$", i + 2, end)
                if j == -1:
                    buf.append(c)
                    i += 1
                else:
                    flush()
                    out.append(Math(s[i + 2 : j].strip(), display=True))
                    i = j + 2
            else:
                j = s.find("$", i + 1, end)
                if j == -1:
                    buf.append(c)
                    i += 1
                else:
                    flush()
                    out.append(Math(s[i + 1 : j]))
                    i = j + 1
        elif s.startswith("**", i):
            j = _find_delim(s, i + 2, end, "**")
            if j == -1:
                buf.append(c)
                i += 1
            else:
                flush()
                out.append(Bold(_scan(s, i + 2, j)))
                i = j + 2
        elif c in "*_":
            j = _find_delim(s, i + 1, end, c)
            if j == -1:
                buf.append(c)
                i += 1
            else:
                flush()
                out.append(Italic(_scan(s, i + 1, j)))
                i = j + 1
        else:
            buf.append(c)
            i += 1
    flush()
    return out


def _find_delim(s: str, i: int, end: int, delim: str) -> int:
    """Index of the closing ``delim`` run, or ``-1``.

    Skips backslash escapes and steps over code and math spans; a delimiter
    character inside them does not close the emphasis. When looking for a
    single ``*``/``_``, a doubled run is stepped over, staying available to
    close an enclosing bold span.
    """
    while i < end:
        c = s[i]
        if c == "\\":
            i += 2
        elif c == "`":
            j = s.find("`", i + 1, end)
            i = end if j == -1 else j + 1
        elif c == "$":
            close = "$$" if s.startswith("$$", i) else "$"
            j = s.find(close, i + len(close), end)
            i = end if j == -1 else j + len(close)
        elif len(delim) == 1 and s.startswith(delim * 2, i):
            i += 2
        elif s.startswith(delim, i):
            return i
        else:
            i += 1
    return -1
