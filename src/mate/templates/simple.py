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
    def __init__(self) -> None:
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

        super().__init__()

        self.layout.get("title").set_anchor_default("center")

    def add_title(self) -> Group:
        slide = self.current_slide
        title_region = self.layout.get("title")

        members = Group()

        if slide.title is not None:
            title = Text(
                slide.title.upper(),
                font=config.get("title.font"),
                fontsize=config.get("title.fontsize"),
                fill_color=config.get("title.color"),
                weight=config.get("title.fontweight"),
                letter_spacing=0.15,
            )
            title_region.add(title)
            members.add(title)

        if slide.subtitle is not None:
            subtitle = Text(
                slide.subtitle,
                font=config.get("subtitle.font"),
                fontsize=config.get("subtitle.fontsize"),
                fill_color=config.get("subtitle.color"),
                weight=config.get("subtitle.fontweight"),
            )
            title_region.add(subtitle)
            members.add(subtitle)

        slide.add(members)
        return members
