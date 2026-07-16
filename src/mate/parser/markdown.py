r"""Parse a Markdown source string into a :class:`ParsedDocument`.

An optional leading YAML front matter block, fenced by ``---`` lines, carries
the presentation's config (see :class:`~mate.parser.ir.FrontMatter`). Slide
syntax: a ``#`` (h1) heading opens a new slide and is its title; a ``##`` (h2)
heading that is the slide's first block is its subtitle. Every other construct
becomes a body block. Supported v1 content: paragraphs with inline
bold/italic/code, ``||`` reveal markers (escapable as ``\||``), hard line
breaks (a trailing backslash or two trailing spaces before a newline),
Typst-style ``$...$`` and ``$$...$$`` math, bullet and ordered lists (nested),
in-body headings, fenced code blocks (``python mate`` runs as Python,
``markdown <name>`` is a directive body, anything else is displayed code),
and blockquotes that call a presentation method, one ``> method name : args``
(or no-arg ``> method name``) call per line. Math spans are carved out before
emphasis parsing so their ``*``/``_`` are not consumed as markup. Unsupported
constructs raise at parse time.
"""

from __future__ import annotations

import ast
import re

import yaml
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.dollarmath import dollarmath_plugin

from .ir import (
    Block,
    Bold,
    BulletList,
    Code,
    CodeBlock,
    FencedBlock,
    FrontMatter,
    Heading,
    Inline,
    Italic,
    LineBreak,
    ListItem,
    Math,
    MathBlock,
    MethodCall,
    OrderedList,
    Paragraph,
    ParsedDocument,
    ParsedSlide,
    Pause,
    PythonBlock,
    TextRun,
)
from ..core.directive import Directive

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)


def _tokenize(text: str) -> SyntaxTreeNode:
    r"""Tokenize Markdown ``text`` into a :class:`SyntaxTreeNode` tree.

    The ``text_join`` rule is disabled: backslash-escaped characters and HTML
    entities then reach the fold as separate ``text_special`` nodes, keeping
    an escaped ``\||`` distinguishable from a literal ``||`` reveal marker.
    """
    md = MarkdownIt("commonmark").use(dollarmath_plugin)
    md.disable("text_join")
    return SyntaxTreeNode(md.parse(text))


def parse_markdown(source: str) -> ParsedDocument:
    """Parse ``source`` into a :class:`ParsedDocument` stream of directives and slides."""
    frontmatter, body = _split_frontmatter(source)
    body = _separate_math_blocks(body)
    tree = _tokenize(body)

    doc = ParsedDocument(frontmatter=frontmatter)
    current: ParsedSlide | None = None
    pending_directive: Directive | None = None

    for node in tree.children:
        if _directive_marker(node):
            pending_directive = Directive()
            # The directive enters the stream at its marker position; a trailing
            # blockquote mutates this same object in place with its props.
            doc.items.append(pending_directive)
            continue
        # A blockquote right after a marker carries the directive's properties.
        if pending_directive is not None and node.type == "blockquote":
            _apply_directive_props(pending_directive, node)
            pending_directive = None
            continue
        pending_directive = None

        if node.type == "heading" and node.tag == "h1":
            current = ParsedSlide(title=_inlines_of(node))
            doc.items.append(current)
            continue

        if current is None:
            raise ValueError(
                "Markdown must open with a '# ' heading: "
                f"found a {node.type!r} block before the first slide title"
            )

        if (
            node.type == "heading"
            and node.tag == "h2"
            and not current.blocks
            and current.subtitle is None
        ):
            current.subtitle = _inlines_of(node)
            continue

        if node.type == "blockquote":
            current.blocks.extend(_fold_blockquote(node))
        else:
            current.blocks.append(_fold_block(node))

    return doc


