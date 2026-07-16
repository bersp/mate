"""The :class:`Directive` domain object: an off-slide instruction placed between
slides by a ``#>`` marker."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Directive:
    """An off-slide instruction placed between slides by a ``#>`` marker.

    ``props`` maps each ``key: value`` line of the marker's blockquote to the
    value read as a Python literal; which keys are meaningful is up to the
    template that consumes the directive through ``on_directive`` (e.g.
    ``cover``, ``title``, ``theme``, ``heading``).
    """

    props: dict[str, object] = field(default_factory=dict)

    def get(self, key: str, default: object = None) -> object:
        """Return the value of a declared property, or ``default``."""
        return self.props.get(key, default)
