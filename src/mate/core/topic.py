"""The :class:`Topic` domain object: a group of slides declared by a ``#>`` marker."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Topic:
    """A presentation topic declared by a ``#> Name`` marker.

    ``name`` is the marker text. ``props`` maps each ``key: value`` line of the
    marker's blockquote to the value read as a Python literal; which keys are
    meaningful is up to the template that consumes the topic (e.g. ``title``,
    ``author``, ``theme``).
    """

    name: str
    props: dict[str, object] = field(default_factory=dict)

    def get(self, key: str, default: object = None) -> object:
        """Return the value of a declared property, or ``default``."""
        return self.props.get(key, default)
