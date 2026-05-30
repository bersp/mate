from __future__ import annotations

from itertools import cycle

from ..config import config
from ..elements.group import Group
from ..elements.text import DEFAULT_FONT, Text
from ..composition.layout import Layout, Region
from ..composition.utils import layout_to_group
from .element import Element


class PresentationTemplate:
    """Base template for a presentation."""

    font: str = DEFAULT_FONT

    def __init__(self) -> None:
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
                anchor=config.get("box.content.anchor"),
            ),
        )

        layout.add("full", Region.create_full(anchor="top-center"))

        m = config.get("box.full_with_margins.margins")
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

    def add_title(self) -> None:
        """Build the current slide's title and subtitle into ``Text`` elements.

        Adds them to the slide and to the title region.
        """
        slide = self.current_slide
        for text in (slide.title, slide.subtitle):
            if text is None:
                continue
            el = Text(text, font=self.font)
            slide.add(el)
            self.layout.get("title").add(el)
