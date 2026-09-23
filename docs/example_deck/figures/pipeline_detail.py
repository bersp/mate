from mate import Arrow, Figure, Rectangle, Text

fig = Figure()

BOX_WIDTH = 2.5
BOX_HEIGHT = 1.2
GAP = 0.95


def stage(x, label, color):
    fig.add(
        Rectangle(
            BOX_WIDTH,
            BOX_HEIGHT,
            pos=(x, 0),
            corner_radius=0.18,
            fill_opacity=0,
            stroke_color=color,
            stroke_width=0.035,
        )
    )
    fig.add(Text(label, pos=(x, 0), anchor="center", fill_color=color))


step = BOX_WIDTH + GAP
stages = [("slides.md", "gray"), ("mate", "red"), ("Typst", "yellow"), ("slides.pdf", "gray")]
left = -1.5 * step

for index, (label, color) in enumerate(stages):
    x = left + index * step
    stage(x, label, color)
    if index:
        fig.add(
            Arrow(
                (x - step + BOX_WIDTH / 2 + 0.15, 0),
                (x - BOX_WIDTH / 2 - 0.15, 0),
                stroke_color="darker_gray",
                stroke_width=0.035,
            )
        )

if __name__ == "__main__":
    fig.write("pipeline_detail.pdf")
