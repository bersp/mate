---
templates: [card]
colors:
  accent1: "#b4553c"
  accent2: "#b8891a"
---

#>
> cover: True
> logos: figures/logo.png
> title: Slides written in Markdown
> subtitle: An introduction to mate
> author: Bernardo L. Español
> date: Today

#>
> section: Basics

# From Markdown to PDF

A deck is a single Markdown file. `mate` reads that file and hands the typesetting over to the backend (only Typst right now).

These slides are made with mate. The source is `docs/example_deck/example_deck.md`, if you want to see how any of them is written.

> vspace : 1.0
> add mate figure : "figures/pipeline.py", align="center"

# Paragraphs, lists and math

You can write regular paragraphs. **Bold**, _italic_ and `code` work as usual.

- Bullet lists too,
  - with nested and multi-paragraph items.
- As you can see.

1. Numbered lists as well,
2. with their numbers as markers.

You can also write math using Typst:
$$
integral_0^oo e^(-x^2) dif x = sqrt(pi) / 2
$$

# Paragraphs, lists and math
```text : title="example_deck.md", fontsize=8
# Paragraphs, lists and math

You can write regular paragraphs.
**Bold**, _italic_ and `code` work as usual.

- Bullet lists too,
  - with nested and multi-paragraph items.
...

You can also write math using Typst:
$$ integral_0^oo e^(-x^2) dif x = sqrt(pi) / 2 $$
```

# Building the deck

That file, as it stands, builds with:

```bash
mate example_deck.md
```

> vspace : 0.6

mate writes the PDF next to the source. [[color="dark_gray"]]

# Templates

A template sets the fonts, colours, background, cover and titles, and can add commands of its own. The deck picks it in the front matter:

```text : fontsize=9
---
templates: [card]
---
```

These slides use `card`, which lives in `card.py` next to the Markdown. Change that name and the whole deck changes its look.

You can also use more than one, like `templates: [card, simple]`, to mix features from different templates. If two of them change the same thing, the first one in the list is used.

# Styling text and math
This is some [styled text][color="accent1"].||

You can do [different][fontsize=8,rotate=180,color="accent1"] things with this. [[align="right"]]

> pause

> vspace : 1

Even in math mode:
$$
[integral][color="accent1"]_0^oo e^(-x^2) [dif][color="accent1"] x
[[align="left"]] = [sqrt(pi) / [2][color="accent2"]][rotate=90, shift=(0, -0.2)]
$$

# Styling text and math

Markdown's link syntax carries the styling, with the properties in the second pair of brackets:

- `[in red][color="red"]` gives you [in red][color="accent1"],
- `[smaller][fontsize=8]` gives you [smaller][fontsize=8],
- `[spaced out][letter_spacing=0.15]` gives you [spaced out][letter_spacing=0.15].
 
> vspace : 1.0

A pair of brackets on its own applies to the whole block, which is how the equation above was pushed to the left, and this paragraph to the right. [[align="right"]]

# Adding an image

The commands a deck can use come from its template, and you write them as `> command : arguments`. Some, like `add image`, are in the base template:

> vspace : 0.5

`> add image : "figures/logo.png", width="60%"`

> vspace : 0.6
> add image : "figures/logo.png", width="60%", align="center"
> vspace : 0.3

The caption under a figure is an ordinary paragraph. [[fontsize=8, color="dark_gray", align="center"]]

# Code blocks

A fenced block is rendered in monospace over a box, highlighted by language. As in a command, its options follow a `:`.

```python : title="relax.py", numbers=True, words={"gamma": {"color": "accent1"}}
def relax(x, gamma=0.5, steps=100):
    """Gradient descent with a fixed step."""
    for _ in range(steps):
        x = x - gamma * grad(x)
    return x
```

Line numbers, a title bar, the colors, the width and the theme of every syntax role are options too. [[color="dark_gray", fontsize=9]]

#>
> section: Layout

# Regions

So far everything went into `content`, the region under the title, each new block below the previous one.

> vspace : 1.0

- To write somewhere else, switch with `> region : "name"`.
- The `anchor` of a region is where its content starts, here the top left.
- `> vspace : 1.0` adds 1 cm of space, like the one above this list.

> pause

- `> draw layout` outlines the regions you name, as on this slide.

> draw layout : ["title", "content", "footer"]

# Two columns in one line

> grid : [["text", "fig"]], hgap=0.6, width_ratios=[1, 1.2]
> region : "text"

`> grid` cuts the active region into named cells, and every cell becomes a region of its own.

- Cells sharing a name merge into one.
- `width_ratios` and `height_ratios` set the proportions.
- Any content command also takes a `region` argument.

