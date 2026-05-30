from __future__ import annotations

from pathlib import Path

from ..backends.typst import TypstRenderer as _Renderer
from ..config import config
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
        return element


class Presentation(PresentationTemplate):
    """Top-level presentation built on a template."""

    def __init__(self, width: float = 20, height: float = 15) -> None:
        self.width: float = width
        self.height: float = height
        config.set_slide_size(width, height)
        super().__init__()
        self.slides: list[Slide] = []
        self.current_slide: Slide | None = None
        self._renderer = _Renderer()

    def new_slide(self, title: str | None = None, subtitle: str | None = None) -> Slide:
        """Create, attach, and return a fresh open slide."""
        slide = Slide(title, subtitle)
        self.slides.append(slide)
        self.current_slide = slide
        return slide

    def end_slide(self) -> None:
        """Arrange every region, close the current slide (snapshotting its fragment), then clear the regions for the next slide."""
        for region in self.layout.regions.values():
            region.arrange()
        slide = self.current_slide
        slide._fragment = self._render_slide(slide)
        self.layout.remove_all_elements()

    def _render_slide(self, slide: Slide) -> str:
        return self._renderer.render_slide(slide, (self.width, self.height))

    def write(self, path: str | Path = "presentation.typ") -> None:
        """Assemble the closed slides into a Typst source file at ``path``.

        Raises if any slide is still open — call :meth:`Slide.close` first.
        """
        open_count = sum(not s.is_closed for s in self.slides)
        if open_count:
            raise RuntimeError(
                f"{open_count} slide(s) still open; call .close() before write()."
            )
        self._renderer.write_document(
            [s._fragment for s in self.slides], (self.width, self.height), Path(path)
        )
