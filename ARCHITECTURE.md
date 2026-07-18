# mate — architecture

A Python-driven presentation tool.

## Design principles

1. **All logic in Python.** The backend is dumb: it receives "draw this here" and "measure this" instructions.
2. **Backend-agnostic.** To add another backend (LaTeX, SVG, canvas, etc.) only `backends/` is touched. The rest of the project knows nothing about Typst syntax.
3. **Uniform bbox.** Every `Element` (text, shapes, lines, ...) exposes `(x, y, w, h)` in cm, where `(x, y)` is the geometric **centre** in slide coordinates. Without this there is no coherent layout.
4. **Lazy, cached measurement.** Measuring runs an in-process Typst query (embedded fonts plus the project `fonts/` directory, no system-font scan); results are cached until something changes.

## Folder structure

```
mate/
├── __init__.py        # public re-exports
├── cli.py             # `mate <presentation.md>` entry point
├── config.py          # process-global `config` singleton (slide size, color palette)
├── log.py             # process-global `mate` logger
├── pyproject.toml
├── core/              # primitives and central abstractions
│   ├── vec.py
│   ├── element.py
│   ├── drawable.py
│   ├── gradient.py
│   ├── registry.py
│   ├── slide.py
│   ├── directive.py
│   ├── template.py
│   └── presentation.py
├── elements/          # concrete visual element types
│   ├── code.py
│   ├── group.py
│   ├── image.py
│   ├── shapes.py
│   ├── spacing.py
│   └── text.py
├── parser/            # Markdown → parsed document (front matter, directives, slides)
│   ├── ir.py
│   ├── markdown.py
│   ├── markup.py
│   └── serialize.py
├── backends/          # backend-specific renderers/measurers
│   └── typst.py
├── composition/       # spatial layout built on top of core + elements
│   ├── arrange.py
│   ├── layout.py
│   └── utils.py
├── templates/         # built-in presentation templates
│   ├── simple.py
│   └── flow.py
├── fonts/             # bundled font families, one directory per family
└── .mate_cache/       # regenerated artifacts (measurement); safe to delete
```

## Coordinate system

Slide coordinates are in centimetres with origin at the slide's **visual centre**, `+x` pointing right and `+y` pointing up (mathematical convention). A slide of size `(W, H)` therefore spans `x ∈ [-W/2, +W/2]` and `y ∈ [-H/2, +H/2]`. A `Vec(0, 0)` placed with the default `anchor="center"` lands at the centre of the slide.

This convention applies everywhere in the Python model: `_pos`, `_bbox`, the values inspected by `arrange`, `move_to`, `shift`, `center`, etc. Typst's native page coordinates are y-down with origin at the top-left; the renderer applies the user→Typst transform (`dx = _pos.x + W/2`, `dy = H/2 - _pos.y`) at emission time so user `(0, 0)` lands at the Typst page centre. The measurer keeps its aux doc in raw user-coords — only the inline `here().position().x` probe is read back, and it returns the user-x directly.

## Model

### `core/vec.py` — `Vec`

A 2D `np.ndarray` subclass with `.x` and `.y`. Use it whenever something has "two coordinates" (position, size, center). Inherits numpy arithmetic and broadcasting for free.

### `core/element.py` — `Element`

Base class of **everything** that appears on a slide. Attributes:

| Attribute | Meaning |
|---|---|
| `pos` | Stored anchor point `Vec` in slide coordinates (cm). Public, read via property; writes go to `_pos`. Never measures. |
| `_pos` | Storage backing `pos`. Internal hot paths (`_translate`, backend) read/write this directly. |
| `anchor` | Which point of the bbox sits at `_pos`. One of the nine `Anchor` strings: `"top-left"`, `"top-center"`, `"top-right"`, `"center-left"`, `"center"` (default), `"center-right"`, `"bottom-left"`, `"bottom-center"`, `"bottom-right"`. Resolved into `(h_mul, v_mul)` multipliers by `anchor_offsets(anchor)` such that the bbox centre is offset from `_pos` by `((0.5 - h_mul) * w, (0.5 - v_mul) * h)`. Under y-up slide coords, `v_mul = 1` for `"top-*"`, `0.5` for `"center-*"`, `0` for `"bottom-*"`. |
| `_anchor` | Storage backing `anchor`. |
| `center` | Visual bbox center `Vec`. Property: fast path returns `_pos` when `_anchor == "center"` and the element is not inline; otherwise measures. `Group` overrides it to always return the union-bbox center. |
| `placement` | `"fixed"` (drawn with the body's `_anchor` point at `_pos`), `"inline"` (flows in parent's content), or `"omitted"` (not rendered, not measured). |
| `parent` | Owning `Element` (set automatically when adopted via `_take_children`); `None` for root elements directly attached to a `Slide`. |
| `hidden` | If `True`, the element takes space but is not drawn. Propagates through ancestors via `get_effective_hidden()` — `hidden=True` on a Group hides the whole subtree at render time. |
| `children` | List of sub-`Element`s. Forms a tree. |
| `angle` | Rotation of the element's own body about its centre, in degrees counterclockwise (slide coords are y-up). The backend emits the matching `#rotate`; the measured bbox grows to the rotated extents. Inert on a `Group` (no body of its own). |
| `_mid` | Globally unique id, used by the backend for metadata. |
| `_bbox` | Cached `(x, y, w, h)` or `None` (not measured). `(x, y)` is the geometric **centre** in slide coords (y-up); `w` and `h` are positive extents. Edges: `left = x - w/2`, `right = x + w/2`, `bottom = y - h/2`, `top = y + h/2`. |

