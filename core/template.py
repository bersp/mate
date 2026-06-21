from __future__ import annotations

from itertools import cycle

from ..composition.layout import Layout, Region
from ..composition.utils import layout_to_group
from ..config import config
from ..elements.group import Group
from ..elements.image import Image
from ..elements.shapes import Line
from ..elements.spacing import VSpace
from ..elements.text import Text
from ..parser.ir import (
    BulletList,
    Heading,
    MathBlock,
    MethodCall,
    OrderedList,
    Paragraph,
    ParsedSlide,
)
from ..parser.serialize import inlines_to_markdown
from .vec import Vec
from .element import Element, HAlign


class PresentationTemplate:
    """Base template for a presentation."""

    # --- Internals ----------------------------------------------------------
    def __init__(self) -> None:
        frontmatter = getattr(self, "_frontmatter", None)
        if frontmatter is not None:
            config.apply_overrides(frontmatter.config)
            config.colors.set_multiple(frontmatter.colors)
        self.auto_add_footer: bool = config.get("template.auto_footer")
        self.footer_show_total: bool = config.get("footer.show_total")
        self.layout: Layout = self.build_layout()

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
            Region.create_full(anchor="top-center").adjust_borders(
                left=-m, right=-m, top=-m, bottom=-m
            ),
        )

        layout.set_default_active("content")
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
    ) -> dict[str, Region]:
        """Split a region into a grid and register each cell in the layout.

        ``region`` is the region to split. The ``template`` array, gaps, and
        ratios are forwarded to :meth:`Region.grid`: cells sharing a label
        merge into one sub-region. Each sub-region is attached to the layout
        under its label, so it can later be reached by name (including as the
        ``"active"`` target via :meth:`Layout.set_active`). Returns the
        ``label -> Region`` mapping.
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
            self.layout.add(label, sub)
        return subregions

    def set_active_region(self, name: str) -> Region:
        """Make ``name`` the layout's active region and return it."""
        return self.layout.set_active(name)

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
        if parsed.title is not None:
            slide.title = inlines_to_markdown(parsed.title)
        if parsed.subtitle is not None:
            slide.subtitle = inlines_to_markdown(parsed.subtitle)
        if parsed.title is not None or parsed.subtitle is not None:
            self.add_title()

        for block in parsed.blocks:
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

    def run_method_call(self, name: str, args: str) -> None:
        """Invoke the method ``name`` with ``args`` evaluated as Python.

        ``args`` is the verbatim argument text of a ``> name : args``
        blockquote, spliced into a ``name(args)`` call and evaluated with the
        bound method in scope, so it may carry positional and keyword
        arguments (``grid``, ``add_vspace``, ...). An unknown ``name`` raises
        :class:`AttributeError`.
        """
        method = getattr(self, name)
        eval(f"_method({args})", {"_method": method})

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
        """Render a bullet list."""
        raise NotImplementedError("add_bullet_list is not implemented")

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

    def add_footer(self, show_total: bool = False) -> Group:
        """Build the current slide's footer: a separator line and a page number.

        The page number sits at the footer's right edge. ``show_total``
        appends ``/<total>`` from the presentation's ``total_slides``;
        asking for it without a declared total raises :class:`ValueError`.
        """
        footer_region = self.layout.get("footer")
        number = self.slides.index(self.current_slide) + 1

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
        align: HAlign | None = None,
        **text_kwargs,
    ) -> Text:
        """Create a wrapped :class:`Text` and add it to a region and the slide.

        ``region`` is the target region name. The text wraps at the region's
        width unless ``max_width`` is passed in ``text_kwargs``; the remaining
        keyword arguments are forwarded to :class:`Text`. ``text_align`` (line
        alignment within the box) defaults to ``align``, so a single ``align``
        both places the box in the region and aligns its lines; pass
        ``text_align`` explicitly to decouple the two. ``line_gap`` defaults to
        the region's ``arrange_gap``, so a wrapped paragraph's inter-line gap
        matches the gap between elements stacked in the region.
        """
        target_region = self.layout.get(region)
        text_kwargs.setdefault("max_width", target_region.width)
        text_kwargs.setdefault("text_align", align)
        text_kwargs.setdefault("line_gap", target_region.arrange_gap)
        el = Text(text, align=align, **text_kwargs)
        self.current_slide.add(el)
        target_region.add(el)
        return el

    def add_vspace(self, height: float, region: str = "active") -> VSpace:
        """Add a vertical spacer of ``height`` cm to a region's stack.

        ``region`` is the target region name. The spacer carries its own
        height into :meth:`Region.arrange`, opening that much vertical space
        between the elements stacked around it.
        """
        target_region = self.layout.get(region)
        spacer = VSpace(height)
        target_region.add(spacer)
        return spacer

    def add_image(
        self,
        path: str,
        region: str = "active",
        *,
        width: float | str | None = None,
        height: float | str | None = None,
        **image_kwargs,
    ) -> Image:
        """Create an :class:`Image` and add it to a region and the slide.

        ``region`` is the target region name. ``width`` and ``height`` are
        each either a length in cm or a ``"<n>%"`` string read as that
        percentage of the region's width/height. Setting one alone lets the
        other follow the file's aspect ratio; setting neither sizes the
        image's longer side to the full matching region extent. ``align``
        defaults to the ``image.align`` config value; the remaining keyword
        arguments are forwarded to :class:`Image`.
        """
        target_region = self.layout.get(region)
        width_cm = self._resolve_image_extent(width, target_region.width)
        height_cm = self._resolve_image_extent(height, target_region.height)
        if width_cm is None and height_cm is None:
            natural = Image(path)
            if natural.get_width() >= natural.get_height():
                width_cm = target_region.width
            else:
                height_cm = target_region.height
        image_kwargs.setdefault("align", config.get("image.align"))
        el = Image(path, width=width_cm, height=height_cm, **image_kwargs)
        self.current_slide.add(el)
        target_region.add(el)
        return el

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
