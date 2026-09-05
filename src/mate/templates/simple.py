"""Simple template.

Fonts: Lato.
Defines: ``add_title``.
"""

from __future__ import annotations

from ..config import config
from ..core.template import PresentationTemplateBase
from ..elements.group import Group
from ..elements.text import Text


class PresentationTemplate(PresentationTemplateBase):
    def setup(self) -> None:
        font = "Lato"
        config.set_multiple(
            {
                "text.font": font,
                "title.font": font,
                "subtitle.font": font,
                "cover.title.font": font,
                "cover.author.font": font,
                "title.fontweight": 700,
                "subtitle.fontweight": 300,
                "subtitle.color": "black",
                "list.bullet.symbols": ["square", "dash", "square_outline"],
                "footer.show": False,
            }
        )

    def setup_layout(self) -> None:
        self.layout.get("title").set_anchor_default("center")

    def add_title(self) -> Group:
        """Build the current slide's title: uppercase, with wide tracking."""
        slide = self.current_slide
        title_region = self.layout.get("title")

        members = Group()

        if slide.title is not None:
            title_width = config.get("title.max_width")
            if title_width is None:
                title_width = title_region.width
            title = Text(
                slide.title.upper(),
                font=config.get("title.font"),
                fontsize=config.get("title.fontsize"),
                weight=config.get("title.fontweight"),
                fill_color=config.get("title.color"),
                letter_spacing=0.15,
                max_width=title_width,
            )
            title_region.add(title)
            members.add(title)

        if slide.subtitle is not None:
            subtitle_width = config.get("subtitle.max_width")
            if subtitle_width is None:
                subtitle_width = title_region.width
            subtitle = Text(
                slide.subtitle,
                font=config.get("subtitle.font"),
                fontsize=config.get("subtitle.fontsize"),
                weight=config.get("subtitle.fontweight"),
                fill_color=config.get("subtitle.color"),
                max_width=subtitle_width,
            )
            title_region.add(subtitle)
            members.add(subtitle)

        slide.add(members)
        return members
