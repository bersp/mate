# Writing mate presentations

A guide for a language model authoring decks with `mate`. It assumes no
knowledge of the codebase and covers the whole authoring surface: deck syntax,
layout, reveals, design defaults, and how to extend the tool when the deck needs
something the current vocabulary does not have.

Run `mate --info deck.md` and read section 2 before writing anything: what a
deck can use (templates, config keys, colors, commands, regions, fonts) is
installation-dependent and is meant to be listed, not remembered.

## 1. The model

A deck is one Markdown file. `mate deck.md` writes `deck.pdf` next to it.

- Content is plain Markdown. `#` opens a slide.
- What Markdown cannot say goes through three extras: `> command` lines,
  `[span][props]` markup, and fenced blocks.
- The look (fonts, colors, background, title design, cover, code style) belongs
  to the template named in the front matter. Content carries no aesthetics:
  restyling a deck is a front-matter edit.
- Python owns every position. Coordinates are centimetres measured from the
  slide centre, x to the right and y up. The slide is 16 x 9 cm by default:
  x runs in [-8, 8] and y in [-4.5, 4.5].

### The loop

1. Run `mate --info deck.md` and read it (section 2). Templates, config keys,
   colors, commands, regions and fonts are installation-dependent.
2. Write the deck.
3. Build with the checks on: `mate deck.md --warn`.
4. Render every page to an image and look at every one of them (section 9).
5. Note every defect in one pass, fix them in a single edit, render again.

Before step 2, the deck needs three things from the user: the material that goes
on the slides, where the images and figures live, and the template. The content
is theirs. Ask when any of the three is missing, and ask again whenever the deck
has a genuinely open choice (a look that departs from the template, a slide
count, a structure). One question costs less than a deck they have to rewrite.

A 25-slide deck of text and images builds in about two seconds (measurements are
cached under `.mate_cache/`, which is safe to delete). Drawings are where the
cost shows: a page carrying a few thousand shapes adds about a second of its own,
and merging repeated shapes into fewer elements is what keeps a generated figure
quick. Build after every change, and read the
error text: mate's errors name the construct that failed and enumerate the valid
values.

## 2. List what varies, do not assume it

One command prints what this installation offers:

```bash
mate --info deck.md
```

The deck's front matter is applied first, and the listing carries, in order: the
built-in templates and the ones the deck loads, every config key with its
current value, the palette, the commands, the regions of the layout, the font
families that resolve, and the API names a `> add` line or a `python mate` fence
can name. `mate --info` alone prints the same listing for a deck with no front
matter.

**A name outside that listing does not exist.** A config key, a color, a
command, a region, a font family or an element invented by analogy raises at
build time. Print the listing and pick from it.

Templates written for a deck are `.py` files sitting next to the Markdown file;
a front-matter entry resolves to a sibling `<name>.py` when one exists and to a
built-in name otherwise. The listing names both kinds.

Two things the listing cannot carry, read from the template file itself: the
`<template>.<key>` keys it reads with a default it never sets, and the `#>`
directive properties it acts on. A property no template reads is ignored without
a word.

```bash
grep -n "def \|config.get\|colors.set_multiple\|directive.get" <template>.py
```

`font_paths` in the front matter adds directories of font files to the set of
families that resolve (section 10).

### Reading the source

Read the installed package, not GitHub: it is the copy that builds the deck.

```bash
python -c "import mate, pathlib; print(pathlib.Path(mate.__file__).parent)"
```

| question | file |
|---|---|
| what a command does and what arguments it takes | `core/template.py` |
| every config key and its default, and the palette | `config.py` |
| an element's constructor arguments and its setters | `elements/<type>.py` |
| deck syntax: front matter, directives, blockquotes, fences | `parser/markdown.py` |
| regions, grids, anchors | `composition/layout.py` |
| worked templates | `templates/` |

Docstrings answer most questions without opening a file:

```bash
python -c "import mate; help(mate.Text)"
python -c "from mate.core.template import PresentationTemplateBase as B; help(B.add_image)"
```

When that path sits inside a git checkout (an editable install), the repository
root also holds `ARCHITECTURE.md`, which documents the internals, and
`docs/README.md`, the user-facing reference.

## 3. Deck anatomy

```markdown
---
templates: [flow]
config:
  text.fontsize: 10
colors:
  accent: "#B5557A"
---

#>
> cover: True
> title: The talk title
> author: Name Surname
> date: March 2026

# First slide
## Optional subtitle

Body text.

# Second slide

More body text.
```

**Write `templates: [flow]` unless the user names another one.** A front matter
without a `templates:` entry builds on the bare base: no background, no cover
design, no title treatment. `flow` is the deck's starting look whenever the user
states no preference. Section 2 lists the alternatives, and section 10 covers
switching or writing one.

Order of the pieces:

1. **Front matter** (optional, opens the file): `templates`, `config`,
   `colors`, `font_paths`. Front-matter values override template values.
2. **Directives** (`#>` plus a blockquote of `key: value` lines): off-slide
   instructions handed to the template between slides.
3. **Slides**: everything from one `#` heading to the next.

The file opens with a `#` heading or a directive. A paragraph before the
first slide raises.

`##` is the slide subtitle only when it is the first block of the slide.
Elsewhere `###` to `######` are in-body headings styled by the `h3` to `h6`
roles; a `##` that is not the subtitle also renders with `h3`.

A title is a `Text` like any other: `**bold**`, `[span][props]` and `$math$` work
inside it. A template that rewrites the title string rewrites that markup with
it, where a span raises and math comes out in the wrong case; a template changing
the case of a title passes `case="upper"` to the `Text`, which transforms the
literal words and leaves the markup alone.

