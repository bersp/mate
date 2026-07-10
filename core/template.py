from __future__ import annotations

from itertools import cycle

from ..composition.arrange import arrange
from ..composition.layout import Layout, Region
from ..composition.utils import layout_to_group
from ..config import config
from ..core.drawable import Drawable
from ..elements.group import Group
from ..elements.image import Image
from ..elements.shapes import Circle, Ellipse, Line, Rectangle
from ..elements.spacing import VSpace
from ..elements.text import Text
from ..parser.ir import (
    Block,
    BulletList,
    FencedBlock,
    Heading,
    ListItem,
    MathBlock,
    MethodCall,
    OrderedList,
    Paragraph,
    ParsedSlide,
    PythonBlock,
)
from ..parser.serialize import inlines_to_markdown
from .gradient import Gradient
from .registry import IDKey, id_registry
from .topic import Topic
from .vec import Vec
from .element import Anchor, Element, HAlign, anchor_offsets, measure_all

# Names exposed to authored Python expressions (blockquote method-call
# arguments and fenced-block property text).
_AUTHOR_GLOBALS = {"Gradient": Gradient}


def _union_bbox(
    elements: list[Element],
) -> tuple[float, float, float, float]:
    """Return the centre-based ``(x, y, w, h)`` union bbox of ``elements``."""
    boxes = [el.get_bbox() for el in elements]
    left = min(cx - w / 2 for cx, _, w, _ in boxes)
    right = max(cx + w / 2 for cx, _, w, _ in boxes)
    bottom = min(cy - h / 2 for _, cy, _, h in boxes)
    top = max(cy + h / 2 for _, cy, _, h in boxes)
    return ((left + right) / 2, (bottom + top) / 2, right - left, top - bottom)