> region : "fig", anchor="center"
> add image : "figures/logo.png", width="100%"

# Two columns in one line
```text : title="two-columns.md", fontsize=9
> grid : [["text", "fig"]], hgap=0.6, width_ratios=[1, 1.2]
> region : "text"

Everything written here lands in the left cell.

- Cells sharing a name merge into one.
...

> region : "fig", anchor="center"
> add image : "figures/logo.png", width="100%"
```

# Cells that share a name merge

> grid : [["head", "head"], ["left", "right"], ["foot", "foot"]], hgap=0.6, vgap=0.25, height_ratios=[1, 2.4, 0.9]
> region : "head"

Repeat a name in the template and those cells become a single region. The top and bottom rows here span both columns.

> region : "left"

- The template is rows by columns, with row 0 on top.
- `height_ratios` gives the middle row most of the height.

> region : "right"

- `anchors` sets the anchor of one cell.
- A grid can split a cell of another grid.

> region : "foot", anchor="center"

One caption running under both columns. [[color="dark_gray", fontsize=9]]

> pause

> draw layout : ["head", "left", "right", "foot"]

#>
> section: Elements

# Leaving the stack

With `floating=True` the image leaves the stack: it sits where `pos` puts it, and `anchor` picks which point of the image goes there, its centre by default. The mate logo in the corner, for example, comes from this line:

> vspace : 0.5

`> add image : "figures/logo.png", width=3.4, floating=True, pos=(4.2, -2.48)` [[fontsize=9]]

> vspace : 0.5
> add image : "figures/logo.png", width=3.4, floating=True, pos=(4.2, -2.48)

Positions are in centimetres from the centre of the slide, with y pointing up. The slide is 16 × 9 cm by default.

# Almost everything is an Element

A paragraph, an image, a figure, a code block and a shape are the same kind of thing. Any of them can go in a region, float at a `pos`, take an `id` or a `z_order`, and so on.

> add : Circle(0.55, pos=(-4.4, -1), fill_color="accent1")
> add : Rectangle(1.7, 1.1, pos=(-1.4, -1), corner_radius=0.15, fill_color="accent2")
> add : Line((1.1, -1.55), (2.8, -0.45), stroke_color="dark_gray", stroke_width=0.06)
> add : Arrow((3.6, -1.0), (5.6, -1.0), stroke_color="dark_gray")

```markdown fragment : floating=True, pos=(0, -2.5), anchor="bottom-center"
`> add` floats any element at its own `pos`, and this block of content floats the same way. [[color="dark_gray", fontsize=9, text_align="center"]]
```

# Cropping an image

> grid : [["fig", "text"]], hgap=0.6, width_ratios=[1, 1.2]
> region : "text", anchor="center"

`> add image : ..., crop=(...)`\
keeps only a piece of the image.

> region : "fig", anchor="center"
> add image : "figures/logo.png", height="80%", crop=(0, 0, 0.249, 1)

#>
> section: Step by step

# Revealing in steps

Every `> pause` opens a new step, and `||` splits a line into pieces that arrive one at a time. || Like this one, || and this one.

> pause

> vspace : 0.4

The space is reserved from the start, so nothing already on the slide moves when the rest shows up.

# Modifying an element

`> modify` restyles or moves anything carrying an id, from its step onward.

> vspace : 0.4

This paragraph holds [one tagged span][id="first"] and [a second one][id="second"].

> pause

> modify : "first", color="accent1", weight="bold"

> pause

> modify : "second", color="accent2", weight="bold"
> modify : "first", color="dark_gray", weight="regular"

# Masking an image

> grid : [["text", "fig"]], hgap=0.6, width_ratios=[1, 1], anchors={"text": "center-left", "fig": "center"}
> region : "text"

`> mask image : id, ...`\
shows a window of a tagged image.

> add image : "figures/logo.png", width="100%", id="mark", region="fig"
> mask image : "mark", x=0.27, y=0, width=0.73, height=1

> pause

`> unmask image : id`\
brings it back.
> unmask image : "mark"

# Grouping content in a fragment

> grid : [["main", "side"]], hgap=0.6, width_ratios=[1.25, 1], anchors={"main": "center-left", "side": "center-left"}
> region : "main"

A `markdown fragment` fence takes a whole run of content and treats it as one block. Give it an `id` to point at it later, a `region` to send it somewhere else, or any span property to restyle all of it at once. [[align="right"]]

```markdown fragment : region="side", color="accent1"
This fragment went to the other column, in one colour.

- including this list,
- and this line.
```

# Rewriting a block in place