## 4. Commands

A blockquote line calls a method of the presentation:

```markdown
> name : python, arguments=here
> name
```

Spaces in the name become underscores (`> add image` calls `add_image`).
Arguments are evaluated as Python with the whole `mate` API in scope. One line
is one call; a blockquote can hold several.

### Aliases: always write the short form

| write | not |
|---|---|
| `> add` | `> add element` |
| `> vspace` | `> add vspace` |
| `> grid` | `> create grid` |
| `> region` | `> set active region` |

### The commands used while writing a deck

| command | arguments |
|---|---|
| `> pause` | none. Opens a reveal step |
| `> vspace : 0.5` | `height`, `region="active"` |
| `> region : "left"` | `name`, `anchor=None` (the anchor override lasts for this slide) |
| `> grid : [["l", "r"]]` | `template`, `region="active"`, `hgap`, `vgap`, `width_ratios`, `height_ratios`, `anchors` |
| `> add image : "f.png"` | `path`, `region`, `floating`, `width`, `height`, plus `align`, `crop`, `id`, `pos`, `anchor`, `z_order` |
| `> add mate figure : "f.py"` | `path`, `region`, `floating`, `pos`, `anchor`, plus `align`, `id`, `z_order` |
| `> add : Circle(0.5, pos=(0, 1))` | `element`, `region=None` (no region means the element floats at its own `pos`) |
| `> add text : "words"` | `text`, `region`, `floating`, `align`, plus any `Text` keyword |
| `> modify : "id", color="red"` | `id`, then any property with a setter |
| `> mask image : "id"` | `id`, `x=0`, `y=0`, `width=1`, `height=1` (fractions) |
| `> unmask image : "id"` | `id` |
| `> draw layout` | `regions=None`, `stroke_width=0.03`. Debug overlay of the region map |

`width` and `height` on an image are centimetres, or a `"<n>%"` string. The
percentage on `width` is that fraction of the region's **width** and on `height`
that fraction of its **height**; the side left free follows the file's aspect
ratio and can run past the region without a word. With neither given the image
fills the region, all of it, and anything stacked after it lands outside.

## 5. Text, math, lists, code

### Styling spans

Markdown's link syntax carries properties in the second bracket pair, written as
Python keywords:

```markdown
A [red word][color="red"] and [a smaller, faded one][fontsize=8, opacity=0.4].

This whole paragraph is gray. [[color="gray", fontsize=9]]
```

`[[...]]` anywhere in a block applies to the whole block. Spans nest, and they
work inside math.

| property | example |
|---|---|
| `color` | `color="red"` (palette name or hex) |
| `opacity` | `opacity=0.4` |
| `fontsize` | `fontsize=8` (points) |
| `font` | `font="Lato"` |
| `weight` | `weight="bold"` or `weight=600` |
| `style` | `style="italic"` |
| `letter_spacing` | `letter_spacing=0.15` (em) |
| `align` | `align="center"` (places the block in its region) |
| `text_align` | `text_align="center"` (aligns wrapped lines inside the block) |
| `shift` | `shift=(0.1, 0.3)` (cm) |
| `rotate` | `rotate=15` (degrees counterclockwise) |
| `scale` | `scale=1.3` |
| `id` | `id="key"` or `id=1` |
| `z_order` | `z_order=-1` |

The property name resolves to `set_<name>` on the element: any setter an
element type defines is a valid property. An unknown one raises with the
element's name in the message.

Several of these are methods on the element, not constructor arguments:
`Text("x", rotate=90)` raises, `Text("x").rotate(90)` works. The same holds for
`shift` and `scale`.

### Math is Typst, not LaTeX

`$x^2$` is inline math inside a line of text. `$$ ... $$` is display math and
takes lines of its own, delimiters included:

```markdown
The inline form $x^2 + y^2 = r^2$ sits in the running text.

$$
integral_0^oo e^(-x^2) dif x = sqrt(pi) / 2
$$
```

A display equation is centered. The `math.align` config key moves every equation
in the deck; a `[[align="left"]]` inside one moves that one:

```markdown
$$
x(t) = x_0 e^(-t / tau) [[align="left"]]
$$
```

