"""Parse a Markdown source string into a :class:`ParsedDocument`.

Slide syntax: a ``#`` (h1) heading opens a new slide and is its title; a ``##``
(h2) heading that is the slide's first block is its subtitle. Every other
construct becomes a body block. Supported v1 content: paragraphs with inline
bold/italic/code, Typst-style ``$...$`` and ``$$...$$`` math, bullet and ordered
lists (nested), and in-body headings. Math spans are carved out before emphasis
parsing so their ``*``/``_`` are not consumed as markup. Unsupported constructs
raise at parse time.
"""

from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.dollarmath import dollarmath_plugin

from .ir import (
    Block,
    Bold,
    BulletList,
    Code,
    Heading,
    Inline,
    Italic,
    ListItem,
    Math,
    MathBlock,
    OrderedList,
    Paragraph,
    ParsedDocument,
    ParsedSlide,
    TextRun,
)


def parse_markdown(source: str) -> ParsedDocument:
    """Parse ``source`` into a :class:`ParsedDocument` of tokenized slides."""
    md = MarkdownIt("commonmark").use(dollarmath_plugin)
    tree = SyntaxTreeNode(md.parse(source))

    doc = ParsedDocument()
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

        current.blocks.append(_fold_block(node))

    return doc


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
    raise _unsupported(node.type)


def _fold_list_item(node: SyntaxTreeNode) -> ListItem:
    return ListItem([_fold_block(c) for c in node.children])


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