An `overwrite` fence redraws a tagged block inside its own box, so nothing around it moves.

```markdown fragment : id="claim"
The first take on the idea, tagged with an id.
```

This line sits underneath and stays where it is.

> pause

```markdown overwrite : "claim"
The replacement, drawn inside the box of the original.
```

# One variant per step

An `alternate` block puts one variant per step in the same slot, as tall as the tallest of them. Use it to step through versions of a figure.

> vspace : 0.8

```markdown alternate
> add mate figure : "figures/pipeline.py", align="center"

> alt

> add mate figure : "figures/pipeline_detail.py", align="center"
```

# Mixing fragments and overwrites

Everything so far can be mixed, and the layout holds. For example, a fragment reveals itself step by step and is then replaced all at once.

```markdown fragment : id="steps"
A fragment reveals itself gradually,

> pause

picking up a second line,

> pause

and then a third.
```

> pause

```markdown overwrite : "steps"
And one overwrite replaces the three of them, inside their box.
```

#>
> section: Python

# Drawings from Python

> grid : [["fig"], ["text"]], vgap=0.5, height_ratios=[1, 1]
> region : "fig", anchor="center"
> add mate figure : "figures/pipeline_detail.py"

> region : "text"

The drawing that opened this deck came from a file like this one: a `Figure` built with the Python API and added with `> add mate figure`. The slide takes the elements themselves, not an image. Colour names from the deck work inside it, and `> modify` can change anything in it that has an id.

# A hidden layer in a figure

> grid : [["fig"], ["text"]], vgap=0.4, height_ratios=[1.7, 1]
> region : "fig", anchor="center"
> add mate figure : "figures/pipeline_layers.py"

> region : "text"

An element built with `set_hidden(True)` holds its box and draws nothing. `> reveal` brings it in and `> hide` takes it out again, and the rest of the drawing stays where it was.

> pause

> reveal : "typst"

# Shapes from a Python block

A `python mate` block runs in the deck, with `self` bound to the presentation:

```text : title="example_deck.md", fontsize=9
for i, name in enumerate(["accent1", "accent2", "dark_gray"]):
    x = -4.6 + i * 4.6
    self.add_element(Circle(0.5, pos=(x, -2.1), fill_color=name))
    self.add_element(Text(name, pos=(x, -2.95), anchor="center"))
```

```python mate
for i, name in enumerate(["accent1", "accent2", "dark_gray"]):
    x = -4.6 + i * 4.6
    self.add_element(Circle(0.5, pos=(x, -2.1), fill_color=name))
    self.add_element(Text(name, pos=(x, -2.95), anchor="center"))
```

#>
> section: Configuration

# The front matter

> grid : [["src", "text"]], hgap=0.6, width_ratios=[1.15, 1]
> region : "src"

```text : title="example_deck.md", fontsize=8
---
templates: [card]
colors:
  accent1: "#b4553c"
  accent2: "#b8891a"
---
```

> region : "text"

The front matter of this file.

- `templates` picks the look, the `card` file next to this one.
- `config` overrides any configuration key.
- `colors` adds palette entries or re-tints the existing ones by name.

# Adjusting the slide count

`> adjust slide count` moves the slide counter. It is useful when a change is long or complex, and duplicating the slide is simpler than using pauses and overwrites. With `> adjust slide count : -1` on the copy, it gets the same number as the original.

> vspace : 0.5

A first take on the idea.

# Adjusting the slide count

> adjust slide count : -1

`> adjust slide count` moves the slide counter. It is useful when a change is long or complex, and duplicating the slide is simpler than using pauses and overwrites. With `> adjust slide count : -1` on the copy, it gets the same number as the original.

> vspace : 0.5

A second take, rewritten by hand. This slide and the one before carry the same number, and the deck's total counts them once.

# From the command line

`mate --help` lists every option. Some of them:

> vspace : 0.5

- `mate --info example_deck.md` lists what this deck can name: the templates, every config key with its value, the palette, the commands, the regions and the fonts that resolve.
- `mate example_deck.md --out build` writes the output to `build/`.
- `mate example_deck.md --png` writes one PNG per page.
- `mate example_deck.md --warn` builds with every check on: regions that overflow, boxes that collide and widow lines (useful for letting an LLM check a deck without looking at every slide).

#

```python mate
config.set("footer.show", False)
```
> region : "full_with_margins", anchor="center"

I hope you find `mate` useful. [[fontsize=14]]

Suggestions and bug reports are welcome. [[color="darker_gray"]]

> vspace : 0.6

github.com/bersp/mate [[color="accent1", fontsize=16]]
