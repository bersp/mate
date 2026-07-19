# mate documentation

`mate` builds a PDF presentation from a Markdown file:

```bash
mate slides.md
```

The PDF lands next to the source, as `slides.pdf`.

## Contents

- [Markdown elements](#markdown-elements)
- [Front matter](#front-matter)
- [Styling text](#styling-text)
- [Math](#math)
- [Code blocks](#code-blocks)
- [Commands](#commands)
- [Vertical space](#vertical-space)
- [Images](#images)
- [Layout and regions](#layout-and-regions)
- [Revealing content](#revealing-content)
- [Fragments, overwrites and alternates](#fragments-overwrites-and-alternates)
- [Directives and covers](#directives-and-covers)
- [Configuration](#configuration)
- [Colors](#colors)
- [Templates](#templates)
- [Python and shapes](#python-and-shapes)
- [As a library](#as-a-library)

## Markdown elements

Slides are plain Markdown. A `#` heading opens a new slide and is its title; everything below it is slide content, rendered in source order.

| element | syntax |
|---|---|
| new slide with title | `# Title` |
| subtitle | `## Subtitle`, placed right after the title |
| bold | `**bold**` |
| italic | `*italic*` or `_italic_` |
| code | `` `code` `` |
| bullet list | `- item` |

A full slide looks like this:

```markdown
# The title of a new slide
## An optional subtitle

Regular paragraphs. **Bold**, _italic_ and `code` work as usual.

- Bullet lists too,
- with nested and multi-paragraph items.
```

Nesting, multi-paragraph items, hard line breaks and the rest follow standard Markdown syntax.

In-body `###`..`######` headings render with the `h3`..`h6` styling, one role per markdown level. Ordered lists parse, but rendering them is up to the template; the built-in ones leave them unimplemented.

## Front matter

An optional YAML block opens the file and configures the deck:

```markdown
---
templates: [simple]
config:
  slide.width: 16
  title.fontsize: 15
colors:
  red: "#C95E61"
font_paths: [../my_fonts]
---
```

- `templates` lists the templates the deck inherits from. Each entry is the name of a built-in template (`simple` or `flow`, for instance) or of a `.py` file next to the deck (see [Templates](#templates)).
- `config` overrides configuration keys (see [Configuration](#configuration)).
- `colors` redefines or adds palette colors by name; values are quoted hex strings (see [Colors](#colors)).
- `font_paths` adds font directories, relative to the deck (`~` expands).

Front matter values win over template values.

## Styling text

`mate` repurposes Markdown's link syntax for styling: a stretch of text wrapped in `[...]` takes properties in a second bracket pair. Properties use Python keyword syntax, so strings are quoted and tuples go in parentheses:

```markdown
Words can be styled in place: [this is red][color="red"], and
[this is translucent and smaller][opacity=0.4, fontsize=7].
```

`shift` displaces a span from where it would normally sit, without touching the rest of the line:

```markdown
The star [*][shift=(0, 0.12), color="yellow"] floats above the baseline.
```

`rotate` spins a span in place, in degrees counterclockwise:

```markdown
Flip a digit with [6][rotate=180], or tilt a [label][rotate=15].
```

A `[[...]]` anywhere in a block applies its properties to the whole block:

```markdown
This entire paragraph is gray and small. [[color="gray", fontsize=9]]
```

The most common properties:

| property | example | notes |
|---|---|---|
| `color` | `color="red"` | palette name or hex string |
| `opacity` | `opacity=0.4` | 0 to 1 |
| `fontsize` | `fontsize=8` | points |
| `font` | `font="Lato"` | font family name |
| `weight` | `weight="bold"` | weight name or an integer 100 to 900 |
| `style` | `style="italic"` | `"normal"`, `"italic"` or `"oblique"` |
| `letter_spacing` | `letter_spacing=0.2` | extra tracking, in em |
| `shift` | `shift=(0.1, 0.3)` | displace by `(dx, dy)` cm |
| `rotate` | `rotate=15` | spin in place, degrees counterclockwise |
| `id` | `id="key"` | tag the span for later targeting |

An `id` tags the span: every element carrying the same id can be addressed later by `> modify`, `markdown overwrite` blocks and `> crop image` (see [Revealing content](#revealing-content)).

Spans nest, and they also work inside math:

```markdown
$$ x(t) = [A e^(-gamma t)][id="envelope", color="red"] [cos(omega_0 t + phi)][opacity=0.4] $$
```

The span becomes a piece of the equation: it takes any of the text styling properties, `shift` and `rotate` move and turn it in place within the equation, and its `id` can be targeted by `> modify` later (see [Revealing content](#revealing-content)).

## Math

`$...$` holds inline math, and `$$...$$` display math, which takes a block of its own:

```markdown
The inline form $x^2 + y^2 = r^2$ sits in the running text.

$$
integral_0^oo e^(-x^2) dif x = sqrt(pi) / 2
$$
```

Equations are written in [Typst math syntax](https://typst.app/docs/reference/math/). Support for LaTeX input via MiTex is planned.

Display math is centered by default; an equation is a block like any other, so a `[[...]]` property re-aligns it within the region:

```markdown
$$
x(t) = x_0 e^(-t / tau) [[align="left"]]
$$
```

Styling spans and `||` reveal markers work inside an equation too; see [Styling text](#styling-text) and [Revealing content](#revealing-content).

## Code blocks

A fenced code block renders its source in monospace over a background box, highlighted by language:

````markdown
```python
def f(x):
    return x**2
```
````

The language is a [Pygments](https://pygments.org) lexer name (`python`, `c`, `bash`, `rust`, ...); a fence without one renders plain text. Options follow the language after a `:`

````markdown
```python : numbers=True, numbers_start=25, bg_color="lighter_gray"
def f(x):
    return x**2
```
````

| option | example | notes |
|---|---|---|
| `title` | `title="solver.py"` | name shown in a header bar above the code |
| `numbers` | `numbers=True` | line numbers in a gutter |
| `numbers_start` | `numbers_start=25` | number of the first line |
| `bg_color` | `bg_color="gray"` | background color |
| `header_bg_color` | `header_bg_color="gray"` | header bar color |
| `title_color` | `title_color="black"` | title color |
| `fontsize` | `fontsize=9` | points |
| `padding` | `padding=0.5` | cm between the code and the box edges |
| `corner_radius` | `corner_radius=0.2` | corner rounding of the box, in cm |
| `width` | `width=8` | box width in cm; the region's width by default |
| `words` | `words={"x": {"color": "red"}}` | style specific words, see below |
| `theme` | `theme={"keyword": {"color": "red"}}` | restyle the syntax roles, see below |
| `region` | `region="right"` | target region, instead of the active one |

A `title` opens a header bar above the code, for the file the source comes from:

````markdown
```python : title="solver.py"
def f(x):
    return x**2
```
````

A template can restyle the block as a whole, header included, and add options of its own (see [Templates](#templates)).

Styling spans and `||` reveal markers work inside a fence like everywhere else (see [Styling text](#styling-text) and [Revealing content](#revealing-content)):

````markdown
```python
def f(x):
    return x**2

||print(f([x][color="red", id="arg"]))
```
````

Everything else is verbatim: Markdown markup does not apply, spacing is preserved exactly, and a bracket pair is a span only when its second bracket reads as properties, so real code like `a[i][j]` stays code. `\||` writes a literal `||`; languages where `||` is an operator need the escape.

`words` styles every whole-word occurrence on top of the language highlighting; each value is a dict of span properties (see [Styling text](#styling-text)):

````markdown
```python : words={"x": {"color": "red", "weight": "bold"}}
def f(x):
    return x**2
```
````

The highlighting itself is a theme: a mapping from each syntax role (`keyword`, `string`, `comment`, `number`, `function`, `builtin`, `decorator`) to the properties of its tokens, span properties again. The `code.theme` configuration key holds the deck-wide theme, and the `theme` option updates it for one fence, role by role: an entry replaces that role's properties, and roles left out keep the deck theme.

````markdown
```python : theme={"keyword": {"color": "red"}}
def f(x):
    return x**2  # keywords turn red; every other role keeps the theme
```
````

The other `code.*` keys set the font, colors and geometry (see [Configuration](#configuration)).

## Commands

A blockquote line calls a method of the presentation. The syntax is `> name : args`, or just `> name` for a call without arguments. Spaces in the name become underscores (`> add vspace` calls `add_vspace`) and the arguments are Python:

```markdown
> add vspace : 0.5
> add image : "figure.png", width="50%"
> pause
```

Each line is one call, and one blockquote can carry several. Any public method of the presentation can be called this way, including the ones a template defines.

Commands follow Markdown's blockquote conventions; in particular, a paragraph starting on the line right below a blockquote is folded *into* the blockquote. This works:

```markdown
> add vspace : 0.5
> pause

Content separated by a blank line renders normally.
```

This does not:

```markdown
> pause
This line has no blank line above it, so Markdown treats it as part of
the blockquote and mate tries to run it as a command.
```

Leaving a blank line after the commands avoids the problem.

## Vertical space

`> add vspace` sets the vertical space at one point of a region's stack:

```markdown
The point above the gap.

> add vspace : 0.7

The point below it, exactly 0.7 cm under the one above.
```

The spacer replaces the stack's usual gap, so the separation ends up at exactly 0.7 cm, and `> add vspace : 0` puts two elements right against each other.

## Images

`> add image` places an image in the current region:

```markdown
> add image : "figure.png"
```

With no size the image scales as large as fits inside the region. Setting `width` or `height` alone keeps the file's aspect ratio; setting both forces the image into that box. Sizes are in cm, or a percentage of the region:

```markdown
> add image : "figure.png", width="50%"
> add image : "diagram.svg", height=4
```

The options of `add image`:

| option | example | notes |
|---|---|---|
| `width` | `width=5`, `width="50%"` | cm, or a percentage of the region width |
| `height` | `height=3`, `height="80%"` | cm, or a percentage of the region height |
| `region` | `region="right"` | target region, instead of the active one |
| `align` | `align="left"` | horizontal alignment inside the region |
| `id` | `id="fig"` | tag for `modify` and `crop image` |
| `floating` | `floating=True` | leave the region's stack; place with `pos`/`anchor` |
| `pos`, `anchor` | `pos=(2, 1), anchor="center"` | position for a floating image |

### Cropping

`> crop image` shows only a window of a tagged image. The window is given as fractions of the image, with the origin at its top-left corner, and the defaults name the whole image, so a single axis can be cropped alone:

```markdown
> add image : "map.png", id="map"
> pause
> crop image : "map", x=0.25, y=0.25, width=0.5, height=0.5
```

The crop applies from that reveal step onward, so this reads as a zoom-in. `> uncrop image : "map"` shows the whole image again.

## Layout and regions

Every element on a slide is either in a region, which stacks its content top to bottom, or floating at a fixed position (see [Floating elements](#floating-elements)). The default layout defines `title`, `footer`, `left_margin`, `right_margin`, `content` (the default active region), `full` and `full_with_margins`.

`> region` switches the active region, and `> grid` splits a region into named cells. The minimal two-column slide:

```markdown
> grid : [["text", "fig"]], hgap=0.5
> region : "text"

The setup is sketched on the right. The laser hits the sample at a
grazing angle.

> region : "fig"
> add image : "setup.png", width="90%"
```

Since content commands take a `region` argument, the last two lines could also be a single one, without touching the active region:

```markdown
> add image : "setup.png", width="90%", region="fig"
```

The grid template is a rows-by-columns array of labels, with row 0 on top. Cells sharing a label merge into one region, so a header or a footer can span several columns:

```markdown
> grid : [["top", "top"], ["left", "right"], ["bottom", "bottom"]], vgap=0.4, height_ratios=[1, 3, 1]
> region : "top"

A full-width line above two columns.

> add image : "experiment.png", region="left"
> add image : "simulation.png", region="right"

> region : "bottom", anchor="center"

And a full-width caption under both. [[color="gray", fontsize=9]]
```

Here `height_ratios` gives the middle row three times the height of the other two, and switching to `"bottom"` with `anchor="center"` centers the caption in its cell instead of stacking it from the top-left corner.

The arguments of `grid`:

| argument | example | notes |
|---|---|---|
| `hgap`, `vgap` | `hgap=0.5` | gaps between columns and rows, in cm |
| `width_ratios` | `width_ratios=[2, 1]` | relative column widths, uniform by default |
| `height_ratios` | `height_ratios=[1, 3]` | relative row heights, uniform by default |
| `anchors` | `anchors={"fig": "center"}` | anchor per cell (see below) |
| `region` | `region="content"` | which region to split; the active one by default |

A region's anchor names the point its content stacks from, one of the nine bbox points: `"top-left"`, `"top-center"`, `"top-right"`, `"center-left"`, `"center"`, `"center-right"`, `"bottom-left"`, `"bottom-center"`, `"bottom-right"`. Content regions default to `"top-left"`. A cell holding a lone image usually looks better centered, either through the grid's `anchors` argument or when switching to it, as with the caption above.

While building a layout, `> draw layout` overlays every region as a labelled outline, which makes gaps and ratios easy to tune.

### Floating elements

`floating=True` detaches content from the region system: nothing stacks it, and it sits with its `anchor` point at `pos`, in cm from the slide center with the y axis pointing up. `> add image` takes it directly:

```markdown
> add image : "stamp.png", width=2, floating=True, pos=(6, 3.5), anchor="top-right"
```

A floating fragment does the same for a whole run of content (see [Fragments](#fragments-overwrites-and-alternates)): the body stacks on its own, wraps at the region's width, and lands with its anchor at `pos`, or on the region's anchor point when `pos` is omitted:

````markdown
```markdown fragment : floating=True, pos=(0, -3.5), anchor="bottom-center"
A remark pinned near the bottom edge of the slide, outside the content
region's stack.
```
````

## Revealing content

So far everything lands on the slide at once; the reveal system decides *when* things appear. A slide compiles to one page per reveal step, and each page shows the content accumulated up to that step. Positions are computed once over the full slide, so revealing content never moves what is already visible.

`> pause` starts a new step; content after it appears on the next page:

```markdown
First the question.

> pause

Then the answer.
```

`||` (the pause symbol) splits a text into segments that appear one step at a time, while the space of the hidden part is reserved from the start:

```markdown
This shows first, || then this, || and this at the end.
```

`\||` escapes the marker and renders a literal `||`.

A `||` inside `$...$` or `$$...$$` splits the equation the same way, keeping the math spacing:

```markdown
$$ f(x) = x^2 || - 2x || + 1 $$
```

### Changing what is already on the slide

`> modify` restyles or moves every element tagged with an id, from its reveal step onward. Tag a span, pause, then change it:

```markdown
Compare [the left term][id="lhs"] with [the right term][id="rhs"].

> pause
> modify : "lhs", color="red"

> pause
> modify : "lhs", color="black"
> modify : "rhs", color="red"
```

Any property with a setter works: the span properties from [Styling text](#styling-text), plus things like `shift` and `crop`. Ids can be strings or numbers, several elements can share one id (they all change together), and one element can carry several ids. A step can combine new content with modifications of old content:

```markdown
This paragraph carries [a tagged span][id="target"].

> pause
> modify : "target", color="red", weight="bold"

This appears on the second step, || this on the third,

> pause
> modify : "target", color="gray", weight="regular"

and this on the fourth, while the span above changes color each time.
```

## Fragments, overwrites and alternates

Three fenced blocks treat a run of content as one unit: `fragment` groups it, `overwrite` rewrites it in place, and `alternate` cycles variants through a single slot.

### Fragments

A `markdown fragment` fence groups blocks and applies properties to the group: an `id` for later targeting, a `region` for placement, or any span property:

````markdown
```markdown fragment : region="right", color="gray"
This paragraph and the list below render in the "right" region, in gray.

- one
- two
```
````

With `floating=True` the fragment leaves the region's stack and is placed on its own (see [Floating elements](#floating-elements)).

### Overwrites

A `markdown overwrite` fence replaces a tagged block from its step onward. The new content is drawn inside the original block's box, so nothing around it moves. This is made for rewriting something that stayed *above*:

````markdown
```markdown fragment : id="block"
This paragraph shows from the first step.
```

This text sits below the tagged paragraph and never moves.

> pause

```markdown overwrite : "block"
This text replaces the tagged paragraph, drawn inside its box.
```
````

A fragment can also reveal itself gradually and then be replaced all at once:

````markdown
```markdown fragment : id="steps"
This shows on the first step.

> pause

This joins it on the second.

> pause

And this on the third.
```

> pause

```markdown overwrite : "steps"
This replaces the three paragraphs at once, inside their box.
```
````

### Alternates

A `markdown alternate` fence shows variants in one slot, one per step, separated by `> alt` lines. The slot reserves the height of the tallest variant, so the content below never moves. Stepping through versions of a figure is the typical use:

````markdown
```markdown alternate
> add image : "step1.png", height="70%"
> alt
> add image : "step2.png", height="70%"
> alt
> add image : "step3.png", height="70%"
```
````

## Directives and covers

`#>` opens an off-slide directive: the `>` lines right below it are `key: value` properties handed to the template between slides. The marker carries no name of its own; everything the template acts on lives in the properties. `cover: True` renders a cover page from the same block.

A short presentation usually needs a single directive at the top of the file, for its cover:

```markdown
#>
> cover: True
> title: Bayesian model comparison
> author: Jane Doe

# First slide

...
```

The cover takes its `title` and shows `author` and `date` when present. Some templates also render a `tagline` line with the cover title. Property values are Python literals when they parse as one, and raw strings otherwise.

A directive placed anywhere in the file runs at that point, and what it does is up to the template: it receives every property and decides. A template can put a running section label on the slides that follow, switch the theme halfway through the talk, drop the footer, restyle code, or act on whatever property it reads. A property no template reads is ignored.

## Configuration

Configuration keys are dotted paths, set from the deck's front matter or from a template (`config.set("title.fontsize", 15)`). From the front matter:

```markdown
---
config:
  slide.width: 20
  slide.height: 11.25
  text.fontsize: 11
  list.bullet: "circle"
  footer.show: false
---
```

The keys and their defaults:

| key | default |
|---|---|
| `slide.width`, `slide.height` | `16.0`, `9.0` (cm) |
| `text.font`, `text.fontweight`, `text.fontsize`, `text.color` | `"libertinus serif"`, `"regular"`, `12.0`, `"black"` |
| `text.line_gap` | `0.25` |
| `title.*`, `subtitle.*`, `math.*` | same four dimensions per role |
| `h3.*` .. `h6.*` | same four dimensions, one role per in-body heading level |
| `cover.title.*`, `cover.tagline.*`, `cover.author.*` | same four dimensions per role |
| `list.bullet` | `"square"` (also `"circle"`, `"dash"`) |
| `list.bullet_scale`, `list.bullet_gap`, `list.dash_thickness` | `0.8`, `0.2`, `0.06` |
| `footer.show`, `footer.show_total` | `True`, `False` |
| `region.default` | `"content"` |
| `region.content.anchor`, `region.content.arrange_gap` | `"top-left"`, `0.25` |
| `region.full_with_margins.margins` | `0.7` |
| `image.align` | `"center"` |
| `code.font`, `code.fontsize`, `code.color` | `"DejaVu Sans Mono"`, `10.0`, `"black"` |
| `code.bg_color`, `code.padding`, `code.corner_radius` | `"lightest_gray"`, `0.35` (cm), `0.1` (cm) |
| `code.line_height` | `1.25` (line step, in multiples of the font size) |
| `code.numbers`, `code.numbers_start`, `code.numbers_color` | `False`, `1`, `"gray"` |
| `code.theme` | syntax role to properties mapping (see [Code blocks](#code-blocks)) |
| `line.stroke_width` | `0.03` |
| `arrange.gap` | `0.2` |
| `typst.preamble` | `""` (markup prepended to every generated document) |

Every typographic role (`text`, `title`, `subtitle`, `h3`..`h6`, `math`, `cover.title`, `cover.tagline`, `cover.author`) carries the same four dimensions: `font`, `fontweight`, `fontsize` and `color`.

Templates read their own knobs from the namespace carrying their name (`flow.<prop>` keys belong to the `flow` template), which the front matter can set freely.

## Colors

Every color-valued property and key takes a palette name or a literal hex string, so `color="red"` and `color="#C95E61"` are both valid anywhere a color goes.

The default palette defines `black`, `white`, `red`, `orange`, `yellow`, `green`, `aqua`, `blue`, `purple`, and six grays: `darkest_gray`, `darker_gray`, `dark_gray`, `gray`, `lighter_gray` and `lightest_gray`. Templates add or re-tint entries, and the front matter `colors:` section overrides any of them by name, or adds new ones:

```markdown
---
templates: [flow]
colors:
  red: "#D08770"
  flow.backdrop: "#22303a"
  accent: "#5B3A86"
---
```

Overriding a name restyles everything that refers to it, so re-tinting a template is a couple of lines. New names (like `accent` above) become available to spans, commands and Python code alike.

The colors a template defines for itself are namespaced with the template's name (`flow.backdrop` above), so stacked templates do not collide.

A gradient works anywhere a color does: `Gradient.linear(*stops, angle=...)` runs at `angle` degrees (0 is left to right) and `Gradient.radial(*stops, center=..., radius=...)` grows from its center. Each stop is a color, optionally paired with its position along the gradient:

```python
Gradient.linear("red", ("yellow", "30%"), "blue", angle=45)
```

## Templates

A template defines the look of the deck: fonts, colors, backgrounds, layout and slide logic. The front matter lists the templates to use; entries can stack, and earlier entries win where two define the same thing.

A template is a file defining a `PresentationTemplate` class:

```python
from mate import PresentationTemplateBase, Rectangle, config


class PresentationTemplate(PresentationTemplateBase):
    palette = {
        "my_template.accent": "#5B3A86",
    }

    def __init__(self) -> None:
        """Color the titles with the accent, hide the footer."""
        config.set("title.color", "my_template.accent")
        config.set("footer.show", False)
        config.colors.set_multiple(self.palette)
        super().__init__()

    def background(self):
        """Draw a thin accent bar along the left edge of every slide."""
        W, H = config.slide_width, config.slide_height
        return Rectangle(0.15, H, pos=(-W / 2 + 0.075, 0), fill_color="my_template.accent")
```

Saved as `my_template.py` next to the deck, it is used with `templates: [my_template]`.

- A template's colors are palette entries, namespaced with the template's name (see [Colors](#colors)). Configuration keys accept both hex values and palette names, but a name lets the deck re-tint it from the front matter.
- Configuration is set before `super().__init__()`; the front matter is applied there, so deck values win over template values.
The hooks one usually overrides are `build_layout` (the region map), `background` (drawn behind every slide), `add_title`, `add_cover`, `on_directive`, `add_footer` and the `add_*` content methods, and any new method is callable from the deck as a command. In principle, though, a template can change every behavior, internals included: `mate/core/template.py` holds the full set of methods.

The built-in templates are also worked examples: `simple` shows the minimal case (a font stack and a restyled title) and `flow` a complete one (its own palette, a generated background, custom cover and title logic). They live in `mate/templates/`.

### Restyling code blocks

A `Code` block's whole look lives in its `build` method, which returns every element the block draws from the styled lines the constructor prepares. A template restyles code blocks by subclassing `Code`, replacing `build`, and overriding `add_code` to instantiate it:

```python
from mate import Code, PresentationTemplateBase, Rectangle, Text, config


class MyCode(Code):
    def __init__(self, source, *, accent_color="my_template.accent", **code_kwargs):
        self.accent_color = accent_color
        super().__init__(source, **code_kwargs)

    def build(self):
        """Draw an accent bar down the left edge, then the code."""
        width = self.width
        height = 2 * self.padding + len(self.lines) * self.line_step
        members = [
            Rectangle(width, height, fill_color=self.bg_color, pos=(0, 0), anchor="top-left"),
            Rectangle(0.1, height, fill_color=self.accent_color, pos=(0, 0), anchor="top-left"),
        ]
        for index, leaves in enumerate(self.lines):
            top_y = -self.padding - index * self.line_step
            line = Text(None, font=self.font, fontsize=self.fontsize,
                        fill_color=self.color, pos=(self.padding, top_y), anchor="top-left")
            line._take_children(leaves)
            members.append(line)
        return members


class PresentationTemplate(PresentationTemplateBase):
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

`build` reads what the constructor leaves on the instance: `lines` (the styled leaf runs of each source line), `line_segments` (the reveal segment each line starts in), `max_columns`, the `char_width` / `cap_height` / `line_step` metrics, and every resolved option (`title`, `width`, `font`, `padding`, ...). It positions everything in a local frame whose origin is the block's top-left corner, and the geometry is its own to decide. A line number must join `reveal_segments[self.line_segments[index]]` to appear with its line.

Passing the subclass to `resolve_code_options` makes its own parameters available as fence options: `accent_color="red"` above works from a deck.

## Python and shapes

A `python mate` fence runs inside the deck with the `mate` API in scope and the presentation available as `self`. The namespace persists across blocks, so imports and definitions carry over:

````markdown
```python mate
self.add_text("Text added from a *python mate* block.")

slide = self.current_slide
slide.add(Rectangle(3.0, 1.8, pos=(-4, -2), fill_color="blue"))
slide.add(Circle(0.9, pos=(0, -2), fill_color=Gradient.radial("yellow", "orange")))
slide.add(Line((3, -2.8), (5.5, -1.2), stroke_color="red", stroke_width=0.06))
```
````

Coordinates are in centimetres, with the origin at the slide centre and the y axis pointing up.

Elements added with `slide.add(...)`, like the shapes above, are floating (see [Floating elements](#floating-elements)). The content methods on `self` (`add_text`, `add_image`, `add_bullet_item`, `add_vspace`, `pause`, `modify`, `grid`, `region`, ...) go through the region system as usual.

The available shapes:

| shape | positional arguments |
|---|---|
| `Rectangle` | `width`, `height` |
| `Circle` | `radius` |
| `Ellipse` | `width`, `height` (the bounding box of the ellipse) |
| `Line` | `start`, `end` |
| `Polygon` | `points` (three or more vertices) |
| `Curve` | `segments` (`MoveTo`, `LineTo`, `QuadTo`, `CubicTo`, `Close`) |

All of them share the same keyword arguments: `pos`, `anchor`, `id`, `fill_color`, `stroke_color`, `fill_opacity`, `stroke_width`, `stroke_dash`, `stroke_cap`, `stroke_join` and `stroke_opacity`. The defaults are a solid black fill with no stroke; `fill_opacity=0` gives a stroke-only shape, and a `Line` draws only its stroke.

## As a library

`mate` is also usable as a plain library, with the same API:

```python
from mate import Presentation

pres = Presentation("deck")
pres.new_slide("Built from Python")
pres.add_title()
pres.add_text("A paragraph added with *add_text*.")
pres.add_vspace(0.4)
pres.add_bullet_item("a bullet item")
pres.end_slide()
pres.write()  # deck.pdf
```