class PresentationTemplateBase:
    """Base for presentation templates: the layout, content methods, and reveal
    machinery a concrete ``PresentationTemplate`` subclass builds on."""

    # --- Internals ----------------------------------------------------------
    def __init__(self) -> None:
        frontmatter = getattr(self, "_frontmatter", None)
        if frontmatter is not None:
            config.apply_overrides(frontmatter.config)
            config.colors.set_multiple(frontmatter.colors)
        self.auto_add_footer: bool = config.get("footer.show")
        self.footer_show_total: bool = config.get("footer.show_total")
        self.layout: Layout = self.build_layout()
        self._cap_height_cache: dict[tuple, float] = {}
        self._content_indent: float = 0.0
        self._fragment_region: str | None = None
        self._region_override: Region | None = None
        self._overwrites: list[tuple[Group, list[Element], str, int]] = []
        self._alternates: list[tuple[VSpace, list[list[Element]], float]] = []
        self._modifies: list[tuple[list[Element], dict, int]] = []
        self._python_namespace: dict | None = None

    def build_layout(self) -> Layout:
        """Return the presentation's region layout."""
        layout = Layout()

        left_margin = 0.7
        right_margin = 0.7

        title = layout.add(
            "title",
            Region.create_top(2, anchor="center-left").adjust_borders(
                left=-left_margin, right=-right_margin
            ),
        )
        footer = layout.add(
            "footer",
            Region.create_bottom(0.5, anchor="bottom-center").adjust_borders(
                left=-left_margin, right=-right_margin
            ),
        )
        left = layout.add(
            "left_margin", Region.create_left(left_margin, anchor="center")
        )
        right = layout.add(
            "right_margin", Region.create_right(right_margin, anchor="center")
        )

        layout.add(
            "content",
            Region.create_inner(
                left=left,
                right=right,
                top=title,
                bottom=footer,
                anchor=config.get("region.content.anchor"),
                arrange_gap=config.get("region.content.arrange_gap"),
            ),
        )

        layout.add("full", Region.create_full(anchor="top-center"))

        m = config.get("region.full_with_margins.margins")
        layout.add(
            "full_with_margins",
            Region.create_full(anchor="center").adjust_borders(
                left=-m, right=-m, top=-m, bottom=-m
            ),
        )

        layout.set_default_active(config.get("region.default"))
        return layout

    def create_grid(
        self,
        template: list[list[str]],
        region: str = "active",
        *,
        hgap: float = 0.0,
        vgap: float = 0.0,
        width_ratios: list[float] | None = None,
        height_ratios: list[float] | None = None,
        anchors: dict[str, Anchor] | None = None,
    ) -> dict[str, Region]:
        """Split a region into a grid and register each cell in the layout.

        ``region`` is the region to split. The ``template`` array, gaps, and
        ratios are forwarded to :meth:`Region.grid`: cells sharing a label
        merge into one sub-region. Each sub-region is attached to the layout
        under its label, so it can later be reached by name (including as the
        ``"active"`` target via :meth:`Layout.set_active`). ``anchors`` maps a
        cell label to the anchor its content sits at, so e.g. a cell holding a
        lone image can be centered. Returns the ``label -> Region`` mapping.
        """
        target_region = self.layout.get(region)
        subregions = target_region.grid(
            template,
            hgap=hgap,
            vgap=vgap,
            width_ratios=width_ratios,
            height_ratios=height_ratios,
        )
        for label, sub in subregions.items():
            if anchors is not None and label in anchors:
                sub.set_anchor(anchors[label])
            self.layout.add(label, sub)
        return subregions

    def set_active_region(self, name: str, anchor: Anchor | None = None) -> Region:
        """Make ``name`` the layout's active region and return it.

        ``anchor``, when given, overrides the region's anchor; the override is
        undone when the next slide opens.
        """
        region = self.layout.set_active(name)
        if anchor is not None:
            region.set_anchor(anchor)
        return region

    def background(self) -> Element | None:
        """Return the slide background element, or ``None`` for no background.

        A subclass overrides this to return a positioned ``Element`` (e.g. a
        full-slide ``Rectangle``). It is added first on every slide, so it
        renders behind all other content and appears on every page.
        """
        return None

    def draw_layout(
        self, regions: list[str] | None = None, stroke_width: float = 0.03
    ) -> Group:
        """Add a debug overlay of the layout: one outline per region, labelled.

        ``regions`` selects which to draw by name; ``None`` draws every region.
        """
        colors = ("red", "orange", "yellow", "green", "aqua", "blue", "purple")
        group = layout_to_group(
            self.layout, regions, fill_opacity=0, stroke_width=stroke_width
        )
        for sub_group, color in zip(group.children, cycle(colors)):
            rect, label = sub_group.children
            rect.set_stroke_color(color)
            label.set_fill_color(color)
        self.current_slide.add(group)
        return group

    def add_parsed_slide(self, parsed: ParsedSlide) -> None:
        """Render a :class:`~mate.parser.ir.ParsedSlide` onto the current slide.

        Serializes the slide's title/subtitle and each body block back to
        Markdown text and dispatches every block to the matching ``add_*``
        method. A block type without a handler raises
        :class:`NotImplementedError`, so a subclass can supply its own.
        """
        slide = self.current_slide
        slide.topic = parsed.topic
        if parsed.title is not None:
            slide.title = inlines_to_markdown(parsed.title)
        if parsed.subtitle is not None:
            slide.subtitle = inlines_to_markdown(parsed.subtitle)
        if parsed.title is not None or parsed.subtitle is not None:
            self.add_title()

        for block in parsed.blocks:
            self._dispatch_block(block)

    def _dispatch_block(self, block: Block) -> None:
        """Render one parsed block via its matching ``add_*`` handler.

        Drives both top-level slide content and the blocks of a list item, so
        a list item carries the full block vocabulary (paragraphs, math, method
        calls, nested lists).
        """
        match block:
            case Paragraph(inlines):
                self.add_paragraph(inlines_to_markdown(inlines))
            case Heading(level, inlines):
                self.add_heading(level, inlines_to_markdown(inlines))
            case MathBlock(raw):
                self.add_math_block(raw)
            case BulletList():
                self.add_bullet_list(block)
            case OrderedList():
                self.add_ordered_list(block)
            case MethodCall(name, args):
                self.run_method_call(name, args)
            case FencedBlock(name, args, blocks):
                getattr(self, f"add_{name}")(blocks, args)
            case PythonBlock(source):
                self._run_python(source)

    def add_fragment(self, blocks: list[Block], args: str) -> None:
        """Render a ``markdown fragment`` body, pushing its properties onto it.

        ``args`` is the fence's verbatim property text. ``region``, ``floating``,
        ``pos`` and ``anchor`` set placement; every other property is applied to
        each root the body produced by calling its ``set_<prop>`` method (or bare
        ``<prop>``) when one exists, and ignored otherwise.

        ``region`` is an ambient region honored by every content method while the
        body renders. With ``floating=True`` the produced roots are not added to
        the region: they keep their own reveal steps and are stacked with their
        ``anchor`` point at ``pos`` (the region's ``anchor`` point when ``pos`` is
        omitted), with ``region`` supplying the wrap width for the body.
        """
        props = eval(f"dict({args})", {"dict": dict, **_AUTHOR_GLOBALS})
        region = props.pop("region", None)
        floating = props.pop("floating", False)
        pos = props.pop("pos", None)
        anchor = props.pop("anchor", None)

        before = {id(el) for el in self._root_elements()}
        if floating:
            geometry = self._resolve_region(region or "active")
            cluster_anchor = anchor or geometry.anchor
            temp = Region(
                geometry.center, geometry.width, geometry.height, anchor=cluster_anchor
            )
            previous_override = self._region_override
            self._region_override = temp
            for block in blocks:
                self._dispatch_block(block)
            self._region_override = previous_override
        else:
            previous_region = self._fragment_region
            if region is not None:
                self._fragment_region = region
            for block in blocks:
                self._dispatch_block(block)
            self._fragment_region = previous_region

        new_roots = [el for el in self._root_elements() if id(el) not in before]
        for el in new_roots:
            for prop, value in props.items():
                method = el.resolve_prop(prop)
                if callable(method):
                    method(value)

        if floating:
            place = Vec(pos) if pos is not None else temp.get_anchor_point(cluster_anchor)
            arrange(temp.elements, place, cluster_anchor, gap=temp.arrange_gap)

    def _root_elements(self) -> list[Element]:
        """Return every root element added to the current slide so far."""
        return [el for step in self.current_slide.steps for el in step]

    def add_overwrite(self, blocks: list[Block], args: str) -> None:
        """Render a body inside the bbox of every element carrying an id.

        ``args`` is ``<id>[, anchor=...]``. The body is laid out at the original
        region's width and anchored within the union bbox of the id's elements
        (computed after arrange), which it visually replaces from its reveal step
        onward without moving the surrounding content. ``anchor`` defaults to the
        original region's anchor and sets both the body's stacking and placement.
        """
        target_id, anchor = eval(
            f"_f({args})", {"_f": lambda id, anchor=None: (id, anchor)}
        )
        try:
            targets = id_registry.get(target_id)
        except KeyError:
            raise ValueError(f"overwrite: no element with id {target_id!r}") from None
        try:
            region = self._region_of(targets[0])
        except ValueError:
            raise ValueError(
                f"overwrite: id {target_id!r} is not a top-level element; "
                "overwrite targets a whole block (e.g. one tagged with "
                "'markdown fragment : id=...'), not an inline span"
            ) from None
        anchor = anchor or region.anchor

        temp = Region(region.center, region.width, region.height, anchor=anchor)
        before = {id(el) for el in self._root_elements()}
        self._region_override = temp
        for block in blocks:
            self._dispatch_block(block)
        self._region_override = None

        body = [el for el in self._root_elements() if id(el) not in before]
        for el in body:
            self._remove_root(el)
        temp.arrange()
        group = Group(children=body)
        self.current_slide.add(group)
        step = len(self.current_slide.steps) - 1
        self._overwrites.append((group, targets, anchor, step))

    def add_alternate(self, blocks: list[Block], args: str) -> None:
        """Render a ``markdown alternate`` body as a sequence of variants in one slot.

        ``> alt`` lines split the body into variants; each variant replaces the
        previous in place when it appears, so only one is visible per reveal
        step. A ``> pause`` inside a variant reveals its content cumulatively
        before the next variant takes over. The slot reserves the height of the
        tallest variant, so content below the block never moves between pages.
        ``args`` may carry ``region=<name>`` to target a region other than the
        active one.
        """
        props = eval(f"dict({args})", {"dict": dict, **_AUTHOR_GLOBALS})
        target = self._resolve_region(props.pop("region", "active"))

        variants: list[list[Block]] = [[]]
        for block in blocks:
            if isinstance(block, MethodCall) and block.name == "alt":
                variants.append([])
            else:
                variants[-1].append(block)

        variant_elements: list[list[Element]] = []
        heights: list[float] = []
        for i, variant in enumerate(variants):
            before = {id(el) for el in self._root_elements()}
            temp = Region(
                target.center, target.width, target.height, anchor=target.anchor
            )
            self._region_override = temp
            for block in variant:
                self._dispatch_block(block)
            self._region_override = None
            temp.arrange()

            els = [el for el in self._root_elements() if id(el) not in before]
            variant_elements.append(els)
            heights.append(_union_bbox(els)[3])
            if i < len(variants) - 1:
                self.pause()
                step = len(self.current_slide.steps) - 1
                for el in els:
                    self.current_slide.replaced.append((step, el))

        # A VSpace is a spacer, so arrange drops the gap on both sides of it.
        # Pad the reserved height with the region gap (above only when content
        # precedes the block) and offset the variants down by it, so the slot
        # flows like a normal block between its neighbours.
        gap = target.arrange_gap
        gap_above = gap if target.elements else 0.0
        vspace = VSpace(max(heights) + gap_above + gap)
        target.add(vspace)
        self._alternates.append((vspace, variant_elements, gap_above))

    def _region_of(self, el: Element) -> Region:
        """Return the layout region whose stack contains ``el``."""
        for region in self.layout.regions.values():
            if el in region.elements:
                return region
        raise ValueError(f"{el!r} is not a top-level element of any region")

    def _remove_root(self, el: Element) -> None:
        """Remove ``el`` from whichever reveal step of the current slide holds it."""
        for step in self.current_slide.steps:
            if el in step:
                step.remove(el)
                return

    def _resolve_overwrites(self) -> None:
        """Place each overwrite body in its target bbox and hide what it replaces.

        Runs after regions are arranged, so the targets' positions are baked.
        """
        for group, targets, anchor, step in self._overwrites:
            cx, cy, w, h = _union_bbox(targets)
            h_mul, v_mul = anchor_offsets(anchor)
            point = Vec(cx + (h_mul - 0.5) * w, cy + (v_mul - 0.5) * h)
            group.set_anchor(anchor)
            group.move_to(point)
            for target in targets:
                self.current_slide.replaced.append((step, target))
        self._overwrites = []

    def _resolve_alternates(self) -> None:
        """Stack each alternate's variants onto its reserved slot.

        Runs after regions are arranged, so the slot spacer's position is baked.
        Every variant is top-aligned to the slot, overlaying the others so they
        share one spot across reveal steps.
        """
        for vspace, variants, gap_above in self._alternates:
            _, scy, _, sh = vspace.get_bbox()
            slot_top = scy + sh / 2 - gap_above
            for els in variants:
                _, cy, _, h = _union_bbox(els)
                delta_y = slot_top - (cy + h / 2)
                for el in els:
                    el.shift((0, delta_y))
        self._alternates = []

    def _resolve_region(self, region: str) -> Region:
        """Resolve a region name, honoring an active region override.

        An ``overwrite`` body renders into a temporary region override; otherwise
        a call leaving ``region`` at its ``"active"`` default lands in the
        fragment region while a ``markdown fragment`` body renders. An explicit
        region name wins over the fragment region.
        """
        if self._region_override is not None:
            return self._region_override
        if region == "active" and self._fragment_region is not None:
            region = self._fragment_region
        return self.layout.get(region)

    def _run_python(self, source: str) -> None:
        """Run a ``python mate`` block's ``source`` in the deck's namespace.

        The namespace exposes the public ``mate`` API plus ``self`` (this
        presentation) and persists across blocks; definitions and imports from
        one block are visible to later ones. A syntax error or a runtime
        exception raises naming the block.
        """
        try:
            code = compile(source, "<python mate block>", "exec")
        except SyntaxError as exc:
            raise ValueError(f"syntax error in a 'python mate' block: {exc}") from None
        exec(code, self._python_ns())

    def _python_ns(self) -> dict:
        """Return the shared ``python mate`` namespace, built once."""
        if self._python_namespace is None:
            import mate

            self._python_namespace = {name: getattr(mate, name) for name in mate.__all__}
            self._python_namespace["self"] = self
        return self._python_namespace

    def run_method_call(self, name: str, args: str) -> None:
        """Invoke the method ``name`` with ``args`` evaluated as Python.

        ``args`` is the verbatim argument text of a ``> name : args``
        blockquote, spliced into a ``name(args)`` call and evaluated with the
        bound method in scope, so it may carry positional and keyword
        arguments (``grid``, ``add_vspace``, ...). ``> alt`` is a variant
        separator reserved for ``markdown alternate`` bodies; reaching it here
        means it was used outside one. An unknown ``name`` raises
        :class:`ValueError` naming the offending blockquote method.
        """
        if name == "alt":
            raise ValueError(
                "'> alt' is only valid as a variant separator inside a "
                "'markdown alternate' block"
            )
        method = getattr(self, name, None)
        if method is None:
            raise ValueError(f"unknown blockquote method '> {name.replace('_', ' ')}'")
        eval(f"_method({args})", {"_method": method, **_AUTHOR_GLOBALS})

    # --- Content ------------------------------------------------------------
    def add_paragraph(self, text: str) -> Text:
        """Render a paragraph of Markdown ``text`` into the active region."""
        return self.add_text(text)

    def add_math_block(self, raw: str) -> Text:
        """Render a display equation from its Markdown math body ``raw``."""
        return self.add_text(
            f"$$ {raw} $$",
            align="center",
            font=config.get("math.font"),
            fontsize=config.get("math.fontsize"),
            fill_color=config.get("math.color"),
        )

    def add_heading(self, level: int, text: str) -> None:
        """Render an in-body heading of the given ``level``."""
        raise NotImplementedError(
            f"add_heading is not implemented (level {level} heading: {text!r})"
        )

    def add_bullet_list(self, block: BulletList) -> None:
        """Render a bullet list, one item per :meth:`_add_list_item` call."""
        for item in block.items:
            self._add_list_item(item)

    def _add_list_item(
        self,
        item: ListItem,
        *,
        symbol: str | Drawable | None = None,
        spacing: float | None = None,
    ) -> None:
        """Render every block of one list item.

        The first block carries the bullet (:meth:`add_bullet_item`); the rest
        are dispatched as ordinary content while the ambient content indent is
        raised to the item's text column, so continuation paragraphs, images,
        method calls (``> pause``, ``> add image``) and nested sub-lists all land
        under the item text and reveal in document order.
        """
        symbol = config.get("list.bullet") if symbol is None else symbol
        spacing = config.get("list.bullet_gap") if spacing is None else spacing

        first, *rest = item.blocks
        self.add_bullet_item(
            inlines_to_markdown(first.inlines), symbol=symbol, spacing=spacing
        )

        _, bullet_width = self._make_bullet(symbol, config.get("text.color"))
        outer_indent = self._content_indent
        self._content_indent = outer_indent + bullet_width + spacing
        for block in rest:
            self._dispatch_block(block)
        self._content_indent = outer_indent

    def add_bullet_item(
        self,
        text: str,
        *,
        symbol: str | Drawable | None = None,
        spacing: float | None = None,
        region: str = "active",
        color: str | None = None,
        **text_kwargs,
    ) -> Group:
        """Add one bullet item (symbol plus ``text``) to a region and the slide.

        ``symbol`` is a built-in name (``"square"``, ``"circle"``, ``"dash"``) or
        a :class:`~mate.core.drawable.Drawable`; its longest dimension is scaled
        to the cap height of ``"A"`` in the body font. ``spacing`` is the gap
        between symbol and text. The text wraps within the region's remaining
        width and hangs-indents under itself; the symbol is centered on the
        first text line. Remaining keyword arguments are forwarded to
        :class:`Text`. The item is a single :class:`Group`, so the region's
        :meth:`~mate.composition.layout.Region.arrange` stacks whole items with
        its own gap, independent of blank lines in the source.
        """
        target_region = self._resolve_region(region)
        symbol = config.get("list.bullet") if symbol is None else symbol
        spacing = config.get("list.bullet_gap") if spacing is None else spacing
        color = config.get("text.color") if color is None else color

        indent = self._content_indent
        cap_height = self._cap_height()
        bullet, bullet_width = self._make_bullet(symbol, color)

        text_x = bullet_width + spacing
        text_kwargs.setdefault("max_width", target_region.width - indent - text_x)
        text_kwargs.setdefault("line_gap", target_region.arrange_gap)
        body = Text(text, pos=(text_x, 0), anchor="top-left", **text_kwargs)

        bullet.set_anchor("center")
        bullet.move_to((bullet_width / 2, -cap_height / 2))

        item = Group()
        item.add(bullet)
        item.add(body)
        item.indent = indent
        self.current_slide.add(item)
        target_region.add(item)
        return item

    def _make_bullet(self, symbol: str | Drawable, color: str) -> tuple[Drawable, float]:
        """Return a filled bullet sized to the body cap height and its width."""
        size = self._cap_height() * config.get("list.bullet_scale")
        bullet = self._make_bullet_symbol(symbol, size, color)
        return bullet, bullet.get_width()

    def _cap_height(self) -> float:
        """Return the height of ``"A"`` measured in the current body font."""
        key = (
            config.get("text.font"),
            config.get("text.fontsize"),
            config.get("text.fontweight"),
        )
        height = self._cap_height_cache.get(key)
        if height is None:
            probe = Text("A", font=key[0], fontsize=key[1], weight=key[2])
            measure_all([probe])
            height = probe.get_height()
            self._cap_height_cache[key] = height
        return height

    def _make_bullet_symbol(
        self, symbol: str | Drawable, size: float, color: str
    ) -> Drawable:
        """Build a filled bullet whose longest dimension equals ``size``.

        ``symbol`` is a built-in name or a :class:`Drawable` (scaled in place on
        a copy so the caller's instance is untouched).
        """
        match symbol:
            case "square":
                shape = Rectangle(size, size)
            case "circle":
                shape = Circle(size / 2)
            case "dash":
                shape = Rectangle(size, config.get("list.dash_thickness"))
            case Drawable():
                shape = self._scale_to_longest(symbol.copy(), size)
            case _:
                raise ValueError(
                    f"{symbol!r} is not a bullet symbol. "
                    'Use "square", "circle", "dash", or a Drawable.'
                )
        shape.set_fill_color(color)
        return shape

    @staticmethod
    def _scale_to_longest(shape: Drawable, size: float) -> Drawable:
        """Scale ``shape`` in place so its longest bbox dimension equals ``size``."""
        factor = size / max(shape.get_width(), shape.get_height())
        match shape:
            case Circle():
                shape.set_radius(shape.get_radius() * factor)
            case Rectangle() | Ellipse():
                shape.set_width(shape.get_width() * factor)
                shape.set_height(shape.get_height() * factor)
            case Line():
                shape.set_start(shape.get_start() * factor)
                shape.set_end(shape.get_end() * factor)
        return shape

    def add_ordered_list(self, block: OrderedList) -> None:
        """Render an ordered list."""
        raise NotImplementedError("add_ordered_list is not implemented")

    def add_title(self) -> Group:
        """Build the current slide's title."""
        slide = self.current_slide
        title_region = self.layout.get("title")

        members = Group()

        if slide.title is not None:
            title = Text(
                slide.title,
                font=config.get("title.font"),
                fontsize=config.get("title.fontsize"),
                weight=config.get("title.fontweight"),
                fill_color=config.get("title.color"),
            )
            title_region.add(title)
            members.add(title)

        if slide.subtitle is not None:
            subtitle = Text(
                slide.subtitle,
                font=config.get("subtitle.font"),
                fontsize=config.get("subtitle.fontsize"),
                weight=config.get("subtitle.fontweight"),
                fill_color=config.get("subtitle.color"),
            )
            title_region.add(subtitle)
            members.add(subtitle)

        slide.add(members)
        return members

    def begin_topic(self, topic: Topic) -> None:
        """Open a topic, fired at its first slide.

        Receives the whole :class:`Topic` and decides what to do with it. The
        default renders a cover slide only when the ``cover`` property is truthy
        (``> cover: True``): it pulls ``title`` (falling back to the topic name)
        and hands the remaining properties to :meth:`add_cover`. A template
        overrides this to act on any declared property (e.g. switch theme)
        before, instead of, or alongside the cover; it owns its own slide via
        :meth:`new_slide`/:meth:`end_slide`.
        """
        props = dict(topic.props)
        if not props.pop("cover", False):
            return
        title = props.pop("title", topic.name)
        self.new_slide(is_cover=True)
        self.add_cover(title, **props)
        self.end_slide()

    def add_cover(self, title: str, **props: str) -> Group:
        """Render a cover page from a ``title`` and generic topic properties.

        Stacks ``title`` and any of ``subtitle``, ``author`` and ``date`` found
        in ``props`` as text in the ``full_with_margins`` region; other
        properties are ignored. A template overrides this to change the layout.
        """
        region = self.layout.get("full_with_margins").set_anchor("center-left")
        members = Group()

        title_el = Text(
            title,
            font=config.get("title.font"),
            fontsize=config.get("title.fontsize"),
            weight=config.get("title.fontweight"),
            fill_color=config.get("title.color"),
            max_width=region.width,
        )
        region.add(title_el)
        members.add(title_el)

        meta = (("subtitle", "subtitle"), ("author", "text"), ("date", "text"))
        if any(props.get(key) is not None for key, _ in meta):
            region.add(VSpace(1))

        for key, style in meta:
            value = props.get(key)
            if value is None:
                continue
            line = Text(
                value,
                font=config.get(f"{style}.font"),
                fontsize=config.get(f"{style}.fontsize"),
                fill_color=config.get(f"{style}.color"),
            )
            region.add(line)
            members.add(line)

        self.current_slide.add(members)
        return members

    def add_footer(self, show_total: bool = False) -> Group:
        """Build the current slide's footer: a separator line and a page number.

        The page number sits at the footer's right edge. ``show_total``
        appends ``/<total>`` from the presentation's ``total_slides``;
        asking for it without a declared total raises :class:`ValueError`.
        """
        footer_region = self.layout.get("footer")
        idx = self.slides.index(self.current_slide)
        number = sum(1 for s in self.slides[: idx + 1] if not s.is_cover)

        if show_total and self.total_slides is None:
            raise ValueError(
                "add_footer(show_total=True) needs a declared total in the presentation"
            )
        label = f"{number}/{self.total_slides}" if show_total else str(number)

        members = Group()
        num_el = Text(
            label,
            font=config.get("text.font"),
            fontsize=config.get("text.fontsize"),
            fill_color=config.get("text.color"),
            pos=footer_region.get_anchor_point("top-right"),
            anchor="top-right",
        )
        members.add(num_el)

        self.current_slide.add(members)

        return members

    def add_text(
        self,
        text: str,
        region: str = "active",
        *,
        floating: bool = False,
        align: HAlign | None = None,
        **text_kwargs,
    ) -> Text:
        """Create a wrapped :class:`Text` and add it to a region and the slide.

        ``region`` is the target region name. The text wraps at the region's
        width unless ``max_width`` is passed in ``text_kwargs``; the remaining
        keyword arguments are forwarded to :class:`Text`. With no ``text_align``,
        the wrapped lines follow ``align`` (see :meth:`Text.get_text_align`), so a
        single ``align`` both places the box and aligns its lines; pass
        ``text_align`` to override only the lines. ``line_gap`` defaults to the
        region's ``arrange_gap``, so a wrapped paragraph's inter-line gap matches
        the gap between elements stacked in the region.

        With ``floating=True`` the text is not added to the region: the region's
        :meth:`~mate.composition.layout.Region.arrange` does not stack it and it
        keeps the ``pos``/``anchor`` passed in ``text_kwargs``.
        """
        target_region = self._resolve_region(region)
        indent = self._content_indent
        text_kwargs.setdefault("max_width", target_region.width - indent)
        text_kwargs.setdefault("line_gap", target_region.arrange_gap)
        el = Text(text, align=align, **text_kwargs)
        el.indent = indent
        self.current_slide.add(el)
        if not floating:
            target_region.add(el)
        return el

    def add_vspace(self, height: float, region: str = "active") -> VSpace:
        """Add a vertical spacer of ``height`` cm to a region's stack.

        ``region`` is the target region name. The spacer carries its own
        height into :meth:`Region.arrange`, opening that much vertical space
        between the elements stacked around it.
        """
        target_region = self._resolve_region(region)
        spacer = VSpace(height)
        target_region.add(spacer)
        return spacer

    def add_image(
        self,
        path: str,
        region: str = "active",
        *,
        floating: bool = False,
        width: float | str | None = None,
        height: float | str | None = None,
        **image_kwargs,
    ) -> Image:
        """Create an :class:`Image` and add it to a region and the slide.

        ``region`` is the target region name. ``width`` and ``height`` are
        each either a length in cm or a ``"<n>%"`` string read as that
        percentage of the region's width/height. Setting one alone lets the
        other follow the file's aspect ratio; setting neither scales the image
        as large as it fits inside the region, binding whichever extent the
        image's aspect ratio reaches first. ``align``
        defaults to the ``image.align`` config value; the remaining keyword
        arguments are forwarded to :class:`Image`.

        With ``floating=True`` the image is not added to the region: the region's
        :meth:`~mate.composition.layout.Region.arrange` does not stack it and it
        keeps the ``pos``/``anchor`` passed in ``image_kwargs``.
        """
        target_region = self._resolve_region(region)
        indent = self._content_indent
        available_width = target_region.width - indent
        width_cm = self._resolve_image_extent(width, available_width)
        height_cm = self._resolve_image_extent(height, target_region.height)
        if width_cm is None and height_cm is None:
            natural = Image(path)
            image_aspect = natural.get_width() / natural.get_height()
            region_aspect = available_width / target_region.height
            if image_aspect >= region_aspect:
                width_cm = available_width
            else:
                height_cm = target_region.height
        image_kwargs.setdefault("align", config.get("image.align"))
        el = Image(path, width=width_cm, height=height_cm, **image_kwargs)
        el.indent = indent
        self.current_slide.add(el)
        if not floating:
            target_region.add(el)
        return el

    def crop_image(
        self,
        id: IDKey,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 1.0,
        height: float = 1.0,
    ) -> None:
        """Crop every image registered under ``id`` to a sub-rectangle.

        ``(x, y, width, height)`` are fractions of the image; see
        :meth:`~mate.elements.image.Image.crop`. The crop applies from the
        reveal step of this call onward.
        """
        self.modify(id, crop=(x, y, width, height))

    def uncrop_image(self, id: IDKey) -> None:
        """Drop the crop from every image registered under ``id``.

        The whole image shows again from the reveal step of this call onward.
        """
        self.modify(id, crop=None)

    def modify(self, id: IDKey, **props) -> None:
        """Apply ``props`` to every element registered under ``id``.

        For each ``name=value`` pair, ``set_<name>(value)`` is called when the
        element defines it, otherwise ``<name>(value)``: ``color="red"`` calls
        ``set_color("red")`` and ``shift=(1, 0)`` calls ``shift((1, 0))``. A
        ``name`` matching neither raises :class:`ValueError`. The change applies
        from the reveal step of this call onward.
        """
        try:
            targets = id_registry.get(id)
        except KeyError:
            raise ValueError(f"modify: no element with id {id!r}") from None
        for el in targets:
            for name in props:
                if not callable(el.resolve_prop(name)):
                    raise ValueError(
                        f"modify: element with id {id!r} has no "
                        f"'set_{name}' or '{name}' method"
                    )
        step = len(self.current_slide.steps) - 1
        self._modifies.append((targets, props, step))

    def _resolve_modifies(self) -> None:
        """Apply the deferred ``modify`` calls.

        Runs after regions are arranged. Edits are grouped by the root element
        containing each target. For each reveal step that carries an edit, the
        root is cloned with every edit up to and including that step applied, the
        previous version is hidden from that step onward, and the clone is shown
        from it.
        """
        slide = self.current_slide

        # root id -> (root, [(step, members, props), ...]); ``members`` are the
        # tagged elements of one ``modify`` that descend from this root.
        buckets: dict[int, tuple[Element, list[tuple[int, list[Element], dict]]]] = {}
        for targets, props, step in self._modifies:
            members_by_root: dict[int, list[Element]] = {}
            for el in targets:
                root = el
                while root.parent is not None:
                    root = root.parent
                members_by_root.setdefault(id(root), []).append(el)
                buckets.setdefault(id(root), (root, []))
            for root_id, members in members_by_root.items():
                buckets[root_id][1].append((step, members, props))

        for root, edits in buckets.values():
            steps = sorted({edit[0] for edit in edits})
            previous = root
            clones: dict[int, Element] = {}
            for step in steps:
                mapping: dict[int, Element] = {}
                clone = root._copy(mapping)
                for edit_step, members, props in edits:
                    if edit_step > step:
                        continue
                    for el in members:
                        node = mapping[id(el)]
                        for name, value in props.items():
                            node.apply_prop(name, value)
                slide.replaced.append((step, previous))
                slide.steps[step].append(clone)
                clones[step] = clone
                previous = clone
            # A removal scheduled for the original (by an alternate or
            # overwrite) also drops the clone standing in for it at that step.
            for s, el in list(slide.replaced):
                if el is root and s not in clones:
                    active = [st for st in steps if st <= s]
                    if active:
                        slide.replaced.append((s, clones[active[-1]]))
        self._modifies = []

    @staticmethod
    def _resolve_image_extent(
        value: float | str | None, region_extent: float
    ) -> float | None:
        """Resolve an image dimension to cm.

        ``None`` stays ``None``; a number is taken as centimetres; a
        ``"<n>%"`` string is that percentage of ``region_extent``.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return float(value.rstrip("%")) / 100.0 * region_extent
        return value

    # --- Aliases ------------------------------------------------------------
    vspace = add_vspace
    grid = create_grid
    region = set_active_region
