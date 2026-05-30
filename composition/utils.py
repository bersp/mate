from __future__ import annotations

from ..elements.group import Group
from ..elements.shapes import Rectangle
from ..elements.text import Text
from .layout import Layout


def layout_to_group(layout: Layout, **drawable_kw) -> Group:
    """Group of one sub-:class:`Group` per region, each a region-sized
    :class:`Rectangle` and a :class:`Text` of the region name.

    ``drawable_kw`` is forwarded to every rectangle.
    """
    sub_groups = [
        Group([
            Rectangle(region.width, region.height, **drawable_kw).move_to(region.center),
            Text(name).move_to(region.center),
        ])
        for name, region in layout.regions.items()
    ]
    return Group(sub_groups)
