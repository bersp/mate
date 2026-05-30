from __future__ import annotations

from ..config import config
from ..elements.text import DEFAULT_FONT, Text
from ..composition.layout import Layout, Region
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

        layout.add("content", Region.create_inner(
            left=left, right=right, top=title, bottom=footer,
            anchor=config.get("box.content.anchor")))

        layout.add("full", Region.create_full(anchor="top-center"))

        m = config.get("box.full_with_margins.margins")
        layout.add("full_with_margins", Region.create_full(anchor="top-center").adjust_borders(
            left=-m, right=-m, top=-m, bottom=-m))

        layout.set_active("content")
        return layout

    def background(self) -> Element | None:
        """Return the slide background element, or ``None`` for no background."""
        return None

    def add_title(self) -> None:
        """Build the current slide's title and subtitle strings into ``Text`` elements, adding them to the slide and title region."""
        slide = self.current_slide
        for text in (slide.title, slide.subtitle):
            if text is None:
                continue
            el = Text(text, font=self.font)
            slide.add(el)
            self.layout.title.add(el)
