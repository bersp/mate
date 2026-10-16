"""The pipeline of ``pipeline.py`` with the Typst stage as a hidden layer."""

from mate import Arrow, Figure, Rectangle, Text

fig = Figure()

BOX_WIDTH = 3.4
BOX_HEIGHT = 1.2
GAP = 1.4
STEP = BOX_WIDTH + GAP
DROP = 2.2


def stage(x, y, label, color, key=None):
    fig.add(
        Rectangle(
            BOX_WIDTH,
            BOX_HEIGHT,
            pos=(x, y),
            corner_radius=0.18,
            fill_opacity=0,
            stroke_color=color,
            stroke_width=0.035,
            id=key,
        )
    )
    fig.add(Text(label, pos=(x, y), anchor="center", fill_color=color, id=key))


stages = [("slides.md", "gray"), ("mate", "red"), ("slides.pdf", "gray")]
left = -STEP

for index, (label, color) in enumerate(stages):
    x = left + index * STEP
    stage(x, 0, label, color)
    if index:
        fig.add(
            Arrow(
                (x - STEP + BOX_WIDTH / 2 + 0.2, 0),
                (x - BOX_WIDTH / 2 - 0.2, 0),
                stroke_color="darker_gray",
                stroke_width=0.035,
            )
        )

stage(0, -DROP, "Typst", "yellow", key="typst")
fig.add(
    Arrow(
        (0, -BOX_HEIGHT / 2 - 0.2),
        (0, -DROP + BOX_HEIGHT / 2 + 0.2),
        stroke_color="darker_gray",
        stroke_width=0.035,
        id="typst",
    )
)

for el in fig.elements:
    if "typst" in el.id:
        el.set_hidden(True)

if __name__ == "__main__":
    for el in fig.elements:
        el.set_hidden(False)
    fig.write("pipeline_layers.pdf")
