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
    is_cover : bool
        ``True`` for a generated cover page. A cover carries no footer and is
        excluded from the slide numbering.
    steps : list[list[Element]]
        Root elements grouped by reveal step; elements with
        ``placement != "fixed"`` are skipped at render time.
    snapshots : list[Snapshot]
        The sealed pages, filled by :meth:`Presentation.end_slide`. Empty until
        the slide is sealed.
    """

    def __init__(
        self,
        title: str | None = None,
        subtitle: str | None = None,
        is_cover: bool = False,
    ) -> None:
        self.title: str | None = title
        self.subtitle: str | None = subtitle
        self.is_cover: bool = is_cover
        self.steps: list[list[Element]] = [[]]
        self.replaced: list[tuple[int, Element]] = []
        self.reveals: list[tuple[int, Element]] = []
        self.snapshots: list[Snapshot] = []

    @property
    def is_sealed(self) -> bool:
        return bool(self.snapshots)

    def add(self, element: Element) -> Element:
        """Append ``element`` to the current reveal step and return it (for chaining).

        Any ``Text`` carrying ``||`` reveal segments anywhere in ``element``'s
        subtree (the text may be wrapped in a ``Group``, as a bullet item is)
        opens one reveal step per segment after the first and registers each
        later segment's nodes in :attr:`reveals`. The tail reveals across steps
        while holding its layout space from the start.
        """
        self.steps[-1].append(element)
        self._register_reveals(element)
        logger.debug(
            rf"[yellow]SLIDE ADD ::[/yellow] {element!r}",
            extra={"markup": True, "highlighter": None},
        )
        return element

    def _register_reveals(self, element: Element) -> None:
        """Open reveal steps for every ``||`` segment in ``element``'s subtree."""
        by_offset: dict[int, list[Element]] = {}
        stack = [element]
        while stack:
            node = stack.pop()
            segments = getattr(node, "reveal_segments", None)
            if segments:
                for offset, nodes in enumerate(segments):
                    if offset:
                        by_offset.setdefault(offset, []).extend(nodes)
            stack.extend(node.children)
        if not by_offset:
            return
        base = len(self.steps) - 1
        for offset in sorted(by_offset):
            self.pause()
            for node in by_offset[offset]:
                self.reveals.append((base + offset, node))

    def pause(self) -> None:
        """Open a new reveal step; subsequent content lands on a later page."""
        self.steps.append([])

    def reveal_states(self) -> Iterator[tuple[list[Element], set[int]]]:
        """Yield ``(roots, hidden_ids)`` for each reveal step.

        ``roots`` is the cumulative root elements visible at step ``k``: an
        element marked in :attr:`replaced` at step ``j`` is dropped from every
        step ``k >= j``.

        ``hidden_ids`` are the ``id()`` of nodes registered in :attr:`reveals`
        whose reveal step has not yet arrived (``r > k``); the renderer keeps
        them in the layout and draws them hidden, holding a ``||`` tail's space
        before it appears.
        """
        revealed: list[Element] = []
        for k, step in enumerate(self.steps):
            revealed = revealed + step
            dropped = {id(el) for j, el in self.replaced if j <= k}
            roots = [e for e in revealed if id(e) not in dropped]
            hidden = {id(el) for r, el in self.reveals if r > k}
            yield roots, hidden
