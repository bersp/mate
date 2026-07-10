"""Flow template.

Colours: full palette + ``flow.*`` (backdrop, cover_title, cover_accent,
cover_author, streamline, streamline_dot).
Fonts: Lato and Playfair Display.
Footer: disabled by default.
Defines: ``background``, ``add_cover``, ``add_title``.
"""

from __future__ import annotations

import numpy as np

from ..composition.arrange import arrange
from ..config import config
from ..core.template import PresentationTemplateBase
from ..elements.group import Group
from ..elements.shapes import Circle, Curve, LineTo, MoveTo, Rectangle
from ..elements.text import Text


class PresentationTemplate(PresentationTemplateBase):
    palette = {
        "black": "#1f1828",
        "darker_gray": "#3a3150",
        "dark_gray": "#564d6e",
        "gray": "#a8a3bb",
        "white": "#f6f3fb",
        "red": "#b5557a",
        "orange": "#cc8a66",
        "yellow": "#cbb37a",
        "green": "#6e8f6a",
        "aqua": "#5f9aa8",
        "blue": "#7e6bb0",
        "purple": "#5b3a86",
        "flow.backdrop": "#34204a",
        "flow.cover_title": "#f3ecf8",
        "flow.cover_accent": "#c79fe6",
        "flow.cover_author": "#b89ed2",
        "flow.streamline": "#8a6bb0",
        "flow.streamline_dot": "#a87fce",
    }

    band_height = 2.6  # depth of the content-slide flow band

    def __init__(self) -> None:
        config.set("text.font", "Lato")
        config.set("text.fontsize", 9.0)

        config.set("title.font", "Playfair Display")
        config.set("title.fontweight", 600)
        config.set("title.fontsize", 16.0)

        config.set("subtitle.font", "Lato")
        config.set("subtitle.fontsize", 11.0)

        config.set("footer.show", False)

        config.colors.set_multiple(self.palette)

        super().__init__()

    def background(self) -> Group:
        W, H = config.slide_width, config.slide_height
        group = Group(anchor="top-left")

        if self.current_slide.is_cover:
            group.add(Rectangle(W, H, fill_color="flow.backdrop"))
            for el in self._flow_band(
                W, y_top=H / 2, y_bottom=-H / 2, n_lines=9, amp=1.2, seed=31,
                line_opacity=0.13, dot_opacity=0.5,
            ):
                group.add(el)
        else:
            bar_w = 0.2
            group.add(Rectangle(bar_w, H, pos=(-W / 2 + bar_w / 2, 0), fill_color="flow.backdrop"))
            for el in self._flow_band(
                W, y_top=-H / 2 + self.band_height, y_bottom=-H / 2, n_lines=4,
                amp=0.5, seed=21, line_opacity=0.12, dot_opacity=0.3,
            ):
                group.add(el)

        return group

    def add_cover(self, title, **props):
        W, H = config.slide_width, config.slide_height
        left_x = -W / 2 + 1.15
        heading = props.get("heading")
        subtitle = props.get("subtitle")

        stack = []
        if heading and heading != title:
            stack.append(
                Text(
                    heading.upper(),
                    font="Lato",
                    fontsize=8,
                    weight=600,
                    fill_color="flow.cover_accent",
                    letter_spacing=0.25,
                )
            )
        if subtitle:
            stack.append(
                Text(subtitle, font="Lato", fontsize=14, fill_color="flow.cover_accent")
            )
        stack.append(
            Text(
                title,
                font="Playfair Display",
                fontsize=20,
                weight=600,
                fill_color="flow.cover_title",
                max_width=W * 0.62,
            )
        )
        stack.append(Rectangle(1.0, 0.045, fill_color="flow.cover_accent"))

        arrange(stack, pos=(left_x, 0.6), anchor="center-left", gap=0.35)

        elements = list(stack)
        meta = [part for part in (props.get("author"), props.get("date")) if part]
        if meta:
            elements.append(
                Text(
                    " · ".join(meta),
                    font="Lato",
                    fontsize=10,
                    fill_color="flow.cover_author",
                    pos=(left_x, -H / 2 + 0.9),
                    anchor="bottom-left",
                )
            )

        members = Group(children=elements)
        self.current_slide.add(members)
        return members

    def add_title(self):
        slide = self.current_slide
        title_region = self.layout.get("title")
        members = Group()

        heading = (
            slide.topic.get("heading", slide.topic.name)
            if slide.topic is not None
            else None
        )
        if heading:
            eyebrow = Text(
                heading.upper(),
                font="Lato",
                fontsize=7,
                weight=600,
                fill_color="flow.backdrop",
                letter_spacing=0.2,
            )
            title_region.add(eyebrow)
            members.add(eyebrow)

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
                fill_color=config.get("subtitle.color"),
            )
            title_region.add(subtitle)
            members.add(subtitle)

        slide.add(members)
        return members

    def _flow_band(
        self, W, *, y_top, y_bottom, n_lines, amp, seed, line_opacity, dot_opacity
    ):
        rng = np.random.default_rng(seed)

        xs = np.linspace(-W / 2 - 0.5, W / 2 + 0.5, 80)
        bases = np.linspace(y_top, y_bottom, n_lines) + rng.uniform(-0.15, 0.15, n_lines)

        elements = []
        for base in bases:
            wave_amp = rng.uniform(amp * 0.4, amp)
            freq = rng.uniform(0.7, 1.8)  # cycles across the slide width
            phase = rng.uniform(0.0, 2 * np.pi)
            ys = base + wave_amp * np.sin(2 * np.pi * freq * xs / W + phase)

            segments = [MoveTo((xs[0], ys[0]))]
            segments += [LineTo((x, y)) for x, y in zip(xs[1:], ys[1:])]
            elements.append(
                Curve(
                    segments,
                    fill_opacity=0,
                    stroke_color="flow.streamline",
                    stroke_opacity=line_opacity,
                    stroke_width=0.013,
                )
            )

            dot_x = rng.uniform(-W / 2, W / 2, 5)
            dot_y = base + wave_amp * np.sin(2 * np.pi * freq * dot_x / W + phase)
            radii = rng.uniform(0.03, 0.05, 5)
            for x, y, radius in zip(dot_x, dot_y, radii):
                elements.append(
                    Circle(
                        float(radius),
                        pos=(float(x), float(y)),
                        fill_color="flow.streamline_dot",
                        fill_opacity=dot_opacity,
                    )
                )
        return elements