def _directive_marker(node: SyntaxTreeNode) -> bool:
    """Return whether ``node`` is a ``#>`` directive marker.

    A directive marker is a single-line paragraph whose only text is ``#>``,
    opening an off-slide directive whose properties come from the blockquote
    right below it. Such a line is not a valid ATX heading; the tokenizer
    yields it as a paragraph. Text after ``#>`` on the same line raises
    :class:`ValueError`: a directive carries no positional argument, only
    ``key: value`` properties.
    """
    if node.type != "paragraph" or not node.children:
        return False
    text = node.children[0].content
    if "\n" in text or not text.lstrip().startswith("#>"):
        return False
    if text.strip() != "#>":
        raise ValueError(
            f"a '#>' directive marker takes no text; put properties on the "
            f"'>' lines below it, got {text.strip()!r}"
        )
    return True


def _apply_directive_props(directive: Directive, node: SyntaxTreeNode) -> None:
    """Collect the ``key: value`` lines of a marker's blockquote into ``directive``.

    Each non-blank line is ``key: value``; the value is read as a Python literal
    (``True``, ``42``, ``(1, 0)``, a quoted string, ...) when it parses as one,
    otherwise kept as the raw string. The result is stored in
    :attr:`Directive.props` under ``key``. Keys are not validated here — the
    consuming template decides which are meaningful. A malformed line or an
    empty value raises :class:`ValueError`.
    """
    content = node.children[0].children[0].content
    for line in content.split("\n"):
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not sep or not key:
            raise ValueError(f"directive property must be 'key: value', got {line!r}")
        if not value:
            raise ValueError(f"directive property {key!r} has an empty value")
        try:
            directive.props[key] = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            directive.props[key] = value


def _split_frontmatter(source: str) -> tuple[FrontMatter, str]:
    """Peel an optional leading ``---`` YAML block off ``source``.

    Returns the parsed :class:`FrontMatter` (empty when absent) and the
    remaining Markdown body.
    """
    match = _FRONTMATTER_RE.match(source)
    if match is None:
        return FrontMatter(), source
    data = yaml.safe_load(match.group(1)) or {}
    return _build_frontmatter(data), source[match.end() :]


def _separate_math_blocks(source: str) -> str:
    """Surround a lone ``$$`` delimiter line with blank lines so the display
    equation parses as its own block. Lines inside fenced code blocks (```` ``` ````
    or ``~~~``) are left untouched.
    """
    out: list[str] = []
    in_code = False
    in_math = False
    for line in source.split("\n"):
        stripped = line.strip()
        if not in_math and (stripped.startswith("```") or stripped.startswith("~~~")):
            in_code = not in_code
            out.append(line)
        elif in_code:
            out.append(line)
        elif stripped == "$$":
            if not in_math:
                if out and out[-1].strip() != "":
                    out.append("")
                out.append(line)
            else:
                out.append(line)
                out.append("")
            in_math = not in_math
        else:
            out.append(line)
    return "\n".join(out)


def _build_frontmatter(data: dict) -> FrontMatter:
    """Validate the raw YAML mapping and fold it into a :class:`FrontMatter`."""
    if not isinstance(data, dict):
        raise ValueError("Front matter must be a YAML mapping")
    unknown = set(data) - {"templates", "config", "colors", "font_paths"}
    if unknown:
        raise ValueError(
            f"Unknown front matter section(s): {sorted(unknown)}. "
            "Allowed: templates, config, colors, font_paths."
        )
    colors = data.get("colors") or {}
    for name, value in colors.items():
        if not isinstance(value, str):
            raise ValueError(
                f"Color {name!r} must be a quoted hex string "
                f'(e.g. "{name}": "#E69875"), got {value!r}'
            )
    return FrontMatter(
        templates=data.get("templates") or [],
        config=data.get("config") or {},
        colors=colors,
        font_paths=data.get("font_paths") or [],
    )


