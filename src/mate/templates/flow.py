"""Flow template.

Colours: full palette + ``flow.*`` (backdrop, cover_title, cover_accent,
cover_author, streamline, streamline_dot).
Config: ``flow.tagline.*`` styles the cover's lead line.
Fonts: Lato and Playfair Display.
Footer: disabled by default.
Defines: ``background``, ``add_cover``, ``add_title``.
"""

from __future__ import annotations

import numpy as np

from ..composition.arrange import arrange
from ..config import config
from ..core.directive import Directive
from ..core.template import PresentationTemplateBase
from ..elements.group import Group
from ..elements.shapes import Circle, Curve, LineTo, MoveTo, Rectangle
from ..elements.text import Text


class PresentationTemplate(PresentationTemplateBase):
    band_height = 2.6  # depth of the content-slide flow band
    directive_properties = {
        "section": "the running section, printed as an eyebrow above every later title",
        "tagline": "a line above the cover title",
    }

    def setup(self) -> None:
        config.colors.set_multiple(
            {
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
        )

        config.set_multiple(
            {
                "text.font": "Lato",
                "text.fontsize": 9.0,
                "title.font": "Playfair Display",
                "title.fontweight": 600,
                "title.fontsize": 16.0,
                "subtitle.font": "Lato",
                "subtitle.fontsize": 11.0,
                "cover.title.font": "Playfair Display",
                "cover.title.fontweight": 600,
                "cover.title.fontsize": 20.0,
                "cover.title.color": "flow.cover_title",
                "flow.tagline.font": "Lato",
                "flow.tagline.fontweight": "regular",
                "flow.tagline.fontsize": 14.0,
                "flow.tagline.color": "flow.cover_accent",
                "cover.author.font": "Lato",
                "cover.author.fontsize": 10.0,
                "cover.author.color": "flow.cover_author",
                "list.bullet.symbols": ["square", "dash", "square_outline"],
                "footer.show": False,
            }
        )

        self._section: str | None = None

    def on_directive(self, directive: Directive) -> None:
        """Record the running section, then run the base directive handling."""
        section = directive.get("section")
        if section is not None:
            self._section = section
        super().on_directive(directive)

    def background(self) -> Group:
        """Return the slide backdrop: a flow band, full-bleed on a cover."""
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

    def add_cover(self, title: str, **props: str) -> Group:
        """Build the cover: an optional tagline, the title, an accent rule, and
        the author and date on one line."""
        W, H = config.slide_width, config.slide_height
        left_x = -W / 2 + 1.15
        tagline = props.get("tagline")

        stack = []
        if tagline:
            stack.append(
                Text(
                    tagline,
                    font=config.get("flow.tagline.font"),
                    fontsize=config.get("flow.tagline.fontsize"),
                    weight=config.get("flow.tagline.fontweight"),
                    fill_color=config.get("flow.tagline.color"),
                )
            )
        stack.append(
            Text(
                title,
                font=config.get("cover.title.font"),
                fontsize=config.get("cover.title.fontsize"),
                weight=config.get("cover.title.fontweight"),
                fill_color=config.get("cover.title.color"),
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
                    "~ · ~".join(meta),
                    font=config.get("cover.author.font"),
                    fontsize=config.get("cover.author.fontsize"),
                    weight=config.get("cover.author.fontweight"),
                    fill_color=config.get("cover.author.color"),
                    pos=(left_x, -H / 2 + 0.9),
                    anchor="bottom-left",
                )
            )

        members = Group(children=elements)
        self.current_slide.add(members)
        return members

    def add_title(self) -> Group:
        """Build the current slide's title, under the running section eyebrow."""
        slide = self.current_slide
        title_region = self.layout.get("title")

        members = Group()

        if self._section:
            eyebrow = Text(
                self._section.upper(),
                font="Lato",
                fontsize=7,
                weight=600,
                fill_color="flow.backdrop",
                letter_spacing=0.2,
            )
            title_region.add(eyebrow)
            members.add(eyebrow)

        if slide.title is not None:
            title_width = config.get("title.max_width")
            if title_width is None:
                title_width = title_region.width
            title = Text(
                slide.title,
                font=config.get("title.font"),
                fontsize=config.get("title.fontsize"),
                weight=config.get("title.fontweight"),
                fill_color=config.get("title.color"),
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