The body is [Typst math](https://typst.app/docs/reference/math/), and LaTeX
habits fail silently or raise.

| intent | Typst |
|---|---|
| fraction | `frac(a, b)`, `a / b`, `(dif E) / (dif t)` (the parentheses group and do not print) |
| literal slash | `\/` (a bare `/` builds a fraction) |
| integral, sum | `integral_0^oo`, `sum_(i=1)^n` |
| greek, operators | `epsilon`, `partial`, `approx`, `prop`, `->`, `=>`, `oo` |
| accents | `hat(beta)`, `overline(x)`, `dot(q)` |
| bold upright symbol | `bold(upright(x))` |
| words inside math | `"cte"`, `"Re"_lambda` |
| spacing | `thin`, `quad`, `wide` |
| calligraphic | `cal(L)` |
| delimiters | `angle.l u angle.r`, `abs(x)`, `norm(x)`; `lr(...)` grows them to their content |

Macros go in the front matter, prepended to every generated document:

```yaml
config:
  typst.preamble: |
    #let vb(x) = math.bold(math.upright(x))
```

Raw Typst is allowed inside math (`#box(stroke: 0.5pt, inset: 5pt)[$ ... $]`).

Body text passes through Typst's markup: `---` renders an em dash, `--` an en
dash, `~` a non-breaking space, and straight quotes turn curly. A trailing
backslash is a hard line break.

### Lists

Standard Markdown. Nesting picks the next bullet symbol from
`list.bullet.symbols`. A list item can hold further blocks (paragraphs, images,
math, `> pause`) indented under it, and they land in the item's text column.

### Code

````markdown
```python : title="solver.py", numbers=True
def f(x):
    return x**2
```
````

The language is a Pygments lexer name; a fence with no language renders plain.
Options follow the language after a `:` and are Python keywords. The valid set
depends on the `Code` class the loaded template uses, and an unknown option
raises with the full list; try one and read the error.

Common options: `title`, `numbers`, `numbers_start`, `bg_color`, `fontsize`,
`padding`, `corner_radius`, `width`, `region`, `words={"x": {"color": "red"}}`,
`theme={"keyword": {"color": "red"}}`.

The `theme` roles are `keyword`, `string`, `comment`, `number`, `function`,
`builtin` and `decorator`. An entry replaces that role's properties and the
roles left out keep the deck theme; a key that is none of the seven is ignored
without a word.

Inside a fence everything is verbatim except two constructs: `[body][props]`
spans (only when the second bracket reads as keyword properties; `a[i][j]`
stays code) and `||` reveal markers. `\||` writes a literal `||`.

## 6. Layout

Every element is either stacked in a region or floating at a fixed position.
The region is the default: a stacked element is placed when the slide is
arranged and follows the content above it when that changes, and a floating one
keeps the coordinates it was given. Floating is for the cases where the position
is the point (a stamp in a corner, a label on a drawing), not a way to take
control of an ordinary block.

The default layout carries `title`, `footer`, `left_margin`, `right_margin`,
`content` (active by default), `full` and `full_with_margins`. A template adds
and resizes regions, and the REGIONS block of `mate --info deck.md` prints the
centre, size, anchor and gap of every one the deck has.

On a default 16 x 9 slide, `content` is 14.6 cm wide and 6.5 cm tall, spanning
x [-7.3, 7.3] and y [-4.0, 2.5], anchored `top-left` with a 0.25 cm gap. Those
are the numbers to size things against, and a template changes them.

A region stacks its content from its anchor, top to bottom, with `arrange_gap`
between elements. The nine anchors are `top-left`, `top-center`, `top-right`,
`center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`,
`bottom-right`.

### Grids

```markdown
> grid : [["text", "fig"]], hgap=0.6, width_ratios=[1, 1.2]
> region : "text"

The left column.

> region : "fig", anchor="center"
> add image : "setup.png", width="100%"
```

The template is rows by columns with row 0 on top. Cells sharing a label merge
into one region. Every content command also takes `region=`: a single element
goes elsewhere without switching the active region.

```markdown
> grid : [["head", "head"], ["left", "right"]], vgap=0.3, height_ratios=[1, 3]
> add image : "a.png", region="left"
> add image : "b.png", region="right"
```

`> draw layout` overlays the region map with labelled outlines while tuning
gaps and ratios. Remove it before finishing.

### Floating

`floating=True` detaches content from the stack: it sits with its `anchor` at
`pos`. Setting `pos` or `anchor` without `floating=True` raises.

```markdown
> add image : "stamp.png", width=2, floating=True, pos=(6, 3.5), anchor="top-right"
```

A whole run of content floats the same way:

````markdown
```markdown fragment : floating=True, pos=(0, -3.4), anchor="bottom-center"
A note pinned near the bottom edge. [[color="dark_gray", fontsize=9]]
```
````

An element added with `> add` floats at its own `pos` unless a region is named.

### Draw order

Every element of a slide is placed on its own and the whole set is sorted
together by `z_order`: higher covers lower, ties keep insertion order, and
everything starts at 0. A value set on a group cascades to every descendant that
carries none, so a `z_order` on a nested group wins over a sibling added after
it. A label coming out under an arrow drawn later is fixed by a `z_order` on the
label or on the group holding it.

## 7. Revealing content

A slide compiles to one page per reveal step, each showing everything
accumulated up to that step. Positions are computed once over the full slide;
revealing never moves what is already visible.

- `> pause` opens a step.
- `||` inside a text, an equation or a code fence splits it into pieces that
  arrive one step at a time, with the space reserved from the start. `\||`
  escapes it.
- `> modify : "id", <props>` restyles or moves every element carrying that id,
  from its step onward. Ids are per slide; the same key is free again in the
  next slide.
- `set_hidden(True)` reserves the element's box and draws nothing. It is how a
  layer built in Python inside a figure waits for its step:
  `> modify : "id", hidden=False` brings it in with the room held from the first
  step and the rest of the drawing still. `opacity` is a different knob,
  writing `fill_opacity` alone: it leaves a stroke visible and, set back to 1,
  fills a shape that was drawn as an outline.
- `> mask image : "id", x=0.2, y=0.3, width=0.4, height=0.5` shows a window of a tagged
  image while the picture holds its place; `> unmask image : "id"` restores it.
  (`crop=` on `> add image` is different: it draws a different picture, and the
  layout sizes that piece alone.)

Three fences treat a run of content as one unit:

````markdown
```markdown fragment : id="block", region="side", color="gray"
Grouped content: an id for later targeting, a region, or any span property.
```

```markdown overwrite : "block"
Replaces the tagged block inside its own box; nothing around it moves.
```

```markdown alternate
> add image : "step1.png", height="70%"
> alt
> add image : "step2.png", height="70%"
```
````

An `alternate` reserves the height of its tallest variant; content below it
never moves. Each `> alt` opens a reveal step, a `> pause` inside a variant
reveals that variant cumulatively before the next one takes over, and a block
written after the fence lands in the last variant's step.

## 8. Drawings and Python

Read this section when the deck needs a drawing built in Python. A deck of text,
images and ready-made figure files needs nothing from here.

Python owns every coordinate here: a shape is an object placed by hand, in
centimetres from the slide centre. One element goes in a `> add` command, a
longer construction in a `python mate` fence, and a reusable drawing in a figure
file of its own.

```markdown
> add : Rectangle(1.7, 1.1, pos=(-1.4, -1.6), corner_radius=0.15, fill_color="accent")
> add : Arrow((3.6, -1.6), (5.6, -1.6), stroke_color="dark_gray")
```

### The elements

| element | positional arguments | notes |
|---|---|---|
| `Rectangle(w, h)` | width, height in cm | `corner_radius=` is one float or a dict keyed `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"` |
| `Circle(r)` | radius | the box is `(2r, 2r)` |
| `Ellipse(w, h)` | width, height | the semi-axes are `w / 2` and `h / 2` |
| `Line(start, end)` | two points | stroke only; `stroke_width` defaults to `line.stroke_width` |
| `Polygon(points)` | three points or more | filled and closed |
| `Curve(segments)` | segments, the first a `MoveTo` | `MoveTo(p)`, `LineTo(p)`, `CubicTo(c1, c2, p)`, `QuadTo(c, p)`, `Close()` |
| `Arrow(start, end)` | two points | `tip=` and `tail=` take `TriangleTip()`, `HookTip()` or `BarTip()`; with none given the tip is the marker `arrow.tip` names |
| `Text("words")` | the source string | the markup of section 5 works here |
| `Image("f.png")` | the path | `width=` / `height=` in cm, `crop=(x, y, w, h)` in fractions of the file |
| `Group([...])` | the children | takes `anchor=`, never `pos=` |
| `VSpace(h)`, `HSpace(w)` | the size in cm | draws nothing and holds a box |

`Rectangle`, `Circle`, `Ellipse`, `Text` and `Image` sit at a `pos=` with an
`anchor=`, one of the nine names in section 6. `Line`, `Polygon`, `Curve` and
`Arrow` carry their geometry as points in the frame they are added to and take
neither: the points are the position, and `move_to` relocates one. Every element
takes `id=` and `z_order=`.

### Style

| field | values | default |
|---|---|---|
| `fill_color` | palette name, hex, or a `Gradient` | black |
| `fill_opacity` | 0 to 1 | 1 |
| `stroke_color` | palette name, hex, or a `Gradient` | black |
| `stroke_width` | cm | 0, which draws no stroke |
| `stroke_opacity` | 0 to 1 | 1 |
| `stroke_dash` | `"solid"`, `"dotted"`, `"dashed"`, `"dash-dotted"`, each with a `densely-` and a `loosely-` variant, or a list of lengths in cm | solid |
| `stroke_cap` | `"butt"`, `"round"`, `"square"` | Typst's |
| `stroke_join` | `"miter"`, `"round"`, `"bevel"` | Typst's |

The default is a solid black fill with no stroke; an outline is
`fill_opacity=0, stroke_width=0.05`. `Line` and `Arrow` fill nothing and take
the stroke fields alone.

A `Text` carries them too, and Typst paints the stroke over the glyph. A label
with a white outline behind it is two copies of the text at the same position,
the back one filled and stroked in the outline colour; the stroke leaves glyph
metrics alone and both copies measure the same.

Each field has a setter (`set_fill_color("red")`, `set_stroke_width(0.04)`) that
writes every descendant carrying the field; `propagate=False` writes the node
alone. `set_color` writes fill and stroke together, and `set_opacity` writes
`fill_opacity` by itself.

A gradient goes anywhere a colour does. Stops are palette names or hex, each
optionally paired with a position:

```python
Gradient.linear("accent", "white", angle=45)
Gradient.radial(("white", 0), ("black", "80%"), center=(0.5, 0.5), radius=0.6)
```

### Placing

| call | what it does |
|---|---|
| `move_to(p)` | puts the element's anchor point at `p`, the subtree following |
| `shift(d)` | translates by `d`, accumulating over calls and surviving a region's `arrange` |
| `next_to(target, side, align=, gap=)` | puts this box against another element's box, or against a point |
| `set_anchor(a)` | changes which point of the box sits at `pos` |
| `rotate(angle, pivot=None)` | degrees counterclockwise, rigid over the subtree |
| `scale(factor, origin=None)` | rigid and compounding; `set_scale(factor)` is the absolute form |

`next_to` is what places a label without hand-tuned coordinates. The two
bounding boxes meet, `align` slides the element along the shared side
(`"left"`, `"center"`, `"right"` on `"top"` and `"bottom"`; `"top"`,
`"center"`, `"bottom"` on `"left"` and `"right"`), and `gap` defaults to
`arrange.gap`. The element's own anchor plays no part and is left alone.

```python
fig.add(Text("inflow").next_to(box, "left", align="top", gap=0.2))
```

### Measuring

| call | returns | cost |
|---|---|---|
| `get_bbox()` | `(centre_x, centre_y, width, height)` in cm | one Typst query on a cache miss |
| `get_anchor_point(anchor)` | that point of the box | the same |
| `get_width()`, `get_height()` | the extents | free on a shape, which knows its size; measured for text, images and groups |
| `center` | the box centre | free for a fixed element anchored `"center"` |
| `measure_all([...])` | nothing, and fills the caches | one pass for the whole list |

The edges come from the box: `left = x - w / 2`, `top = y + h / 2`. Measurement
is the slow half of a build and sizes are cached on disk between runs; ask for a
box when the drawing needs one, and call `measure_all` ahead of a loop that would
otherwise ask element by element.

### Ids, hiding and draw order

`id="key"` on any element registers it, and `> modify : "key", <props>` restyles
or moves everything carrying that key from its reveal step onward.
`set_hidden(True)` holds the box and draws nothing, which is how a layer waits
for its step. `z_order` sorts the whole slide and cascades from a group to the
descendants that carry none.

### Grouping and stacking

A `Group` is a tree node whose box is the union of its children's. It has no
body of its own, which makes its fill and stroke fields bulk setters over the
subtree, and it moves as a unit.

`arrange(elements, pos, anchor, gap=0.0, width=None)` stacks a list from top to
bottom and anchors the stack as a whole. It is what a region runs internally,
and it is available for a column built inside a drawing.

A region is reachable from a fence when a drawing is placed against the layout:
`self.layout.get("content")` carries `center`, `left`, `right`, `top`, `bottom`
and `get_anchor_point(anchor)`.

### Running Python in a deck

A longer construction goes in a `python mate` fence, which runs with the `mate`
API in scope and the presentation as `self`. The namespace persists across
fences in the deck.

````markdown
```python mate
W = config.slide_width
for i, name in enumerate(["red", "green", "blue"]):
    self.add_element(Circle(0.5, pos=(-W / 3 + i * W / 3, -2.7), fill_color=name))
```
````

The fence runs at its position in the slide, which makes it the way to change a
setting partway through a deck:

````markdown
```python mate
config.set("text.fontsize", 8)
self.layout.get("content").set_anchor("center")
```
````

The two lines above differ in reach:

- A `config` value is read by each element as it is built: the change applies to
  the content after the fence and holds for the rest of the deck (the config is
  process-global). Write the old value back when the change is meant for one
  slide.
- A region's anchor, size or gap is read when the slide is arranged, at the end
  of the slide: the change applies to the whole slide, content above the fence
  included, and it resets when the next slide opens. `set_anchor_default` makes
  it the deck's default instead.

### Figure files

A reusable drawing belongs in a file of its own, holding exactly one
module-level `Figure`:

```python
from mate import Figure, Rectangle, Text

fig = Figure()
box = fig.add(
    Rectangle(3.4, 1.2, fill_opacity=0, stroke_color="gray", stroke_width=0.035)
)
fig.add(Text("label").next_to(box, "top"))

if __name__ == "__main__":
    fig.write("scene.pdf")
```

`> add mate figure : "scene.py"` embeds it. It arrives as elements, not a
picture: palette names resolve against the deck and ids inside the file answer to
`> modify`. Run the file directly to preview it as a standalone PDF.

The collision check runs on that preview when the guard turns it on, naming the
labels that cross while they are being placed:

```python
from mate import config

if __name__ == "__main__":
    config.set("warn.collisions", True)
    fig.write("scene.pdf")
```

### Composing a drawing

- A group stacked in a region is placed by the region, and `set_align("center")`
  decides where it sits across the region's width.
- Derive positions from a few named constants and stack with
  `arrange(elements, pos, anchor, gap=...)`. Shared baselines and even gaps are
  most of what makes a drawing read as deliberate; eyeballed offsets read as
  noise.
- Attach the labels with `next_to` and keep written coordinates for the few
  things whose position is the point.
- Label the arrows. `writes`, `every 30 s`, `x 3` carries information; a bare
  arrow means "related somehow".
- Keep a label to a word or three and leave the explanation to the caption.
- One hue carries the meaning and the rest of the drawing stays neutral.

## 9. Putting a slide together

Patterns for the slides that come up most, and the defaults to fall back on. An
instruction from the user wins over anything here. The content is the user's:
text, images and figures come from them, and this section is about placing what
they give. Produce a figure only when asked for one.

**Leave the defaults alone until they fail.** `> grid : [["text", "fig"]]` splits
a region evenly, an image with no size fills what it is given, a region stacks
from its own anchor. Add `width_ratios`, an explicit `width`, an `anchor` or a
floating `pos` when the default comes out visibly wrong, one argument at a time.
An argument written by habit is one more value to keep in sync when the content
or the template changes.

**Show the tools the deck has.** Unless the user asks otherwise, open a deck with
a cover directive, and use the structural devices the loaded template supports
(a running section, a section cover, a theme switch) where the talk changes
subject. Which properties exist is template-dependent: `cover`, `title`, `author`
and `date` are handled by the base, everything else is read by the template;
grep it for `directive.get` before writing a property. A property no template
reads is silently ignored.

**One idea per slide.** A title and a body that fits. Splitting a slide in two
keeps the text at the size the rest of the deck uses.

**Reveal in steps when the slide argues something.** A list of consequences, a
derivation, a before-and-after comparison: `> pause` between the parts. A slide
that is a single figure or a single statement needs no steps.

**A figure gets a caption.** The image and the caption stack in the active
region, one after the other, with the caption styled down and centred under a
centred image:

```markdown
> add image : "figures/result.pdf", height="80%"

Energy spectrum against wavenumber. [[fontsize=7, color="dark_gray", align="center"]]
```

Size a figure that carries a caption on `height`. A `width` of 14.6 cm is 6.5 cm
tall only for a file wider than 2.25:1, and a plot is usually nearer 1.4:1, which
comes out 10 cm tall on a 9 cm slide. The image, the 0.25 cm gap and the caption
share the region's 6.5 cm.

**Figure plus commentary goes in a grid**: the text gets its own column and the
figure keeps its size.

```markdown
> grid : [["text", "fig"]], hgap=0.6
> region : "text"

- What to look at first.
- What it means.

> region : "fig", anchor="center"
> add image : "figures/result.pdf"
```

Anchor a cell holding a lone figure at `"center"`, either through
`anchors={"fig": "center"}` on the grid or when switching to it.

**A run of slides that varies one thing keeps its geometry.** Consecutive slides
showing a figure at two zoom levels, or an equation gaining terms, read as one
thought when the title, the grid and the image size stay identical and only the
varying part moves. A shared title alone is not that case: two slides can carry
the same title and hold different material. `markdown alternate` collapses such a
run into a single slide; reach for it when the variants are short and the source
stays legible, and keep separate slides otherwise. Someone reads the deck file
itself, and that comes before compactness.

**A slide holding one equation or one line gets its region anchored.**
`> region : "content", anchor="center"` centres it for that slide, and
`"center-left"` centres it vertically while the text stays left-flush. A
`> vspace` at the top of a `top-left` region pushes the content down without
balancing it.

**A bold lead line frames the body** when the title alone does not. `##` is the
slide subtitle, right under the title; an in-body lead is a bold paragraph of its
own.

**`> vspace` sets the separation where the region's gap is wrong.** The spacer
replaces the region's usual gap at that point, it does not add to it. Reach for
it around equations, before a closing statement, and between a figure and its
caption. The spacer replaces the gap: a value at or below the region's
`arrange_gap` (0.25 cm in `content`) changes nothing at all. A spacer is an
element of the stack: one left at the end still counts toward the stack's
height, which shows up when the region is anchored at its centre or its
bottom.

**Sizes come from the role keys.** `text.fontsize`, `title.fontsize` and the
other role keys carry the deck's sizes, and a `fontsize=` on a span is for one
genuine exception. When most slides want smaller text, change the role key in the
front matter once instead of tuning block by block.

**Emphasis is the author's call, not a default.** Inside the running text, write
plain: no color and no bold unless one word genuinely carries the point (the lead
line above is a structural device, not emphasis). A plain deck is one request
away from the emphasis its author wants; a colored one has to be undone first.

**Colors come from the palette by name** (`color="red"`, `color="accent"`), never
as a hex literal inside a slide. A hex belongs in the front matter `colors:`
block, under a name.

**Turn the checks on while building the deck.** Three of them, each off by
default, each naming the slide as the deck builds:

| key | what it reports |
|---|---|
| `warn.overflow` | a region holding more than it fits |
| `warn.collisions` | two drawn boxes crossing: a label over a stroke, a label over a label |
| `warn.widows` | a paragraph whose last line carries `warn.widow_min_words` words or fewer (3 by default) |

`mate deck.md --warn` turns on all three for one build, which is how to run them
while writing. The front matter is for a check left on:

```yaml
config:
  warn.overflow: true
```

The collision report compares bounding boxes, so a diagonal arrow reports
against the rectangle it spans, and a box holding another (a label inside a
shape, the slide background) is never reported. The widow report reads the
prose: titles, covers, code, equations and a paragraph broken by hand are left
out.

**Look at the pages before handing the deck over.** The checks catch what they
name and nothing else: an image that pushes its caption off the slide, a wide
equation reaching into the margin, a long title crowding the body. Render every
page to an image and open every one of them:

```bash
pdftoppm -png -r 150 deck.pdf /tmp/deck_page    # /tmp/deck_page-01.png, ...
```

Reading the images is the step, not rendering them. At 150 dpi a 16 x 9 cm slide
comes out 945 px wide, which is where a 7 pt caption stays legible; 80 dpi is
small enough to hide the defect being looked for.

Render every page at once, note every defect in one pass, fix them in a single
edit, and render once more to confirm. Chasing one defect per rebuild costs
several times as much. Every reveal step is a page someone sees: check that the
first one is not blank and the last one is not crowded.

### A deck end to end

One file carrying the pieces above: a cover directive, a subtitle, reveal steps,
a grid holding a figure, an anchored region and a captioned equation. It builds
without a warning.

```markdown
---
templates: [flow]
config:
  text.fontsize: 11
colors:
  accent: "#B5557A"
---

#>
> cover: True
> title: Mixing in a stratified layer
> author: Name Surname
> date: March 2026

# What the runs measure

## Two regimes, one control parameter

- Above Ri = 0.25 the buoyancy flux saturates.

> pause

- Below it the layer overturns within one eddy turnover.

> pause
> vspace : 0.5

The transition is what the next slide isolates. [[color="accent"]]

# The spectrum

> grid : [["text", "fig"]], hgap=0.6, width_ratios=[1, 1.2]
> region : "text"

- Energy peaks at the forcing scale and decays steadily below it.
- The slope holds in both runs.

> region : "fig", anchor="center"
> add image : "figures/spectrum.png", width="100%"

# The balance

> region : "content", anchor="center"

$$
(dif E) / (dif t) = P - epsilon - B
$$

> vspace : 0.6

Production feeds the range, dissipation and buoyancy drain it. [[align="center", color="dark_gray", fontsize=9]]
```

## 10. Changing the look

Read this section when the deck's look is what the task is about. A deck that
takes the template it names as it comes needs nothing from here.

Three levels, in order.

**1. Front matter, for anything that is already a config key or a palette
color.** This is the answer for font sizes, slide size, footer visibility, bullet
symbols, code style, and re-tinting any color:

```yaml
---
templates: [<name>]
config:
  text.fontsize: 10
  math.fontsize: 10
  footer.show: false
colors:
  red: "#A8483F"
  accent: "#5B3A86"
---
```

An undefined key raises and the message lists every defined one. A template also
publishes keys in its own namespace (`<template>.<prop>`), which the front matter
can set.

### Fonts

Each typographic role carries its own family, and the `.font` keys of
`mate --info` are the roles: `text`, `title`, `subtitle`, `h3` to `h6`,
`cover.title`, `cover.author`, `math` and `code`. Changing the deck's type is a
front-matter block:

```yaml
config:
  text.font: Lato
  title.font: Playfair Display
  math.font: New Computer Modern Math
```

Every role but `code` also carries `<role>.fontweight`, which takes `"regular"`,
`"bold"` or a number (`700`). A single word or line takes `font=` in a span
(section 5) and leaves the deck alone.

The FONTS block of `mate --info` is the whole set of families that resolve, and
naming one outside it raises at build time with the set listed. `font_paths`
adds directories of font files (`.ttf`, `.otf`) to that set, expanding a leading
`~` and otherwise relative to the Markdown file:

```yaml
font_paths: [~/.local/share/fonts, ./assets/fonts]
```

A font a template names is a config value like any other: the front matter
overrides it without touching the template.

**2. A different template**, when the user asks about aesthetics. `flow` is the
default; the other built-in templates are starting points to offer, not solutions
to a specific layout problem. Templates stack: `templates: [mine, base]` inherits from both, and the
earlier entry wins where the two define the same thing.

**3. A template file next to the deck**, for everything else: a background, a
cover design, a title treatment, a new command, a restyled code block, a new
region map. Write `my_template.py` beside the Markdown file and list it as
`templates: [my_template]`.

Asked for a template with nothing else stated, keep the structure and the design
language of the one it starts from (`flow` unless the user names another) and
take the theme from the deck's subject: the palette, the cover, the background
motif, the title treatment. A talk on ocean turbulence and a talk on compiler
internals come out of the same skeleton with different colors and a different
cover. When the subject suggests no particular direction, or when the design
wants a structure the base template does not have, ask the user which way to go.

### Writing a template

```python
from __future__ import annotations

from mate import Group, PresentationTemplateBase, Rectangle, config


class PresentationTemplate(PresentationTemplateBase):
    def setup(self) -> None:
        """Declare colors and config knobs."""
        config.colors.set_multiple(
            {
                "my_template.paper": "#FAF8F2",
                "my_template.accent": "#1E7A4C",
            }
        )
        config.set_multiple(
            {
                "text.font": "Lato",
                "title.color": "my_template.accent",
                "footer.show": False,
            }
        )

    def setup_layout(self) -> None:
        """Adjust the regions built from the resolved configuration."""
        self.layout.get("title").adjust_borders(bottom=-0.5)

    def background(self) -> Group:
        """Return the element drawn behind every slide."""
        W, H = config.slide_width, config.slide_height
        group = Group(anchor="top-left")
        group.add(Rectangle(W, H, fill_color="my_template.paper"))
        return group
```

Rules that come from the machinery:

- The class is named `PresentationTemplate` and subclasses
  `PresentationTemplateBase`. It defines no `__init__` and calls no `super()`
  for the hooks; construction runs `setup()`, then the front matter, then
  `build_layout()`, then `setup_layout()`.
- Config and colors go in `setup()`. The front matter is applied after it:
  deck values win over template values.
- A template's own colors and config keys are namespaced with the template's
  name (`my_template.accent`), which lets a deck re-tint them and keeps stacked
  templates from colliding. The template name cannot collide with a core config
  namespace.
- Config values that are colors take palette names, not hex. Hex literals belong
  in the palette declaration.
- A template overrides only what it exists to change. The rest is inherited: do
  not copy a sibling template's whole config dict.
- A hook that also wants the base behaviour calls `super()` explicitly
  (`on_directive` typically does).

Hooks worth knowing, all optional:

| hook | purpose |
|---|---|
| `setup` | colors, config keys, bullet symbols (`self.bullet_symbols["name"] = builder`) |
| `build_layout` | replace the region map |
| `setup_layout` | adjust or extend the regions built by `build_layout` |
| `background` | the element drawn behind every slide (branch on `self.current_slide.is_cover`) |
| `add_title` | the title design (an eyebrow line, uppercase, tracking) |
| `add_cover` | the cover design, from `title` and the directive properties |
| `add_footer` | the footer |
| `on_directive` | act on `#>` properties: a running section, a theme switch, a section cover |
| `add_code` | build a `Code` subclass instead of the default block |

Every public method is callable from the deck as a command: a new command is a
method.

```python
    def full_center_layout(self) -> None:
        """Make the full-slide region active, centered."""
        self.layout.set_active("full_with_margins").set_anchor("center")
```

```markdown
> full center layout
```

A method named `add_<name>(self, blocks, args)` becomes a new fenced block,
reached as ```` ```markdown <name> : args ````. `args` is the fence's verbatim
property text and `blocks` its parsed body:

```python
from mate.core.authoring import eval_props
from mate.parser import BulletList, Paragraph, inlines_to_markdown


class PresentationTemplate(PresentationTemplateBase):
    def add_note(self, blocks: list, args: str) -> None:
        """Render a ``markdown note`` body as an aside in the note style."""
        props = {"color": "my_template.accent", **eval_props(args)}
        for block in blocks:
            match block:
                case Paragraph(inlines):
                    el = self.add_text(inlines_to_markdown(inlines))
                    for name, value in props.items():
                        el.apply_prop(name, value)
                case BulletList():
                    self.add_bullet_list(block)
                case _:
                    self._dispatch_block(block)
```

Two vocabularies meet here. A fence's properties are markup names, the ones from
the span table, and `apply_prop(name, value)` is what applies one to an element.
The content methods forward their keyword arguments to a constructor instead,
where the same colour is `fill_color`.

The block types come from `mate.parser`: `Paragraph.inlines`, `BulletList.items`,
`ListItem.blocks`, `MathBlock`, `MethodCall`, plus `inlines_to_markdown` to turn
inlines back into the Markdown a content method takes. `CodeBlock(language,
options, source)` and the other fence types live in `mate.parser.ir`.
`self._dispatch_block(block)` renders any block the way the deck itself would,
which is the fallback for everything the fence does not treat specially.

A directive property the template acts on is read in `on_directive`, which owns
the slides it makes:

```python
    def on_directive(self, directive) -> None:
        """Open a section cover on ``section:``, then run the base handling."""
        section = directive.get("section")
        if section is not None:
            self._section = section          # state initialised in setup()
            self.new_slide(is_cover=True)
            self.current_slide.add(Text(section, fontsize=24))
            self.end_slide()
        super().on_directive(directive)
```

`new_slide(is_cover=True)` and `end_slide()` are the pair that builds a slide
from a hook. The `super()` call keeps the base behaviour, which handles
`cover: True` and ignores every property no template reads.

To restyle code blocks, subclass `Code`, replace `build()`, and override
`add_code` to instantiate it. `build()` owns the whole geometry and returns every
element the block draws, in a frame whose origin is the block's top-left corner,
which makes copying it the way to start: take the whole method from
`elements/code.py`, or from a built-in template that already subclasses `Code`,
paste it into the deck's template and edit the copy.

```python
    def add_code(self, source, language="", options="", region="active", **code_kwargs):
        target_region, kwargs = self.resolve_code_options(
            options, region, code_kwargs, MyCode
        )
        el = MyCode(source, language=language, **kwargs)
        el.indent = self._content_indent
        self.current_slide.add(el)
        target_region.add(el)
        return el
```

Passing the subclass to `resolve_code_options` makes its own constructor
parameters valid fence options.

## 11. Traps

Failure modes verified against the current code, split by what the build does.

### Silent: the build exits clean and the deck is wrong

These are the ones to check by reading the file and the rendered pages.

- **A fence inside a fence needs more backticks than the one it sits in.** A
  three-backtick block holding another three-backtick block ends at the inner
  one, and everything after it, slides included, is swallowed as its content
  without a word. The build succeeds with the slides simply gone. Use four
  backticks outside, and count the slides in the build log.
- **`$$ ... $$` written inside a paragraph line is not display math**: it comes
  out as inline math flanked by literal `$`. The delimiters take their own lines.
- **A `||` inside an emphasis pair breaks it.** `**bold with || a marker**`
  renders its asterisks literally. Keep the marker outside the emphasis.
- **Math is Typst.** `\frac{a}{b}` is not a fraction, and a bare `/` inside math
  builds one where a literal slash was meant (`\/`).
- **A bracket pair inside a code fence becomes a span** when the second bracket
  parses as keyword properties. Real code rarely does, but `[x][color="red"]`
  inside a fence is markup, not code.
- **A `code.theme` role outside the seven is ignored** (`keyword`, `string`,
  `comment`, `number`, `function`, `builtin`, `decorator`), and so is a `#>`
  directive property no loaded template reads. Both spell nothing on the page.
- **`> modify` and `> mask image` apply from the reveal step of the call
  onward**; placed before their `> pause`, they land a step early.
- **A long title wraps and grows downward.** A title wraps at the width of the
  `title` region (14.6 cm by default, or what `title.max_width` sets), and every
  extra line pushes the title block toward the content, which does not move out
  of the way. Shorten the title, move the second half to `##`, or lower
  `title.fontsize`.
- **Blank lines between list items change nothing.** Items stack with the
  region's gap; `> vspace` is what opens space.
- **A hex string works anywhere a color does**, and putting one in slide content
  defeats re-tinting from the front matter. The palette is the deck's.

### Loud: the build raises and names the construct

- **A paragraph on the line right below a blockquote is swallowed by it**, and
  mate tries to run it as a command. Leave a blank line after a command block
  before a paragraph. Lists, fences, math blocks and headings interrupt the
  blockquote on their own and need no blank line.
- **`> alt` outside a `markdown alternate` body raises.**
- **`pos` or `anchor` without `floating=True` raises.**
- **Ids are cleared at every new slide.** Reusing a key on the next slide is
  fine; targeting an element on a previous slide raises.
- **A deck that does not open with a `#` heading or a directive raises.**
- **A font family that does not resolve raises at build time.** List the families
  before naming one.
- **`color` is a markup property, not a constructor argument.**
  `Rectangle(3, 1, color="red")` raises; constructors take `fill_color` and
  `stroke_color`. `color=` belongs in a span, a fence option or `> modify`.
- **A `Group` takes no `pos`.** A group's position is the union of its children's
  boxes. `Group(children=[...], pos=(5, 3))` raises; build it and place it with
  `move_to((5, 3))`.
- **Ordered lists parse but are not rendered** by the base template
  (`add_ordered_list` raises `NotImplementedError`). Use bullets, or implement
  the method in a template.
- **Image and figure paths resolve against the working directory**, not against
  the Markdown file. Run `mate` from the deck's own directory.

## 12. Before you finish

- The deck builds: `mate deck.md` exits clean.
- The build log names every slide the file carries. A missing one is a fence
  swallowing the rest of the deck.
- No `> draw layout` left in the file.
- The pages were rendered at 150 dpi and every one of them was looked at:
  nothing runs past its region or off the slide. Check the figure slides first,
  an oversized image is the usual cause and it takes the caption with it.
- Every `$$` delimiter sits on a line of its own, and no `||` sits inside an
  emphasis pair.
- Colors are palette names; hex values live in the front matter or in the
  template's palette.
- The build was run once with `--warn` and what it reported was read.
- The reveal steps make sense read in order.
- Every image and figure path resolves from the directory the build runs in.
