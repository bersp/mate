from __future__ import annotations

from pathlib import Path

from ..backends.typst import TypstRenderer as _Renderer
from ..composition.collisions import Collision, find_collisions, log_collisions
from ..config import config
from ..log import logger
from ..parser.ir import FrontMatter
from .element import union_bbox
from .registry import id_registry
from .slide import Slide, Snapshot
from .template import PresentationTemplateBase


class Presentation(PresentationTemplateBase):
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

    def new_slide(
        self,
        title: str | None = None,
        subtitle: str | None = None,
        is_cover: bool = False,
    ) -> Slide:
        """Create, attach, and return a fresh open slide.

        The template's :meth:`background` element, when any, is added first so
        it renders behind everything. When ``footer.show`` is enabled,
        a content slide's footer is added on creation; the footer shows
        ``/<total>`` when ``footer.show_total`` is set. A cover slide
        (``is_cover``) carries no footer.
        """
        id_registry.clear()
        slide = Slide(title, subtitle, is_cover)
        self.slides.append(slide)
        self.current_slide = slide
        self.layout.reset_active()
        logger.debug(
            rf"[yellow]NEW SLIDE[/yellow] ({len(self.slides)}) {title!r}",
            extra={"markup": True, "highlighter": None},
        )
        background = self.background()
        if background is not None:
            slide.background = slide.add(background)
        if config.get("footer.show") and not is_cover:
            self.add_footer(show_total=config.get("footer.show_total"))
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
        if config.get("warn.overflow"):
            self._warn_overflow(number)
        self._resolve_overwrites()
        self._resolve_alternates()
        self._resolve_modifies()
        if config.get("warn.collisions"):
            self._warn_collisions(number)
        canvas = (self.width, self.height)
        slide.snapshots = [
            Snapshot(self._renderer.render_snapshot(roots, canvas, hidden))
            for roots, hidden in slide.reveal_states()
        ]
        self.layout.remove_all_elements()
        suffix = f" ([u]{slide.title}[/u])" if slide.title else ""
        logger.info(
            rf"[yellow b]Generating[/yellow b] Slide {number}{suffix}",
            extra={"markup": True, "highlighter": None},
        )

    def _warn_overflow(self, number: int) -> None:
        """Log a warning for each region holding more than it can fit.

        Runs on the arranged regions and reads the bboxes the arrange pass
        measured, without a query of its own.
        """
        tolerance = 0.01  # cm
        for name, region in self.layout.regions.items():
            if not region.elements:
                continue
            _, _, width, height = union_bbox(region.elements)
            excess = []
            if width - region.width > tolerance:
                excess.append(f"{width - region.width:.2f} cm wider")
            if height - region.height > tolerance:
                excess.append(f"{height - region.height:.2f} cm taller")
            if excess:
                logger.warning(
                    rf"[yellow b]Slide {number}[/yellow b] content is "
                    rf"{' and '.join(excess)} than region [magenta]{name}[/magenta]",
                    extra={"markup": True, "highlighter": None},
                )

    def _warn_collisions(self, number: int) -> None:
        """Log a warning for each pair of drawn boxes crossing on this slide.

        Walks every reveal step with the elements it hides and reports a pair
        once, on the first step it appears in. The slide background is left
        out: it sits behind the content by design.
        """
        seen: set[tuple[int, int]] = set()
        collisions: list[Collision] = []
        slide = self.current_slide
        for roots, hidden in slide.reveal_states():
            content = [root for root in roots if root is not slide.background]
            for a, b, area in find_collisions(content, hidden):
                key = (id(a), id(b))
                if key not in seen:
                    seen.add(key)
                    collisions.append((a, b, area))
        log_collisions(collisions, f"Slide {number}")

    def write(self, path: str | Path | None = None, ppi: float | None = None) -> None:
        """Compile the closed slides into a file at ``path``.

        ``path`` defaults to ``<name>.pdf`` in the working directory; its
        suffix picks the output format and ``ppi`` the resolution of a raster
        one. Raises if any slide is still open (call
        :meth:`Presentation.end_slide` first) or, when ``total_slides`` was
        declared, if the number of content slides built (covers excluded)
        differs from it.
        """
        open_count = sum(not s.is_sealed for s in self.slides)
        if open_count:
            raise RuntimeError(
                f"{open_count} slide(s) still open; call .end_slide() before write()."
            )
        content_count = sum(1 for s in self.slides if not s.is_cover)
        if self.total_slides is not None and content_count != self.total_slides:
            raise RuntimeError(
                f"declared {self.total_slides} slide(s) but built {content_count}."
            )
        path = Path(path) if path is not None else Path(f"{self.name}.pdf")
        logger.info(
            rf"[yellow b]Compiling[/yellow b] [magenta]{path}[/magenta]",
            extra={"markup": True, "highlighter": None},
        )
        self._renderer.compile_document(
            [snap.markup for s in self.slides for snap in s.snapshots],
            (self.width, self.height),
            path,
            ppi,
        )
        logger.info(
            "[green b]Ready[/green b]",
            extra={"markup": True, "highlighter": None},
        )
