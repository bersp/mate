"""Parse a Markdown source string into a :class:`ParsedDocument`.

An optional leading YAML front matter block, fenced by ``---`` lines, carries
the presentation's config (see :class:`~mate.parser.ir.FrontMatter`). Slide
syntax: a ``#`` (h1) heading opens a new slide and is its title; a ``##`` (h2)
heading that is the slide's first block is its subtitle. Every other construct
becomes a body block. Supported v1 content: paragraphs with inline
bold/italic/code, Typst-style ``$...$`` and ``$$...$$`` math, bullet and ordered
lists (nested), in-body headings, and blockquotes that call a presentation
method, one ``> method name : args`` (or no-arg ``> method name``) call per
line. Math spans are carved out before emphasis parsing so
their ``*``/``_`` are not consumed as markup. Unsupported constructs raise at
parse time.
"""

from __future__ import annotations

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
    Fragment,
    FrontMatter,
    Heading,
    Inline,
    Italic,
    ListItem,
    Math,
    MathBlock,
    MethodCall,
    OrderedList,
    Paragraph,
    ParsedDocument,
    ParsedSlide,
    TextRun,
)

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)


def _tokenize(text: str) -> SyntaxTreeNode:
    """Tokenize Markdown ``text`` into a :class:`SyntaxTreeNode` tree."""
    md = MarkdownIt("commonmark").use(dollarmath_plugin)
    return SyntaxTreeNode(md.parse(text))


def parse_markdown(source: str) -> ParsedDocument:
    """Parse ``source`` into a :class:`ParsedDocument` of tokenized slides."""
    frontmatter, body = _split_frontmatter(source)
    body = _separate_math_blocks(body)
    tree = _tokenize(body)

    doc = ParsedDocument(frontmatter=frontmatter)
    current: ParsedSlide | None = None

    for node in tree.children:
        if node.type == "heading" and node.tag == "h1":
            current = ParsedSlide(title=_inlines_of(node))
            doc.slides.append(current)
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
            if lang.strip() != "markdown" or name.strip() != "fragment":
                raise _unsupported("fence")
            return Fragment(args.strip(), _fold_body(node.content))
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
                    out.append(TextRun(n.content))
            case "strong":
                out.append(Bold(_fold_inlines(n.children)))
            case "em":
                out.append(Italic(_fold_inlines(n.children)))
            case "code_inline":
                out.append(Code(n.content))
            case "math_inline":
                out.append(Math(n.content.strip()))
            case "softbreak" | "hardbreak":
                out.append(TextRun(" "))
            case _:
                raise _unsupported(n.type)
    return out


def _unsupported(node_type: str) -> ValueError:
    return ValueError(f"Markdown construct {node_type!r} is not supported")
