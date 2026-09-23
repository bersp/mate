from mate import Arrow, Figure, Rectangle, Text

fig = Figure()

BOX_WIDTH = 3.4
BOX_HEIGHT = 1.2
GAP = 1.4

stages = [("slides.md", "gray"), ("mate", "red"), ("slides.pdf", "gray")]
step = BOX_WIDTH + GAP
left = -step

for index, (label, color) in enumerate(stages):
    x = left + index * step
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
    if index:
        fig.add(
            Arrow(
                (x - step + BOX_WIDTH / 2 + 0.2, 0),
                (x - BOX_WIDTH / 2 - 0.2, 0),
                stroke_color="darker_gray",
                stroke_width=0.035,
            )
        )

if __name__ == "__main__":
    fig.write("pipeline.pdf")
