from __future__ import annotations

from pathlib import Path

from ..backends.typst import TypstRenderer as _Renderer
from ..config import config
from ..log import logger
from ..parser.ir import FrontMatter
from .element import Element
from .template import PresentationTemplate


class Slide:
    """A single page of a :class:`Presentation`.

    Built mutable, then sealed with :meth:`Presentation.end_slide`, which
    snapshots the slide's rendered Typst fragment. Mutations after closing
    do not affect the snapshot.

    Attributes
    ----------
    elements : list[Element]
        Root-level elements; those with ``placement != "fixed"`` are
        skipped at render time.
    title, subtitle : str | None
        The slide's title and subtitle text; :meth:`Presentation.add_title`
        turns the title string into a rendered ``Text``.
    """

    def __init__(self, title: str | None = None, subtitle: str | None = None) -> None:
        self.elements: list[Element] = []
        self.title: str | None = title
        self.subtitle: str | None = subtitle
        # Opaque backend artifact captured at close; the core never inspects it.
        self._fragment: str | None = None

    @property
    def is_closed(self) -> bool:
        return self._fragment is not None

    def add(self, element: Element) -> Element:
        """Append ``element`` to the slide's roots and return it (for chaining)."""
        self.elements.append(element)
        logger.debug(
            rf"[yellow]SLIDE ADD ::[/yellow] {element!r}",
            extra={"markup": True, "highlighter": None},
        )
        return element


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

        When ``template.auto_footer`` is enabled, the slide's footer is added
        on creation; the footer shows ``/<total>`` when ``footer.show_total``
        is set.
        """
        slide = Slide(title, subtitle)
        self.slides.append(slide)
        self.current_slide = slide
        logger.debug(
            rf"[yellow]NEW SLIDE[/yellow] ({len(self.slides)}) {title!r}",
            extra={"markup": True, "highlighter": None},
        )
        if self.auto_add_footer:
            self.add_footer(show_total=self.footer_show_total)
        return slide

    def end_slide(self) -> None:
        """Arrange every region, snapshot the slide's fragment, then clear regions.

        Snapshotting seals the current slide; the cleared regions are reused
        by the next slide.
        """
        slide = self.current_slide
        number = self.slides.index(slide) + 1
        for region in self.layout.regions.values():
            region.arrange()
        slide._fragment = self._render_slide(slide)
        self.layout.remove_all_elements()
        suffix = f" ([u]{slide.title}[/u])" if slide.title else ""
        logger.info(
            rf"[yellow b]Generating[/yellow b] Slide {number}{suffix}",
            extra={"markup": True, "highlighter": None},
        )

    def _render_slide(self, slide: Slide) -> str:
        return self._renderer.render_slide(slide, (self.width, self.height))

    def write(self) -> None:
        """Compile the closed slides into ``<name>.pdf`` in the working directory.

        Raises if any slide is still open — call :meth:`Presentation.end_slide`
        first — or, when ``total_slides`` was declared, if the built slide
        count differs from it.
        """
        open_count = sum(not s.is_closed for s in self.slides)
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
            [s._fragment for s in self.slides],
            (self.width, self.height),
            path,
        )
        logger.info(
            "[green b]Ready[/green b]",
            extra={"markup": True, "highlighter": None},
        )
