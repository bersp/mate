from __future__ import annotations

from pathlib import Path

from ..backends.typst import TypstRenderer as _Renderer
from ..config import config
from ..log import logger
from ..parser.ir import FrontMatter
from .slide import Slide, Snapshot
from .template import PresentationTemplate


class Presentation(PresentationTemplate):
    """Top-level presentation built on a template."""

    def __new__(cls, *args, **kwargs):
        if cls is Presentation and config.templates:
            from ..templates import load_template

            templates = [load_template(name) for name in config.templates]
            cls = type("Presentation", (cls, *templates), {})
        return super().__new__(cls)

    def __init__(
        self,
        name: str,
        width: float | None = None,
        height: float | None = None,
        total_slides: int | None = None,
        frontmatter: FrontMatter | None = None,
    ) -> None:
        self.name: str = name
        self.total_slides: int | None = total_slides
        self._frontmatter: FrontMatter = frontmatter or FrontMatter()
        if width is not None:
            config.set("slide.width", float(width))
        if height is not None:
            config.set("slide.height", float(height))
        super().__init__()
        self.width: float = config.slide_width
        self.height: float = config.slide_height
        self.slides: list[Slide] = []
        self.current_slide: Slide | None = None
        self._renderer = _Renderer()

    def new_slide(self, title: str | None = None, subtitle: str | None = None) -> Slide:
        """Create, attach, and return a fresh open slide.

        The template's :meth:`background` element, when any, is added first so
        it renders behind everything. When ``template.auto_footer`` is enabled,
        the slide's footer is added on creation; the footer shows ``/<total>``
        when ``footer.show_total`` is set.
        """
        slide = Slide(title, subtitle)
        self.slides.append(slide)
        self.current_slide = slide
        logger.debug(
            rf"[yellow]NEW SLIDE[/yellow] ({len(self.slides)}) {title!r}",
            extra={"markup": True, "highlighter": None},
        )
        background = self.background()
        if background is not None:
            slide.add(background)
        if self.auto_add_footer:
            self.add_footer(show_total=self.footer_show_total)
        return slide

    def pause(self) -> None:
        """Split the current slide: open a new reveal step.

        Content added after a ``pause`` lands on a later page; sealing the
        slide produces one page per reveal step, each showing the cumulative
        content up to that step.
        """
        self.current_slide.pause()

    def end_slide(self) -> None:
        """Arrange every region, seal the slide into snapshots, then clear regions.

        The regions are arranged once over the slide's full content, so every
        position is baked before any page is rendered; each reveal step is then
        rendered as a :class:`Snapshot` of its cumulative root elements. The
        cleared regions are reused by the next slide.
        """
        slide = self.current_slide
        number = self.slides.index(slide) + 1
        for region in self.layout.regions.values():
            region.arrange()
        canvas = (self.width, self.height)
        slide.snapshots = [
            Snapshot(self._renderer.render_snapshot(roots, canvas))
            for roots in slide.reveal_prefixes()
        ]
        self.layout.remove_all_elements()
        suffix = f" ([u]{slide.title}[/u])" if slide.title else ""
        logger.info(
            rf"[yellow b]Generating[/yellow b] Slide {number}{suffix}",
            extra={"markup": True, "highlighter": None},
        )

    def write(self) -> None:
        """Compile the closed slides into ``<name>.pdf`` in the working directory.

        Raises if any slide is still open — call :meth:`Presentation.end_slide`
        first — or, when ``total_slides`` was declared, if the built slide
        count differs from it.
        """
        open_count = sum(not s.is_sealed for s in self.slides)
        if open_count:
            raise RuntimeError(
                f"{open_count} slide(s) still open; call .end_slide() before write()."
            )
        if self.total_slides is not None and len(self.slides) != self.total_slides:
            raise RuntimeError(
                f"declared {self.total_slides} slide(s) but built {len(self.slides)}."
            )
        path = Path(f"{self.name}.pdf")
        logger.info(
            rf"[yellow b]Compiling[/yellow b] [magenta]{self.name}.pdf[/magenta]",
            extra={"markup": True, "highlighter": None},
        )
        self._renderer.compile_document(
            [snap.markup for s in self.slides for snap in s.snapshots],
            (self.width, self.height),
            path,
        )
        logger.info(
            "[green b]Ready[/green b]",
            extra={"markup": True, "highlighter": None},
        )
