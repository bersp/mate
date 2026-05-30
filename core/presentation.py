from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..backends.typst import TypstRenderer
from ..config import config
from .element import Element
from .template import PresentationTemplate

if TYPE_CHECKING:
    from ..elements.text import Text


class Slide:
    """A single page of a :class:`Presentation`.

    Attributes
    ----------
    elements : list[Element]
        Root-level elements; those with ``placement != "fixed"`` are
        skipped at render time.
    title, subtitle : Text | None
        The slide's title and subtitle, if set.
    """

    def __init__(self) -> None:
        self.elements: list[Element] = []
        self.title: Text | None = None
        self.subtitle: Text | None = None

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

    def new_slide(self) -> Slide:
        """Create, attach, and return a fresh empty slide."""
        slide = Slide()
        self.slides.append(slide)
        self.current_slide = slide
        return slide

    def add_slide(self, slide: Slide) -> Slide:
        """Attach an externally built ``slide`` and return it."""
        self.slides.append(slide)
        self.current_slide = slide
        return slide

    def write(self, path: str | Path = "presentation.typ") -> None:
        """Render the presentation to a Typst source file at ``path``."""
        TypstRenderer(Path(path)).render(self)
