from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..log import logger
from .element import Element


@dataclass
class Snapshot:
    """One compiled page of a :class:`Slide`: a frozen snapshot of rendered markup."""

    markup: str


class Slide:
    """A single authored unit of a :class:`Presentation`.

    A slide is a sequence of reveal *steps*. Content is appended to the current
    step; :meth:`pause` opens a new one. :meth:`Presentation.end_slide` seals the
    slide into one :class:`Snapshot` per cumulative step, so a slide with a
    ``pause`` compiles to several pages that reveal more content each.

    Attributes
    ----------
    title, subtitle : str | None
        The slide's title and subtitle text; :meth:`Presentation.add_title`
        turns the title string into a rendered ``Text``.
    steps : list[list[Element]]
        Root elements grouped by reveal step; elements with
        ``placement != "fixed"`` are skipped at render time.
    snapshots : list[Snapshot]
        The sealed pages, filled by :meth:`Presentation.end_slide`. Empty until
        the slide is sealed.
    """

    def __init__(self, title: str | None = None, subtitle: str | None = None) -> None:
        self.title: str | None = title
        self.subtitle: str | None = subtitle
        self.steps: list[list[Element]] = [[]]
        self.snapshots: list[Snapshot] = []

    @property
    def is_sealed(self) -> bool:
        return bool(self.snapshots)

    def add(self, element: Element) -> Element:
        """Append ``element`` to the current reveal step and return it (for chaining)."""
        self.steps[-1].append(element)
        logger.debug(
            rf"[yellow]SLIDE ADD ::[/yellow] {element!r}",
            extra={"markup": True, "highlighter": None},
        )
        return element

    def pause(self) -> None:
        """Open a new reveal step; subsequent content lands on a later page."""
        self.steps.append([])

    def reveal_prefixes(self) -> Iterator[list[Element]]:
        """Yield the cumulative root elements visible at each reveal step."""
        revealed: list[Element] = []
        for step in self.steps:
            revealed = revealed + step
            yield revealed
