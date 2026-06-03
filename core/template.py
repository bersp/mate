from __future__ import annotations

from itertools import cycle

from ..config import config
from ..elements.group import Group
from ..elements.text import Text
from ..elements.spacing import VSpace
from ..composition.layout import Layout, Region
from ..composition.utils import layout_to_group
from .element import Element


class PresentationTemplate:
    """Base template for a presentation."""

    def __init__(self) -> None:
        self.text_font: str = config.get("text.font")
        self.text_fontsize: float = config.get("text.fontsize")
        self.text_color: str = config.get("text.color")
        self.title_font: str = config.get("title.font")
        self.title_fontsize: float = config.get("title.fontsize")
        self.title_color: str = config.get("title.color")
        self.subtitle_font: str = config.get("subtitle.font")
        self.subtitle_fontsize: float = config.get("subtitle.fontsize")
        self.subtitle_color: str = config.get("subtitle.color")
        self.math_font: str = config.get("math.font")
        self.math_fontsize: float = config.get("math.fontsize")
        self.math_color: str = config.get("math.color")
        self.layout: Layout = self.build_layout()

    def build_layout(self) -> Layout:
        """Return the presentation's region layout."""
        layout = Layout()

        title = layout.add("title", Region.create_top(1.7, anchor="top-center"))
        footer = layout.add("footer", Region.create_bottom(0.5, anchor="bottom-center"))
        left = layout.add("left_margin", Region.create_left(0.7, anchor="center"))
        right = layout.add("right_margin", Region.create_right(0.7, anchor="center"))

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

        layout.set_active("content")
        return layout

    def background(self) -> Element | None:
        """Return the slide background element, or ``None`` for no background."""
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

    def add_title(self) -> Group:
        """Build the current slide's title and subtitle into a ``Group``.

        The group is added to the slide; its members are also added to the
        title region so :meth:`Region.arrange` stacks them. Returns the
        group, which is empty when both title and subtitle are unset.
        """
        slide = self.current_slide
        title_region = self.layout.get("title")

        title_region.add(VSpace(0.5))

        members: list[Text] = []

        if slide.title is not None:
            title = Text(
                slide.title,
                font=self.title_font,
                fontsize=self.title_fontsize,
                fill_color=self.title_color,
            )
            title_region.add(title)
            members.append(title)

        if slide.subtitle is not None:
            subtitle = Text(
                slide.subtitle,
                font=self.subtitle_font,
                fontsize=self.subtitle_fontsize,
                fill_color=self.subtitle_color,
            )
            title_region.add(subtitle)
            members.append(subtitle)

        group = Group(members)
        slide.add(group)
        return group

    def add_text(self, text: str, region: str = "active", **text_kwargs) -> Text:
        """Create a wrapped :class:`Text` and add it to a region and the slide.

        ``region`` is the target region name. The text wraps at the region's
        width unless ``max_width`` is passed in ``text_kwargs``; the remaining
        keyword arguments are forwarded to :class:`Text`.
        """
        target_region = self.layout.get(region)
        text_kwargs.setdefault("max_width", target_region.width)
        el = Text(text, **text_kwargs)
        self.current_slide.add(el)
        target_region.add(el)
        return el