def _fold_block(node: SyntaxTreeNode) -> Block:
    match node.type:
        case "paragraph":
            return Paragraph(_inlines_of(node))
        case "heading":
            return Heading(int(node.tag[1:]), _inlines_of(node))
        case "bullet_list":
            return BulletList([_fold_list_item(c) for c in node.children])
        case "ordered_list":
            start = int(node.attrs.get("start", 1))
            return OrderedList(start, [_fold_list_item(c) for c in node.children])
        case "math_block":
            return MathBlock(node.content.strip())
        case "fence":
            lang, _, rest = node.info.partition(" ")
            name, _, args = rest.partition(":")
            if lang.strip() == "python" and name.strip() == "mate":
                return PythonBlock(node.content)
            if lang.strip() == "markdown":
                return FencedBlock(name.strip(), args.strip(), _fold_body(node.content))
            language, _, options = node.info.partition(":")
            return CodeBlock(language.strip(), options.strip(), node.content)
    raise _unsupported(node.type)


def _fold_blocks(nodes: list[SyntaxTreeNode]) -> list[Block]:
    """Fold a sequence of block nodes, expanding blockquotes to method calls."""
    blocks: list[Block] = []
    for node in nodes:
        if node.type == "blockquote":
            blocks.extend(_fold_blockquote(node))
        else:
            blocks.append(_fold_block(node))
    return blocks


def _fold_body(text: str) -> list[Block]:
    """Parse a Markdown ``text`` body (no slide title) into a list of blocks."""
    return _fold_blocks(_tokenize(_separate_math_blocks(text)).children)


def _fold_blockquote(node: SyntaxTreeNode) -> list[MethodCall]:
    """Fold a blockquote into one :class:`MethodCall` per line.

    Each line is ``method name : args``, or just ``method name`` for a call
    with no arguments. The name (before ``:``, or the whole line) is stripped
    and its inner spaces become underscores; the argument text (after ``:``)
    is kept verbatim apart from stripping, and is empty when the line has no
    ``:``.
    """
    content = node.children[0].children[0].content
    calls: list[MethodCall] = []
    for line in content.split("\n"):
        if not line.strip():
            continue
        name_part, _, args_part = line.partition(":")
        calls.append(MethodCall(name_part.strip().replace(" ", "_"), args_part.strip()))
    return calls


def _fold_list_item(node: SyntaxTreeNode) -> ListItem:
    blocks: list[Block] = []
    for child in node.children:
        if child.type == "blockquote":
            blocks.extend(_fold_blockquote(child))
        else:
            blocks.append(_fold_block(child))
    return ListItem(blocks)


def _inlines_of(node: SyntaxTreeNode) -> list[Inline]:
    """Fold the inline content of a ``heading`` or ``paragraph`` node.

    Such nodes wrap their content in a single ``inline`` child; an empty heading
    or paragraph has no child and yields an empty list.
    """
    if not node.children:
        return []
    return _fold_inlines(node.children[0].children)


def _fold_inlines(nodes: list[SyntaxTreeNode]) -> list[Inline]:
    out: list[Inline] = []
    for n in nodes:
        match n.type:
            case "text":
                if n.content:  # the tokenizer emits empty text nodes at span boundaries
                    out.extend(_split_pause_markers(n.content))
            case "text_special":
                # A backslash-escaped character or an HTML entity, resolved to
                # its literal character(s). Kept out of the ``||`` split so an
                # escaped ``\||`` never opens a reveal step.
                out.append(TextRun(n.content))
            case "strong":
                out.append(Bold(_fold_inlines(n.children)))
            case "em":
                out.append(Italic(_fold_inlines(n.children)))
            case "code_inline":
                out.append(Code(n.content))
            case "math_inline":
                out.append(Math(n.content.strip()))
            case "softbreak":
                out.append(TextRun(" "))
            case "hardbreak":
                out.append(LineBreak())
            case _:
                raise _unsupported(n.type)
    return out


def _split_pause_markers(text: str) -> list[Inline]:
    r"""Split ``text`` on ``||`` reveal markers into ``TextRun``/``Pause`` runs.

    Only plain text carries markers: an escaped ``\||`` reaches the fold as a
    separate ``text_special`` node and is never split.
    """
    out: list[Inline] = []
    for k, part in enumerate(text.split("||")):
        if k:
            out.append(Pause())
        if part:
            out.append(TextRun(part))
    return out


def _unsupported(node_type: str) -> ValueError:
    return ValueError(f"Markdown construct {node_type!r} is not supported")
