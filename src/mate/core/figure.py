from __future__ import annotations

from pathlib import Path

from ..backends.typst import TypstRenderer as _Renderer
from ..log import logger
from .element import Element, measure_all, union_bbox


class Figure:
    """Standalone drawing: root elements compiled to a PDF sized to their content.

    A figure file builds one module-level ``Figure``, adds elements, and calls
    :meth:`write` under an ``if __name__ == "__main__":`` guard. Run directly,
    the file compiles the PDF; executed under another ``__name__``, the guard
    does not fire and the elements stay available on the instance.

    Attributes
    ----------
    elements : list of :class:`~mate.core.element.Element`
        Root elements in add order.
    """

    def __init__(self) -> None:
        self.elements: list[Element] = []
        self._renderer = _Renderer()

    def add(self, element: Element) -> Element:
        """Append a root ``element`` and return it for chaining."""
        self.elements.append(element)
        return element

    def write(self, path: str | Path) -> None:
        """Compile the elements into a PDF at ``path`` sized to their union bbox.

        Measures every element in one pass and translates them in place to
        centre the union bbox at the origin; the page matches the union's
        size exactly. A repeated ``write`` translates by zero. Raises if no
        element has been added.
        """
        if not self.elements:
            raise RuntimeError("the figure has no elements; call .add() before write().")
        measure_all(self.elements)
        cx, cy, w, h = union_bbox(self.elements)
        for el in self.elements:
            el.shift((-cx, -cy))
        canvas = (w, h)
        logger.info(
            rf"[yellow b]Compiling[/yellow b] [magenta]{path}[/magenta]",
            extra={"markup": True, "highlighter": None},
        )
        self._renderer.compile_document(
            [self._renderer.render_snapshot(self.elements, canvas)], canvas, Path(path)
        )
