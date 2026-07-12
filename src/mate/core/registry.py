from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .element import Element


IDKey = int | float | str


class IDRegistry:
    """Process-global index from id values to elements that declared them.

    Every :class:`~mate.core.element.Element` constructed with a non-empty
    ``id`` registers itself here, once per key in its id list. A single
    key may map to multiple elements — duplicate ids in source markup
    (e.g. two ``[...](id=foo)`` blocks) are intentionally allowed so
    operations can target every element tagged with the same label.

    Clones produced by :meth:`Element.copy` do **not** auto-register:
    copies are not globally addressable, by design.
    """

    def __init__(self) -> None:
        self._by_id: dict[IDKey, list[Element]] = {}

    def register(self, element: Element, key: IDKey) -> None:
        """Append ``element`` to the bucket for ``key``."""
        self._by_id.setdefault(key, []).append(element)

    def clear(self) -> None:
        """Drop every registered id. Called at the start of each slide."""
        self._by_id.clear()

    def get(self, key: IDKey) -> list[Element]:
        """Return the elements registered under ``key`` in insertion order.

        Raises
        ------
        KeyError
            If no element has been registered under ``key``.
        """
        if key not in self._by_id:
            raise KeyError(f"unknown id: {key!r}")
        return self._by_id[key]


id_registry = IDRegistry()
