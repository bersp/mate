from __future__ import annotations

from pathlib import Path

from ..backends.typst import TypstRenderer
from ..config import config
from .element import Element


class Slide:
    """A single page of a :class:`Presentation`.

    Owns the root list of :class:`Element`\\ s. Has no other state —
    measurement and rendering are driven entirely by the element tree;
    the slide is just a container.

    Attributes
    ----------
    elements : list[Element]
        Root-level elements; those with ``placement != "fixed"`` are
        skipped at render time.
    """

    def __init__(self) -> None:
        self.elements: list[Element] = []

    def add(self, element: Element) -> Element:
        """Append ``element`` to the slide's roots and return it (for chaining)."""
        self.elements.append(element)
        return element


class Presentation:
    """Top-level container: page geometry plus an ordered list of slides.

    Parameters
    ----------
    width, height : float, optional
        Page size in cm. Applies uniformly to every slide.
    """

    def __init__(self, width: float = 20, height: float = 15) -> None:
        self.width: float = width
        self.height: float = height
        self.slides: list[Slide] = []
        config.set_slide_size(width, height)

    def new_slide(self) -> Slide:
        """Create, attach, and return a fresh empty slide."""
        slide = Slide()
        self.slides.append(slide)
        return slide

    def add_slide(self, slide: Slide) -> Slide:
        """Attach an externally built ``slide`` and return it."""
        self.slides.append(slide)
        return slide

    def write(self, path: str | Path = "presentation.typ") -> None:
        """Render the presentation to a Typst source file at ``path``."""
        TypstRenderer(Path(path)).render(self)
