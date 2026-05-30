from __future__ import annotations

from ..elements.group import Group
from ..elements.shapes import Rectangle
from ..elements.text import Text
from .layout import Layout


def layout_to_group(
    layout: Layout, names: list[str] | None = None, **drawable_kw
) -> Group:
    """Group of one sub-:class:`Group` per region, each a region-sized
    :class:`Rectangle` and a :class:`Text` of the region name.

    ``names`` selects which regions to include (in the given order);
    ``None`` includes every region. ``drawable_kw`` is forwarded to every
    rectangle.
    """
    selected = (
        layout.regions.items()
        if names is None
        else ((n, layout.get(n)) for n in names)
    )
    sub_groups = [
        Group([
            Rectangle(region.width, region.height, **drawable_kw).move_to(region.center),
            Text(name).move_to(region.center),
        ])
        for name, region in selected
    ]
    return Group(sub_groups)
