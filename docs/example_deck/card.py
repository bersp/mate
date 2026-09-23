"""Card template.

Fonts: Lato for titles, Libertinus Serif for the body.
Defines: ``background``, ``add_title``, ``add_cover``, ``on_directive``.
"""

from __future__ import annotations

from mate import Group, Image, PresentationTemplateBase, Rectangle, Text, arrange, config


class PresentationTemplate(PresentationTemplateBase):
    inset = 0.45  # distance from the slide edge to the card
    padding = 0.85  # distance from the card edge to the content
    section_fontsize = 22.0  # display size of a section break's title
    shadow_offset = 0.12
    cover_logo_width = 3.4  # width of each cover logo in cm
    cover_logo_gap = 0.5  # space between two cover logos in cm
    directive_properties = {
        "section": "the running section, printed at the foot of every later slide",
    }

    def setup(self) -> None:
        config.colors.set_multiple(
            {
                "card.tint": "#d9e2df",
                "card.paper": "#fbfaf6",
                "card.shadow": "#b9c6c2",
                "card.ink": "#26333a",
                "card.accent": "#1d5c63",
            }
        )
        config.set_multiple(
            {
                "text.font": "Libertinus Serif",
                "text.color": "card.ink",
                "title.font": "Lato",
                "title.fontweight": 700,
                "title.fontsize": 13.0,
                "title.color": "card.accent",
                "subtitle.font": "Libertinus Serif",
                "subtitle.fontsize": 11.0,
                "cover.title.font": "Lato",
                "cover.title.fontweight": 700,
                "cover.title.fontsize": 20.0,
                "cover.title.color": "card.accent",
                "cover.subtitle.font": "Libertinus Serif",
                "cover.subtitle.fontsize": 11.0,
                "cover.subtitle.color": "dark_gray",
                "cover.author.font": "Lato",
                "cover.author.fontsize": 8.0,
                "cover.author.color": "dark_gray",
                "footer.font": "Lato",
                "footer.fontsize": 8.0,
                "footer.show_total": True,
                "list.bullet.symbols": ["square", "dash", "square_outline"],
            }
        )
        self._section: str | None = None

    def setup_layout(self) -> None:
        """Pull every region inside the card and set the inline code spans in
        the accent.

        The tint is appended to ``typst.preamble`` here, where the front
        matter has already had its say on ``card.accent``.
        """
        ink = config.colors.get("card.accent")
        preamble = config.get("typst.preamble")
        config.set(
            "typst.preamble",
            f'{preamble}\n#show raw: set text(fill: rgb("{ink}"))',
        )
        side = self.inset + self.padding - 0.7  # the base layout's own margin
        self.layout.get("title").adjust_borders(left=-side, right=-side, top=-0.8)
        self.layout.get("footer").adjust_borders(left=-side, right=-side, top=0.65, bottom=-0.65)
        self.layout.get("content").adjust_borders(left=-side, right=-side, bottom=-0.65)

    def on_directive(self, directive) -> None:
        """Open a section break on ``section:``, then run the base handling."""
        section = directive.get("section")
        if section is not None:
            self._section = section
            self.new_slide(counted=False)
            self.current_slide.add(
                self._display_title(
                    section,
                    self.section_fontsize,
                    max_width=config.slide_width - 4,
                    text_align="center",
                )
            )
            self.end_slide()
        super().on_directive(directive)

    def background(self) -> Group:
        """Return the backdrop: a card with a shadow on the tinted slide."""
        W, H = config.slide_width, config.slide_height
        width, height = W - 2 * self.inset, H - 2 * self.inset
        offset = self.shadow_offset

        group = Group(anchor="top-left")
        group.add(Rectangle(W, H, fill_color="card.tint"))
        group.add(Rectangle(width, height, pos=(offset, -offset), fill_color="card.shadow"))
        group.add(Rectangle(width, height, fill_color="card.paper"))
        return group

    def add_footer(self, show_total: bool = False) -> Group:
        """Add the running section at the footer's left, beside the page number.

        A cover and a section break carry no footer, and the label with it.
        """
        members = super().add_footer(show_total)
        if self._section:
            members.add(
                Text(
                    self._section,
                    case="upper",
                    font=config.get("footer.font"),
                    fontsize=config.get("footer.fontsize"),
                    letter_spacing=0.15,
                    fill_color=config.get("footer.color"),
                    pos=self.layout.get("footer").left,
                    anchor="center-left",
                )
            )
        return members

    def add_title(self) -> Group:
        """Build the title in tracked capitals, with the subtitle in the body face."""
        slide = self.current_slide
        title_region = self.layout.get("title")
        members = Group()
        if slide.title is not None:
            title = Text(
                slide.title,
                case="upper",
                font=config.get("title.font"),
                fontsize=config.get("title.fontsize"),
                weight=config.get("title.fontweight"),
                fill_color=config.get("title.color"),
                letter_spacing=0.12,
                max_width=config.get("title.max_width") or title_region.width,
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
                style="italic",
                max_width=config.get("subtitle.max_width") or title_region.width,
            )
            title_region.add(subtitle)
            members.add(subtitle)
        slide.add(members)
        return members

    def add_cover(self, title: str, **props: str) -> Group:
        """Build the cover: the logo at the head of the card, the title and its
        subtitle along the foot, over a rule that runs the width of the card."""
        W, H = config.slide_width, config.slide_height
        left = -W / 2 + self.inset + self.padding
        right = W / 2 - self.inset - self.padding
        top = H / 2 - self.inset - self.padding
        bottom = -H / 2 + self.inset + self.padding
        elements = []

        logos = props.get("logos")
        if logos:
            paths = [logos] if isinstance(logos, str) else list(logos)
            strip = [
                Image(path, width=self.cover_logo_width) for path in paths
            ]
            arrange(
                strip,
                pos=(left, top),
                anchor="top-left",
                gap=self.cover_logo_gap,
                direction="row",
            )
            elements += strip

        stack = [self._display_title(title, 26.0, max_width=right - left)]
        if props.get("subtitle"):
            stack.append(
                Text(
                    props["subtitle"],
                    style="italic",
                    font=config.get("cover.subtitle.font"),
                    fontsize=config.get("cover.subtitle.fontsize"),
                    weight=config.get("cover.subtitle.fontweight"),
                    fill_color=config.get("cover.subtitle.color"),
                )
            )
        arrange(stack, pos=(left, bottom + 1.35), anchor="bottom-left", gap=0.4)
        elements += stack

        elements.append(
            Rectangle(right - left, 0.03, pos=(left, bottom + 0.95),
                      anchor="center-left", fill_color="card.accent")
        )
        meta = " / ".join(
            part for part in (props.get("author"), props.get("date")) if part
        )
        if meta:
            elements.append(
                Text(
                    meta,
                    case="upper",
                    font=config.get("cover.author.font"),
                    fontsize=config.get("cover.author.fontsize"),
                    fill_color=config.get("cover.author.color"),
                    letter_spacing=0.15,
                    pos=(left, bottom + 0.55),
                    anchor="center-left",
                )
            )

        members = Group(children=elements)
        self.current_slide.add(members)
        return members

    def _display_title(self, title: str, fontsize: float, **kwargs) -> Text:
        """Return a title in the cover face: tracked capitals in the accent."""
        return Text(
            title,
            case="upper",
            font=config.get("cover.title.font"),
            fontsize=fontsize,
            weight=config.get("cover.title.fontweight"),
            fill_color=config.get("cover.title.color"),
            letter_spacing=0.1,
            **kwargs,
        )