Public API: `move_to / shift / set_anchor / rotate / get_bbox / get_width / get_height / get_bbox_center / copy` plus the `pos`, `anchor`, and `center` properties. Movement (`move_to` / `shift`) forces `placement = "fixed"` and invalidates the bbox cache of the whole tree.

All `Element` constructor parameters (`pos`, `anchor`, `placement`, `id`) are **keyword-only** — subclasses keep their intrinsic positional args (`Rectangle(width, height, ...)`, `Circle(radius, ...)`, `Text(source, ...)`, `Group(children, ...)`) but everything else flows as `**kwargs`. The split is enforced by the `*` in each `__init__`.

- `move_to(p)` — sets `_pos = p`. Reads the current visual anchor point via `_current_anchor_point()` (no measurement for fixed non-Group; measures for inline or Group), and translates every fixed descendant by `p - <old anchor point>` so the subtree moves as a unit.
- `shift(d)` — adds `d` to `_pos` (accumulates over repeated calls). When the element is `"inline"`, freezes `_pos` to its measured anchor point first, so the increment is taken from the flowed position. Same propagation: every fixed descendant gets `+= d`. A fragment inside a math run has no independent bbox: `shift` accumulates `d` into `offset` and stays in the equation, where the backend renders it as an in-place `#move` (the fragment's original slot is kept).
- `set_anchor(anchor)` — changes `_anchor` without modifying `_pos`. The visual position shifts so the new anchor point sits at the same coordinate. Invalidates the bbox cache.
- `rotate(angle, pivot=None)` — rotates this element and its fixed subtree rigidly by `angle` degrees counterclockwise about `pivot` (default: the element's own centre). `_place_roots` gathers the nodes that get their own `#place` (this element plus every fixed descendant); each one re-orients by `angle` about its centre and revolves about `pivot`, giving a `Group` a single rigid turn. A piece whose centre coincides with the pivot spins in place: its position, anchor, and placement stay untouched, and an inline run stays in flow (the path a per-run `rotate=` markup property takes). A piece that the revolution displaces becomes `"fixed"`, re-anchored to `"center"` at its revolved point. `Group` nodes carry no body of their own and move through their descendants. A fragment inside a math run has no independent bbox: `rotate` accumulates its `angle` and returns without measuring, and the backend emits the rotation inside the equation.
- `get_width()` / `get_height()` — return bbox width/height in cm; shape primitives override with their intrinsic values (no measurement).
- `get_bbox_center()` — always measures (cache miss → Typst query) and returns the bbox center. Use `center` when the cheaper fast path is enough.

**Inline → fixed freeze.** Inline elements have no anchor of their own — their visible position only exists after Typst lays them out. The freeze captures the current anchor point (`_current_anchor_point()` derives it from the measured bbox and the anchor's offsets) and stores it in `_pos` before applying the increment, which makes `shift((0, 0))` a true visual no-op. The cost is one measurement when the bbox cache is cold.

**Movement propagates by default.** Mutating an element's position translates every fixed descendant by the same delta (`_translate` walks the subtree). `"inline"` descendants are not touched (their `_pos` is meaningless under flow), but the recursion descends through them so fixed grand-descendants follow too.

**Cache invalidation is geometric only.** `move_to`, `shift`, `set_anchor`, and the intrinsic-size setters (`set_width`, `set_height`, `set_radius`) call `_invalidate_tree`, which clears `_bbox` on every node in the tree (a position or anchor change can shift the flowed `x` of inline siblings, so the whole tree must be re-measured). Visual-only mutators (color, opacity, stroke, hidden) leave the cache alone, since they do not affect typesetting size.

**Placement semantics.** The renderer skips `"omitted"` elements at every level. `"inline"` only makes sense as a descendant of a fixed element — at the slide root it is treated like `"omitted"` for rendering, since there is no parent flow to participate in. The parser in `Text` produces `"inline"` subs by default; users opt into placement explicitly with `move_to` or `shift`.

**`Group.center` and `Group._current_anchor_point` always measure.** A `Group` has no rendered body, so its visual position is the union of children's bboxes — not the stored `_pos`. Both reads override the base to measure on every call. The stored `_pos` exists so `move_to`/`shift` arithmetic is uniform across subclasses; it is not a reliable query of "where is the group".

**`measure_all(elements)`** is the batch-measurement helper. It deduplicates the tree roots reached from the input and runs one `TypstMeasurer` over them, filling `_bbox` everywhere in one Typst query. Layout utilities (`arrange`) use it to amortize measurement over N elements.

**Copy protocol.** `copy()` is the public entry. `Element._copy(mapping)` uses `copy.copy(self)` to duplicate the instance's `__dict__` and then resets identity-bearing fields (`_mid`, `id`, `parent`, `_bbox`) and deep-clones `children`. Intrinsic-data fields (`w`, `h`, `r`, `content`, ...) come along automatically, so `Rectangle` / `Circle` / `Ellipse` need no override. Only subclasses with **cross-references between descendants** override — `Text._copy` calls `super()._copy(mapping)` and then remaps its `subs` list through the shared `mapping`, so the cloned subs point at the cloned descendants.

### `core/presentation.py` — `Presentation`

- `Presentation` is a :class:`PresentationTemplate` (see below) plus the list of `Slide`s. It owns the global `width` / `height` (every slide has the same size), publishes them to `config`, and tracks `current_slide` (the most recently created slide, set by `new_slide`). It also carries the presentation `name`; `write()` raises if any slide is still open, then compiles every slide's snapshot markup (flattened across slides) into `<name>.pdf` via `TypstRenderer.compile_document`.
- `pause()` opens a new reveal step on the current slide (see `core/slide.py`): content added after it lands on a later page.
- `end_slide()` arranges every region of the layout **once over the slide's full content** — so each element's position is baked before any page is rendered — then seals the slide by rendering one `Snapshot` per reveal step (the step's cumulative root elements, via `TypstRenderer.render_snapshot`), and clears the regions for the next slide. Because every root is absolutely placed, a page that draws only a prefix of the roots shows them at their final positions with no reflow.
- Measurement is **independent of slide membership**. An orphan element can call `get_bbox()` and the measurer runs over its own tree (rooted at the topmost ancestor reachable via `parent`). The slide never appears in the measurement path.

### `core/slide.py` — `Slide`, `Snapshot`

- `Slide` is the authored unit (one ``#`` block): `title` / `subtitle` strings (passed to `new_slide`) plus `steps`, a list of reveal steps. Each step is a list of root elements; those with `placement != "fixed"` are skipped at render time. Root elements keep `parent = None` (the slide is not itself an `Element`). `add(element)` appends to the current step and returns it for chaining; `pause()` opens a new step. A slide starts with one (empty) step, so a slide without a pause is a single step. `Slide` never references a backend.
- `reveal_prefixes()` yields the cumulative root elements visible at each step, one list per step. `Presentation.end_slide` renders one `Snapshot` from each.
- `Snapshot` is one compiled page: a frozen snapshot of rendered Typst markup. `Presentation.end_slide` fills `snapshots` (one per step); `is_sealed` reflects whether the slide has been sealed. Mutations after sealing do not affect the snapshots.

### `core/template.py` — `PresentationTemplate`

Base class of `Presentation`: the theme a presentation overrides. Holds the presentation-wide `font`, builds the region `Layout` (`build_layout`), and the optional slide `background` (returns an `Element` or `None`). `new_slide` adds the `background` element first, so it renders behind all other content and appears on every page of the slide. A concrete theme subclasses `Presentation` and overrides these hooks; the geometry and `config` wiring live in `Presentation`, so the template assumes the slide size is already published when `build_layout` runs.

`build_layout` reads slide-relative geometry from `config` and per-theme knobs from the `config` defaults store (`box.full_with_margins.margins`, `box.content.anchor`), producing named regions: `title`, `footer`, `left_margin`, `right_margin`, `content` (the inner region left after subtracting the four sides), `full`, and `full_with_margins`; `active` starts on `content`.

`add_title()` builds the current slide's `title` and `subtitle` strings into `Text` elements in the template `font` and adds them to both the current slide and the `title` region.

### `core/drawable.py` — `Drawable`

Intermediate class for elements with fill/stroke styling. Adds four optional fields, all keyword-only:

| Field | Type | Default → resolved value |
|---|---|---|
| `fill_color` | `str` or `None` | `None` → `"black"` |
| `stroke_color` | `str` or `None` | `None` → `"black"` |
| `fill_opacity` | `float` or `None` | `None` → `1` (set `0` for no fill) |
| `stroke_width` | `float` (cm) or `None` | `None` → `0` (no stroke) |

The backend resolves `None` to the default values locally at render time — every `Drawable` element renders from its own concrete values. To restyle a subtree, the bulk setters (`set_fill_color`, `set_stroke_color`, `set_fill_opacity`, `set_stroke_width`) walk the tree and overwrite the chosen field on every `Drawable` descendant. Plain `Element` descendants (e.g. an `Image` that does not carry fill/stroke) are skipped during the walk.

`Rectangle`, `Circle`, `Ellipse`, `Text`, and `Group` all inherit from `Drawable`. `Element` remains the base for nodes that don't carry these fields.

## Elements

### `elements/text.py` — `Text`

`Text` extends `Drawable`. It is either a **leaf** (with `content: str`) or a **composite** (with `children: list[Text]`).

**Markup:** `Text("foo [bar [baz](id=1)](id=2)")` parses balanced brackets; each block followed by `(id=K)` becomes a sub-`Text` (`placement="inline"` by default) appended in source order to the parent's `subs` list and registered in `id_registry` under the key `K`. Subs are real `Element`s: calling `move_to` (or `shift`) on a sub flips it to `placement="fixed"` and lifts it out of parent flow.

Every `Text` carries explicit `font: str` and `size: float` (points) as keyword-only constructor params. Defaults are the Typst defaults hardcoded as constants (`DEFAULT_FONT = "libertinus serif"`, `DEFAULT_SIZE_PT = 11.0`). The backend wraps every rendered/measured Text in `#text(font: "...", size: ...pt, ...)`. Sub-elements built by the parser inherit the parent's font/size, propagated in the constructor after `_take_children`. An optional `max_width: float | None` (cm) wraps the text: the backend boxes it at `min(natural width, max_width)` via a Typst `#context` block, so the bbox width shrinks to fit and the height grows with the wrapped line count.

`fill_*` and `stroke_*` fold into the same `#text(...)` wrapper as `font` and `size`, each emitted only when the element carries explicit values; an element without them inherits Typst's lexical defaults (black fill, no stroke).

**`_copy()`** override re-maps the `subs` list using the shared `mapping` from `Element._copy`, so the cloned subs point at the cloned descendants. Clones inherit structure but are not registered in `id_registry`: the registry indexes user-tagged originals.

A leaf with `verbatim=True` renders its `content` literally: no Markdown parsing, every punctuation character backslash-escaped and every space emitted as a no-break space, so exact characters and spacing survive Typst's markup mode.

### `elements/code.py` — `Code`

`Code` extends `Group`: a background `Rectangle`, one fixed monospace composite `Text` per source line, one right-anchored `Text` per line number when numbers are on, and a header bar (a `Rectangle` plus a `Text`) when a `title` is given. Lines sit at a fixed vertical step, anchored top-left: Typst's default text edges (cap-height to baseline) give every single-line text the same measured height, so baselines stay aligned with no per-line measurement. One cached probe of a digit supplies the character advance and the cap height; the number gutter and the hugged width are character counts times the advance.

Construction runs in two phases. `__init__` resolves the options against the `code.*` config keys and scans the source into `lines` (the styled leaf `Text` runs of each line, unpositioned), `line_segments` (the reveal segment each line starts in), `reveal_segments`, `max_columns`, and the `char_width` / `cap_height` / `line_step` metrics, all left on the instance. `build()` reads those and returns every element the block draws, positioned in a local frame whose origin is the block's top-left corner. The block's whole visual design lives in `build()`, geometry included: the gutter width, the header height, the hugged width and the total height are computed there. A subclass overrides it to restyle the block.

`corner(corner_radius, name)` returns the radius one `corner_radius` value gives a named corner. A piece drawn over the background uses it for the corners it shares with it: a header bar takes the two top ones, a gutter column the two left ones.

The source is verbatim. Two constructs are parsed out of it: `[body][props]` spans and `||` reveal markers. A bracket pair is a span only when `props` reads as keyword properties, so code like `a[i][j]` stays literal; the props apply to each styled run the span covers, and `id=` registers those runs. `||` splits the whole block into segments recorded in `reveal_segments`. `\||` is the only escape, yielding a literal `||`; every other backslash is code.

Pygments tokenizes the plain source; each token maps to a `code.theme` role whose property dict styles it, the `words` option overlays the theme on whole-word matches, and explicit spans win over both. Each run of uniform style becomes one verbatim leaf `Text`, so the backend renders a `Code` like any other Group.

### `elements/shapes.py` — `Rectangle`, `Circle`, `Ellipse`, `Line`, `Polygon`, `Curve`

Geometric primitives extending `Drawable` with intrinsic dimensions and no children. The three filled shapes render as solid black with no stroke under the `Drawable` defaults; pass `fill_opacity=0` to make a layout placeholder, and `stroke_width > 0` to draw an outline.

- `Rectangle(width, height, ...)` → `#rect(width: Wcm, height: Hcm, fill: ..., stroke: ...)`. Bbox is `(width, height)`. A `corner_radius` rounds the corners (visual-only: the bbox is unchanged); it is a float for the four of them or a dict keyed by `"top-left"` / `"top-right"` / `"bottom-left"` / `"bottom-right"`, which the backend's `_typst_radius` turns into Typst's `radius:` length or per-corner dictionary. A dict naming something else raises at construction.
- `Circle(radius, ...)` → `#circle(radius: Rcm, fill: ..., stroke: ...)`. Bbox is `(2 radius, 2 radius)`.
- `Ellipse(width, height, ...)` → `#ellipse(width: Wcm, height: Hcm, fill: ..., stroke: ...)`. Bbox is `(width, height)`; semi-axes are `width/2` and `height/2`.

The three filled shapes dispatch through a single `_shape_markup(el)` helper that branches on the concrete type and resolves the four `Drawable` fields via `_typst_fill` / `_typst_stroke`. Measurement returns Typst's `measure()` of the emitted body, which matches the intrinsic dimensions.

- `Line(start, end, ...)` is stroke-only: `start` and `end` are points (cm) in the element's local frame, and the bbox is the axis-aligned box bounding them, so a horizontal line has zero height and a vertical line zero width. Bbox is `(|end.x - start.x|, |end.y - start.y|)`. `stroke_width` defaults to the `line.stroke_width` config value; `fill_*` is inert. The backend's `_line_markup(el)` normalizes the endpoints to the bbox's top-left in Typst's y-down frame and emits `#line(start: ..., end: ..., stroke: ...)`, so the segment draws inside its own bounding box and `measure()` returns `(|dx|, |dy|)`.

- `Polygon(points, ...)` is a filled, auto-closed polygon through a list of vertices (cm) in the element's local frame (at least three). Like `Line`, `_pos` is the centre of the box bounding the vertices and the stored `points` are relative to it (`get_points()` returns them in slide coords); the bbox is that vertex box. Fill/stroke follow the `Drawable` defaults. The backend's `_polygon_markup(el)` normalizes vertices to the bbox's top-left in Typst's y-down frame and emits `#polygon(fill:, stroke:, ...)`; Typst's `measure()` of a polygon is exactly the vertex box.

- `Curve(segments, ...)` is a filled/stroked Bézier path. `segments` is a list of `CurveSegment` instances drawn in order; the first must be a `MoveTo`. The segment types — `MoveTo(point)`, `LineTo(point)`, `CubicTo(control_start, control_end, point)`, `QuadTo(control, point)`, `Close()` — carry points (cm) in the curve's local frame and are pure geometry (a segment never references Typst; the backend dispatches on its type). `_pos` is the centre of the box bounding **every** referenced point (endpoints and control points), and the bbox is that control-point box — a conservative bound that always contains the drawn path (a Bézier lies within the convex hull of its control points). The backend's `_curve_markup(el)` normalizes all points to the bbox's top-left in Typst's y-down frame, emits the matching `curve.move`/`curve.line`/`curve.cubic`/`curve.quad`/`curve.close` calls, and wraps the `#curve` in a `#box` sized to the bbox, which fixes `measure()` to that size for placement and anchoring. (Typst's native `measure()` of a curve pins the box to the curve's origin and drops extents on the negative side.)

### `elements/spacing.py` — `VSpace`, `HSpace`

Invisible spacers extending `Element` (no fill/stroke) with intrinsic size and no rendered body. `VSpace(height)` has bbox `(0, height)`; `HSpace(width)` has bbox `(width, 0)`. The backend's `_spacer_markup(el)` emits an empty `#box(width: ..., height: ...)` so `measure()` returns the exact size while nothing is drawn. They report their size without a Typst query (`_INTRINSIC_SIZE` in `arrange`), and `arrange` drops the inter-element gap next to a spacer so the spacer alone sets the space between its neighbours.

### `elements/group.py` — `Group`

`Group` extends `Drawable` with no markup of its own. It is a real tree node (children are reparented on construction) and its bbox is the **union** of children's bboxes (omitted children excluded), so `group.center` (and `group.get_bbox_center()`) returns the visual center of all the contained content. `group.anchor` applies to that union bbox — `_current_anchor_point()` returns the corresponding corner of it.

A Group has no rendered body, so its own `fill_color` / `stroke_color` / `fill_opacity` / `stroke_width` are inert at render time. Their purpose is to serve as the receiver for the `set_*` bulk setters, which walk and rewrite every `Drawable` descendant.

Movement (`move_to`, `shift`) is inherited from `Element`: every fixed descendant follows the group's translation. `Group(children=[...])` adopts the iterable at construction; `group.add(el)` appends later (reparents and invalidates the tree's bbox cache). The backend recognises `Group` in `_render_node` (renders children, with fixed ones as placeholders just like a `Text` composite) and in `_assign` (overrides the metadata-derived size with the union).

### `hidden` propagation

`hidden` lives on `Element` (so it applies to nodes without a body too) and propagates through the parent chain via `Element.get_effective_hidden()`. The renderer applies it at every fixed `#place` block (`_render_placed` wraps the body in `#hide[...]` when an ancestor is hidden), so the flag reaches fixed descendants that have escaped lexical scope.

## Composition

### `composition/arrange.py` — `arrange`

`arrange(elements, pos, anchor, *, gap=0.0)` stacks elements in a single column, top-to-bottom in list order, with bboxes flush against each other (plus `gap` between them). The stack as a whole is anchored at `pos` with mode `anchor`: the union bbox is sized as `(max(widths), sum(heights))` (conceptually) and positioned so its `anchor` point lands at `pos`. The horizontal half of `anchor` picks the alignment of bboxes inside the stack (`*-left` → flush left, `*-center` → centered, `*-right` → flush right); the vertical half picks where `pos.y` sits relative to the stack (`top-*` → top edge, `center-*` → vertical center, `bottom-*` → bottom edge). Each element is moved via `move_to`, which honors that element's own anchor.

The `gap` is per-pair: it is inserted between two consecutive elements only when neither is a spacer (`VSpace` / `HSpace`). A spacer carries its own height, so it alone sets the space between its neighbours — `arrange([A, VSpace(v), B], gap=g)` puts `v` between `A` and `B`, not `v + 2g`.

Math note: writing out the per-element `pos.x` in terms of the stack's `pos.x`, the stack's `h_mul`, the element's own `h_mul`, and its width, the stack's `total_width` cancels — only the element's own width is needed. So `arrange` never computes `max(widths)` and only reads `get_width()` for elements whose horizontal anchor half differs from the stack's.

Before the positioning loop it collects the elements that need a measured bbox — everything except the intrinsic-size types (`Rectangle`, `Circle`, `Ellipse`, `Line`, `Polygon`, `Curve`, `VSpace`, `HSpace`), which report their own dimensions — and runs `measure_all` over that subset, so the worst case is one Typst query for the whole call. A stack of intrinsic-size elements pays zero queries.

### `composition/layout.py` — `Region`, `Layout`

`Region` is a rectangle (centre, width, height) plus a default `anchor` and `arrange_gap`. It exposes `center`; `left`/`right`/`top`/`bottom` as the midpoint `Vec` of each edge; and `get_anchor_point(anchor)` for the nine anchor points. Slide-relative classmethods (`Region.create_full()`, `create_left(w)`, `create_right(w)`, `create_top(h)`, `create_bottom(h)`, `create_inner(*, left=, right=, top=, bottom=)`) read the slide size from `config` and build regions from it; `create_inner` takes side regions and returns what's left after subtracting each side's extent from the slide. `Region.merge_regions(regions)` is a static helper returning the bounding region of several. `adjust_borders(left=, right=, top=, bottom=)` mutates in place by moving each border outward (positive) or inward (negative); chained setters `set_width`/`set_height`/`set_center`/`set_arrange_gap` follow the same return-self pattern. `grid(template, *, hgap=, vgap=, width_ratios=, height_ratios=)` splits the region and merges cells sharing a label into one sub-`Region` (sub-regions inherit the parent's `anchor` and `arrange_gap`).

Region owns its elements: `add(el)`, `remove(el)`, `replace(old, new)`, `remove_all()` mutate `region.elements`. `region.arrange()` stacks `region.elements` via `composition.arrange.arrange` using the region's own `anchor` and `arrange_gap` (line-height heights for Text).

`Layout` is a named container of `Region`s: `Layout()` starts empty; regions are attached with `layout.add(name, region)` (which returns the region) or by direct attribute assignment (`layout.header = Region.create_top(2.0)`). `layout.regions` is the read-only mapping of name to `Region`. `layout.active` (initially `None`) is set with `set_active(region_or_name)` and serves as the "current region" pointer. `layout.remove_all_elements()` clears every region's `elements`.

### `composition/utils.py` — composition helpers

`layout_to_group(layout, **drawable_kw)` returns a `Group` of one sub-`Group` per region, each holding a `Rectangle` matching the region (with `drawable_kw` forwarded, so the caller picks outline vs. fill) and a `Text` of the region name centred on it.

`config.py` holds the process-global `config` singleton. It owns a flat store of defaults keyed by dotted paths — `config.get("region.content.anchor")` / `config.set(key, value)` — which templates read as starting values and may override; `get` raises on an undefined key. The slide size lives in this store under `slide.width`/`slide.height`; `config.slide_width`/`slide_height` are read-only views of those keys (read by `Region.create_*`). The color palette is `config.colors`, a `Colors` registry: `config.colors.get(name)` returns the hex for a palette name, passes a literal hex string through unchanged, and raises on anything else; `config.colors.set(name, hex)` defines a name. `config.templates` is the ordered list of template file names a `Presentation` inherits from (see `templates/`). `config.font_paths` is a list of extra font directories the backend hands to Typst (on top of the project `fonts/` dir). `config.apply_overrides(values)` sets each key after checking it against the defined keys, raising on an undefined one.

### `templates/` — the template stack

`config.templates` lists template entries (e.g. `["nice"]`); `load_template` resolves each to a module's `PresentationTemplate` class — a `.py` file path is loaded directly, any other name is the built-in `mate.templates.<name>`. The driver resolves a front-matter entry to a sibling `<name>.py` next to the Markdown file when present, else keeps it as a built-in name. Each `PresentationTemplate` subclasses the base `PresentationTemplate`. `Presentation.__new__` reads `config.templates` and builds a dynamic subclass whose bases are `(Presentation, *template_classes)`, so the MRO is `Presentation → templates… → PresentationTemplate`. A template sets config in its `__init__` (before `super().__init__()`) and overrides methods like `add_footer`. Earlier-listed templates take precedence for overridden methods.

`resolve_code_options(options, region, code_kwargs, code_class=Code)` turns a code fence's verbatim property text into a target `Region` and the keyword arguments of a `Code`, resolving `region=` and defaulting `width` to the region's width minus the ambient indent. The valid option names come from `code_class`, walking every `__init__` from it down to `Code` (`_code_options`): a subclass's own parameters are accepted as fence options and listed in the error for an unknown one. A template restyling code blocks overrides `add_code`, calls the helper with its class, and attaches the element to the slide and the region itself.

A `Presentation` is built from Markdown with an optional leading `---` YAML front matter (`mate.parser.ir.FrontMatter`: `templates`, `config`, `colors`, `font_paths`). The driver assigns `config.templates` and `config.font_paths` (resolved relative to the Markdown file) before construction and passes the `FrontMatter` to `Presentation`. `PresentationTemplate.__init__` applies the front matter's `config`/`colors` after the templates' `__init__` and before reading any value into its attributes, so front-matter values take precedence over template values.

### Why a uniform tree

A `Text` with subs is internally a tree of `Text`s. When `Square`, `Triangle`, etc. are added later they all live in the same tree under an `Element` root. Renderer and measurer walk `children` without knowing the concrete type (except where type-specific dispatch is needed, like Text → glyphs).

## Backend

### `backends/typst.py`

Two classes with separate responsibilities:

**`TypstRenderer`** — assembles the document source and compiles it to PDF. `render_snapshot(elements, canvas)` returns the fixed-element placements of one page (a slide's reveal step) as a fragment string (no page preamble, no pagebreak); `compile_document(fragments, canvas, path)` emits the `#set page(...)` preamble once, joins the fragments with `#pagebreak()`, and hands the in-memory source to the bundled Typst compiler — no intermediate `.typ` is written. A `Slide` captures its snapshots when `end_slide` seals it — the renderer never measures to render, so this is a cheap string build. Slide coords are y-up with origin at the slide centre; the renderer applies the user→Typst transform (`dx = _pos.x + W/2`, `dy = H/2 - _pos.y`) so user `(0, 0)` lands at the page centre. Each fixed element with `_anchor == "top-left"` becomes a plain `#place(top + left, dx: (_pos.x + W/2) cm, dy: (H/2 - _pos.y) cm, [body])` — no inline measure (it's the only anchor where both `h_mul == 0` and `(1 - v_mul) == 0`). Every other anchor becomes a `#context { let __b = [body]; let __s = measure(__b); place(top + left, dx: (_pos.x + W/2) cm - h_mul * __s.width, dy: (H/2 - _pos.y) cm - (1 - v_mul) * __s.height, __b) }` block, where `(h_mul, v_mul) = anchor_offsets(_anchor)`. Typst evaluates `measure(...)` at compile time, so Python never measures to render. Other emitted forms: `#text(font:, size:, fill:)[...]`, `#box(rotate(...))`, `#hide[...]`, `#pagebreak()`.

**`TypstMeasurer`** — writes an auxiliary `.typ` (at `.mate_cache/measure.typ`) and runs an in-process `typst.query` to obtain bboxes. Constructed with a list of root elements (any subtree, attached to a slide or not) and writes results into `el._bbox` for every reachable node. The aux document opens with `#set page(margin: 0cm)` — page width/height are intentionally left at Typst's default (measurement is page-size agnostic) but the margin must be zero so that `#place(top + left, dx, dy)` (body-relative) and `here().position()` (page-absolute) share the same coordinate system. The measurer invokes `_render_placed` with `canvas=None`, which skips the user→Typst centring/y-flip the renderer applies: the aux doc keeps fixed ancestors at their raw user-coord `(dx, dy)`, which lets each inline `here().position().x` probe return the user-x directly (no offset to subtract). The aux doc never has to be visually correct; only the x probe values are read back.

Module-level helpers (shared by both classes):
- `_collect_fixed(el)` — recursively gathers descendants with `placement == "fixed"`.
- `_render_placed(el, render_node)` — emits the `#place` and recurses. The body-render function is passed as a callable; it is the only thing that differs between renderer and measurer.
- `_wrap_rotate(el, body)` — wraps `body` in `#box(rotate(-angle deg, origin: center + horizon, reflow: true)[...])` when `el.angle` is nonzero, applied to every node's body in `_bare` and both `_render_node`s, and to a math fragment's body in `_math_fragment_markup` (re-entering math for the fragment's equation typesetting); measured size and rendered mark then carry the same rotation. The negated sign maps `el.angle` (counterclockwise, y-up) onto Typst's clockwise `#rotate`; `reflow: true` makes `measure(...)` report the rotated bounding box. The `#box` keeps the rotation inline (a bare `#rotate` is a block that breaks the surrounding paragraph): an inline run spins within its own line.
- `_markdown_to_typst`, `_bare`, `_write` — utilities. `_markdown_to_typst` translates a leaf `Text`'s Markdown content (`**bold**`, `*italic*`/`_italic_`, `` `code` ``, inline `$math$`, display `$$math$$`, a trailing backslash before a newline as a hard line break) into Typst markup, backslash-escaping every other special character; it is the only place the Markdown-to-Typst mapping lives. A leaf with `verbatim=True` goes through `_verbatim_to_typst` instead, which backslash-escapes all punctuation and turns spaces into no-break spaces.

#### Measurement logic (the subtle part)

For each `Element` (other than `"omitted"`, which is pruned everywhere) we need:

- **(w, h)**: the *isolated* size of the element. Obtained by writing a `#context [ ... ]` block with one `#metadata((id, w: measure(...).width/1cm, h: ...))<bbox>` per element.
- **x**: the *actual* horizontal position after parent flow, only for inline elements. Obtained by injecting `#context { let p = here().position(); [#metadata((id, x: p.x/1cm))<bbox>] }` right before the inline child, inside the page-rendered tree.
- **y**: by convention, `bbox.y` of an inline element equals `ancestor_top_y - h/2` — the centre under the rule that the inline body's top sits at the line top of the nearest fixed ancestor. Equivalently, for a fixed ancestor with `_pos.y`, anchor multiplier `v_mul`, and measured height `h`, its top edge in y-up slide coords is `_pos.y + (1 - v_mul) * h`; this value is threaded down through `_assign` as `ancestor_top_y`. This is what makes `shift((0, 0))` on an inline element a true visual no-op: freezing `_pos` to the measured anchor point and re-emitting overlaps the inline rendering. Typst's `here().position().y` returns the cursor baseline, not the line top, so it cannot be used directly.

Everything is emitted under the same `<bbox>` label and recovered in a single `typst.query(..., field="value", ignore_system_fonts=True, font_paths=_font_paths())` call. Telling apart size and x is done by checking which key is present in the JSON entry.

#### Persistent size cache

The isolated `(w, h)` of an element is a pure function of the Typst body handed to `measure(...)`, the fonts it resolves against, and the compiler version. `MeasureCache` stores those sizes on disk (`.mate_cache/measure_cache.json`) keyed by `_size_cache_key(body, font_signature)` — a SHA-256 over the body, the font signature (path/size/mtime of every file under `_font_paths()`), the `typst` package version, and a format-version constant. A measurement pass serves every hit from the cache and emits a `measure(...)` record only for the misses; when no size misses and no inline-`x` probes remain, the pass runs no Typst query at all. The file is rewritten on interpreter exit with exactly the keys touched in the run, keeping it scoped to the current deck. Inline-`x` records are flow-dependent and are not cached.

#### Fonts

`query` (measure) and `compile` (render) both run with `ignore_system_fonts=True` and the same `_font_paths()`: Typst's embedded faces, the project `fonts/` directory, and the `config.font_paths` directories.

Each family used by a `Text` is checked against `typst.Fonts(...).families()` for the current `_font_paths()` before measuring, case-insensitively; an unresolved family raises. The family set is enumerated once per `font_paths` set and cached.

## Logging

### `log.py` — the `mate` logger

A single `logging` logger named `mate`, attached to a rich `RichHandler`, carries both output layers: user-facing progress at INFO and developer narration at DEBUG. "Debug mode" is the logger sitting at DEBUG level — there is no separate flag. `config.set_debug(enabled)` sets it by writing the logger's level, so the level stays the single source of truth (no parallel boolean).

Messages opt into rich markup per call with `extra={"markup": True, "highlighter": None}`; the handler leaves markup off by default so message data containing brackets is not mangled. Narration is hand-placed `logger.debug(...)` at the lifecycle points worth watching, in library code rather than user scripts, so the same presentation script run with debug on streams the events. Guard an expensive debug payload with `if logger.isEnabledFor(logging.DEBUG)` before building it.

## How to extend

### Add an element type (e.g. `Square`)

1. Add `class Square(Element)` to `elements/shapes.py` (for another shape) or create a new file (for a non-shape element). Define `__init__` with size/style and override `_copy(mapping)` to copy your fields.
2. Re-export from `elements/__init__.py` and `mate/__init__.py`.
3. In `backends/typst.py`, add the dispatch in `_bare`, `_shape_markup` (for shapes), and the `_render_node` of both renderer and measurer (the `isinstance` dispatch lives there because the backend is the one that knows how to translate each type). Update the `_render_placed` cascade guard (`isinstance(el, (Rectangle, Circle, Ellipse))`) if your element carries its own fill.

### Add a backend (e.g. SVG)

1. Create `backends/svg.py` exposing `SvgRenderer` and `SvgMeasurer` with the same public interface (`render(presentation)`, `measure()`).
2. Switch the import in `core/presentation.py` (or parametrize the presentation with the backend if runtime swapping is desired).

## Notes

- `.mate_cache/` is created automatically. Deleting it breaks nothing — it is regenerated on the next measurement.
- `Presentation.write` compiles to `<name>.pdf` in the cwd. The measurement path is internal to the backend (`.mate_cache/measure.typ`).
- `_mid` is global and monotonic. Sufficient as long as a single Presentation is built per process. If isolation is needed later, move it to a per-`Presentation` counter.
