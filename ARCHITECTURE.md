# mate — architecture

A Python-driven presentation tool.

## Design principles

1. **All logic in Python.** The backend is dumb: it receives "draw this here" and "measure this" instructions.
2. **Backend-agnostic.** To add another backend (LaTeX, SVG, canvas, etc.) only `backends/` is touched. The rest of the project knows nothing about Typst syntax.
3. **Uniform bbox.** Every `Element` (text, shapes, lines, ...) exposes `(x, y, w, h)` in cm, where `(x, y)` is the geometric **centre** in slide coordinates. Without this there is no coherent layout.
4. **Lazy, cached measurement.** Measuring spawns a Typst subprocess (~25 ms with `--ignore-system-fonts`); results are cached until something changes.

## Folder structure

```
mate/
├── __init__.py        # public re-exports
├── config.py          # process-global `config` singleton (slide size, color palette)
├── demo.py            # usage example
├── pyproject.toml
├── core/              # primitives and central abstractions
│   ├── vec.py
│   ├── element.py
│   └── presentation.py
├── elements/          # concrete visual element types
│   ├── group.py
│   ├── shapes.py
│   └── text.py
├── backends/          # backend-specific renderers/measurers
│   └── typst.py
├── utils/             # layout helpers built on top of the core model
│   ├── arrange.py
│   └── layout.py
└── .cache/            # regenerated artifacts (measurement); safe to delete
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
| `_mid` | Globally unique id, used by the backend for metadata. |
| `_bbox` | Cached `(x, y, w, h)` or `None` (not measured). `(x, y)` is the geometric **centre** in slide coords (y-up); `w` and `h` are positive extents. Edges: `left = x - w/2`, `right = x + w/2`, `bottom = y - h/2`, `top = y + h/2`. |

Public API: `move_to / shift / set_anchor / get_bbox / get_width / get_height / get_bbox_center / copy` plus the `pos`, `anchor`, and `center` properties. Movement (`move_to` / `shift`) forces `placement = "fixed"` and invalidates the bbox cache of the whole tree.

All `Element` constructor parameters (`pos`, `anchor`, `placement`, `id`) are **keyword-only** — subclasses keep their intrinsic positional args (`Rectangle(width, height, ...)`, `Circle(radius, ...)`, `Text(source, ...)`, `Group(children, ...)`) but everything else flows as `**kwargs`. The split is enforced by the `*` in each `__init__`.

- `move_to(p)` — sets `_pos = p`. Reads the current visual anchor point via `_current_anchor_point()` (no measurement for fixed non-Group; measures for inline or Group), and translates every fixed descendant by `p - <old anchor point>` so the subtree moves as a unit.
- `shift(d)` — adds `d` to `_pos` (accumulates over repeated calls). When the element is `"inline"`, freezes `_pos` to its measured anchor point first, so the increment is taken from the flowed position. Same propagation: every fixed descendant gets `+= d`.
- `set_anchor(anchor)` — changes `_anchor` without modifying `_pos`. The visual position shifts so the new anchor point sits at the same coordinate. Invalidates the bbox cache.
- `get_width()` / `get_height()` — return bbox width/height in cm; shape primitives override with their intrinsic values (no measurement). `Text.get_height(line=True)` returns the cached font line-slot height.
- `get_bbox_center()` — always measures (cache miss → subprocess) and returns the bbox center. Use `center` when the cheaper fast path is enough.

**Inline → fixed freeze.** Inline elements have no anchor of their own — their visible position only exists after Typst lays them out. The freeze captures the current anchor point (`_current_anchor_point()` derives it from the measured bbox and the anchor's offsets) and stores it in `_pos` before applying the increment, which makes `shift((0, 0))` a true visual no-op. The cost is one measurement when the bbox cache is cold.

**Movement propagates by default.** Mutating an element's position translates every fixed descendant by the same delta (`_translate` walks the subtree). `"inline"` descendants are not touched (their `_pos` is meaningless under flow), but the recursion descends through them so fixed grand-descendants still follow.

**Cache invalidation is geometric only.** `move_to`, `shift`, `set_anchor`, and the intrinsic-size setters (`set_width`, `set_height`, `set_radius`) call `_invalidate_tree`, which clears `_bbox` on every node in the tree (a position or anchor change can shift the flowed `x` of inline siblings, so the whole tree must be re-measured). Visual-only mutators (color, opacity, stroke, hidden) leave the cache alone, since they do not affect typesetting size.

**Placement semantics.** The renderer skips `"omitted"` elements at every level. `"inline"` only makes sense as a descendant of a fixed element — at the slide root it is treated like `"omitted"` for rendering, since there is no parent flow to participate in. The parser in `Text` produces `"inline"` subs by default; users opt into placement explicitly with `move_to` or `shift`.

**`Group.center` and `Group._current_anchor_point` always measure.** A `Group` has no rendered body, so its visual position is the union of children's bboxes — not the stored `_pos`. Both reads override the base to measure on every call. The stored `_pos` exists so `move_to`/`shift` arithmetic is uniform across subclasses; it is not a reliable query of "where is the group".

**`measure_all(elements)`** is the batch-measurement helper. It deduplicates the tree roots reached from the input and runs one `TypstMeasurer` over them, filling `_bbox` everywhere in one Typst subprocess. Layout utilities (`arrange`) use it to amortize measurement over N elements.

**Copy protocol.** `copy()` is the public entry. `Element._copy(mapping)` uses `copy.copy(self)` to duplicate the instance's `__dict__` and then resets identity-bearing fields (`_mid`, `id`, `parent`, `_bbox`) and deep-clones `children`. Intrinsic-data fields (`w`, `h`, `r`, `content`, ...) come along automatically, so `Rectangle` / `Circle` / `Ellipse` need no override. Only subclasses with **cross-references between descendants** override — `Text._copy` calls `super()._copy(mapping)` and then remaps its `subs` list through the shared `mapping`, so the cloned subs point at the cloned descendants.

### `core/presentation.py` — `Presentation`, `Slide`

- `Presentation` owns the global `width` / `height` (every slide has the same size) and the list of `Slide`s. `write(path)` delegates to `TypstRenderer`.
- `Slide` is a thin container — it holds `elements` (root list) and that's it. `add(element)` just appends and returns it for chaining. Root elements keep `parent = None` (the slide is not itself an `Element`).
- Measurement is **independent of slide membership**. An orphan element can call `get_bbox()` and the measurer runs over its own tree (rooted at the topmost ancestor reachable via `parent`). The slide never appears in the measurement path.

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

Every `Text` carries explicit `font: str` and `size: float` (points) as keyword-only constructor params. Defaults are the Typst defaults hardcoded as constants (`DEFAULT_FONT = "libertinus serif"`, `DEFAULT_SIZE_PT = 11.0`). The backend wraps every rendered/measured Text in `#text(font: "...", size: ...pt, ...)`. Sub-elements built by the parser inherit the parent's font/size, propagated in the constructor after `_take_children`. `Text.get_line_height()` measures a reference glyph string (with ascenders and descenders) at the element's `(font, size)`, caches the result in the module-level `_line_height_cache`, and returns the line slot in cm — content-independent and content-cheap on cache hit. `Text.get_height(line=True)` returns that slot instead of the measured bbox height.

Only `fill_color` / `fill_opacity` reach Typst (folded into the same `#text(...)` wrapper as `font` and `size`); `stroke_*` is accepted but currently ignored for text rendering.

**`_copy()`** override re-maps the `subs` list using the shared `mapping` from `Element._copy`, so the cloned subs point at the cloned descendants. Clones inherit structure but are not registered in `id_registry`: the registry indexes user-tagged originals.

### `elements/shapes.py` — `Rectangle`, `Circle`, `Ellipse`

Three filled-shape primitives extending `Drawable` with intrinsic dimensions and no children. With the `Drawable` defaults they render as solid black with no stroke; pass `fill_opacity=0` to make a layout placeholder, and `stroke_width > 0` to draw an outline.

- `Rectangle(width, height, ...)` → `#rect(width: Wcm, height: Hcm, fill: ..., stroke: ...)`. Bbox is `(width, height)`.
- `Circle(radius, ...)` → `#circle(radius: Rcm, fill: ..., stroke: ...)`. Bbox is `(2 radius, 2 radius)`.
- `Ellipse(width, height, ...)` → `#ellipse(width: Wcm, height: Hcm, fill: ..., stroke: ...)`. Bbox is `(width, height)`; semi-axes are `width/2` and `height/2`.

Measurement returns Typst's `measure()` of the emitted body, which matches the intrinsic dimensions for all three. The backend dispatches them through a single `_shape_markup(el)` helper that branches on the concrete type and resolves the four `Drawable` fields via `_typst_fill` / `_typst_stroke`.

### `elements/group.py` — `Group`

`Group` extends `Drawable` with no markup of its own. It is a real tree node (children are reparented on construction) and its bbox is the **union** of children's bboxes (omitted children excluded), so `group.center` (and `group.get_bbox_center()`) returns the visual center of all the contained content. `group.anchor` still applies — `_current_anchor_point()` returns the corresponding corner of the union bbox.

A Group has no rendered body, so its own `fill_color` / `stroke_color` / `fill_opacity` / `stroke_width` are inert at render time. Their purpose is to serve as the receiver for the `set_*` bulk setters, which walk and rewrite every `Drawable` descendant.

Movement (`move_to`, `shift`) is inherited from `Element`: every fixed descendant follows the group's translation. `Group(children=[...])` adopts the iterable at construction; `group.add(el)` appends later (reparents and invalidates the tree's bbox cache). The backend recognises `Group` in `_render_node` (renders children, with fixed ones as placeholders just like a `Text` composite) and in `_assign` (overrides the metadata-derived size with the union).

### `hidden` propagation

`hidden` lives on `Element` (so it applies to nodes without a body too) and propagates through the parent chain via `Element.get_effective_hidden()`. The renderer applies it at every fixed `#place` block (`_render_placed` wraps the body in `#hide[...]` when an ancestor is hidden), so the flag reaches fixed descendants that have escaped lexical scope.

## Utilities

### `utils/arrange.py` — `arrange`

`arrange(elements, pos, anchor, *, line_height=False)` stacks elements in a single column, top-to-bottom in list order, with bboxes flush against each other at zero gap. The stack as a whole is anchored at `pos` with mode `anchor`: the union bbox is sized as `(max(widths), sum(heights))` (conceptually) and positioned so its `anchor` point lands at `pos`. The horizontal half of `anchor` picks the alignment of bboxes inside the stack (`*-left` → flush left, `*-center` → centered, `*-right` → flush right); the vertical half picks where `pos.y` sits relative to the stack (`top-*` → top edge, `center-*` → vertical center, `bottom-*` → bottom edge). Each element is moved via `move_to`, which honors that element's own anchor.

Math note: writing out the per-element `pos.x` in terms of the stack's `pos.x`, the stack's `h_mul`, the element's own `h_mul`, and its width, the stack's `total_width` cancels — only the element's own width is needed. So `arrange` never computes `max(widths)` and only reads `get_width()` for elements whose horizontal anchor half differs from the stack's.

Performance is the reason this helper exists as a single function rather than a couple of inlined lines. Before the positioning loop it identifies which elements will end up needing a real bbox — elements whose horizontal anchor half differs from the stack's (require width) plus elements without an intrinsic height (`Text` under `line_height=False`, or custom subclasses) — and runs `measure_all` over that subset, so the worst case is one Typst subprocess for the whole call. A stack of shape primitives whose anchors all share the stack's horizontal half pays zero subprocesses; a stack of similarly-anchored `Text`s with `line_height=True` pays one subprocess to seed the line-height cache for a given `(font, size)` and zero afterwards.

### `utils/layout.py` — `Region`, `Layout`

`Region` is a rectangle (centre, width, height) plus a default `anchor` and `arrange_gap`. It exposes `center`; `left`/`right`/`top`/`bottom` as the midpoint `Vec` of each edge; and `get_anchor_point(anchor)` for the nine anchor points. Slide-relative classmethods (`Region.create_full()`, `create_left(w)`, `create_right(w)`, `create_top(h)`, `create_bottom(h)`, `create_inner(*, left=, right=, top=, bottom=)`) read the slide size from `config` and build regions from it; `create_inner` takes side regions and returns what's left after subtracting each side's extent from the slide. `Region.merge_regions(regions)` is a static helper returning the bounding region of several. `adjust_borders(left=, right=, top=, bottom=)` mutates in place by moving each border outward (positive) or inward (negative); chained setters `set_width`/`set_height`/`set_center`/`set_arrange_gap` follow the same return-self pattern. `grid(template, *, hgap=, vgap=, width_ratios=, height_ratios=)` splits the region and merges cells sharing a label into one sub-`Region` (sub-regions inherit the parent's `anchor` and `arrange_gap`).

Region owns its elements: `add(el)`, `remove(el)`, `replace(old, new)`, `remove_all()` mutate `region.elements`. `region.arrange()` stacks `region.elements` via `utils.arrange.arrange` using the region's own `anchor` and `arrange_gap` (line-height heights for Text). `region.get_bbox_el(**drawable_kw)` returns a `Rectangle` matching this region for debug overlays.

`Layout` is a named container of `Region`s: `Layout(**regions)` stores each kwarg as an attribute, and regions can also be attached afterward (`layout.header = Region.create_top(2.0)`) or via `layout.add(name, region)`. `layout.active` (initially `None`) is set with `set_active(region_or_name)` and serves as the "current region" pointer. `layout.remove_all_elements()` clears every region's `elements`. `layout.get_bbox_el_for_each_region(**drawable_kw)` returns a `Group` containing one `Region.get_bbox_el` per stored region.

`config.py` holds the process-global `config` singleton: the slide size (`config.slide_width`/`slide_height`, read by `Region.create_*`, written by `Presentation.__init__` via `config.set_slide_size(width, height)`) and the color palette (`config.colors`, a `Colors` registry). `config.colors.get(name)` returns the hex for a palette name, passes a literal hex string through unchanged, and raises on anything else; `config.colors.set(name, hex)` defines a name.

### Why a uniform tree

A `Text` with subs is internally a tree of `Text`s. When `Square`, `Triangle`, `Line`, etc. are added later they all live in the same tree under an `Element` root. Renderer and measurer walk `children` without knowing the concrete type (except where type-specific dispatch is needed, like Text → glyphs).

## Backend

### `backends/typst.py`

Two classes with separate responsibilities:

**`TypstRenderer`** — writes the final `.typ` the user compiles to PDF. Slide coords are y-up with origin at the slide centre; the renderer applies the user→Typst transform (`dx = _pos.x + W/2`, `dy = H/2 - _pos.y`) so user `(0, 0)` lands at the page centre. Each fixed element with `_anchor == "top-left"` becomes a plain `#place(top + left, dx: (_pos.x + W/2) cm, dy: (H/2 - _pos.y) cm, [body])` — no inline measure (it's the only anchor where both `h_mul == 0` and `(1 - v_mul) == 0`). Every other anchor becomes a `#context { let __b = [body]; let __s = measure(__b); place(top + left, dx: (_pos.x + W/2) cm - h_mul * __s.width, dy: (H/2 - _pos.y) cm - (1 - v_mul) * __s.height, __b) }` block, where `(h_mul, v_mul) = anchor_offsets(_anchor)`. Typst evaluates `measure(...)` at compile time, so Python never measures to render. Other emitted forms: `#text(font:, size:, fill:)[...]`, `#hide[...]`, `#pagebreak()`.

**`TypstMeasurer`** — writes an auxiliary `.typ` (at `.cache/measure.typ`) and runs `typst query` to obtain bboxes. Constructed with a list of root elements (any subtree, attached to a slide or not) and writes results into `el._bbox` for every reachable node. The aux document opens with `#set page(margin: 0cm)` — page width/height are intentionally left at Typst's default (measurement is page-size agnostic) but the margin must be zero so that `#place(top + left, dx, dy)` (body-relative) and `here().position()` (page-absolute) share the same coordinate system. The measurer invokes `_render_placed` with `canvas=None`, which skips the user→Typst centring/y-flip the renderer applies: the aux doc keeps fixed ancestors at their raw user-coord `(dx, dy)`, which lets each inline `here().position().x` probe return the user-x directly (no offset to subtract). The aux doc never has to be visually correct; only the x probe values are read back.

Module-level helpers (shared by both classes):
- `_collect_fixed(el)` — recursively gathers descendants with `placement == "fixed"`.
- `_render_placed(el, render_node)` — emits the `#place` and recurses. The body-render function is passed as a callable; it is the only thing that differs between renderer and measurer.
- `_escape`, `_bare`, `_write` — utilities.

#### Measurement logic (the subtle part)

For each `Element` (other than `"omitted"`, which is pruned everywhere) we need:

- **(w, h)**: the *isolated* size of the element. Obtained by writing a `#context [ ... ]` block with one `#metadata((id, w: measure(...).width/1cm, h: ...))<bbox>` per element.
- **x**: the *actual* horizontal position after parent flow, only for inline elements. Obtained by injecting `#context { let p = here().position(); [#metadata((id, x: p.x/1cm))<bbox>] }` right before the inline child, inside the page-rendered tree.
- **y**: by convention, `bbox.y` of an inline element equals `ancestor_top_y - h/2` — the centre under the rule that the inline body's top sits at the line top of the nearest fixed ancestor. Equivalently, for a fixed ancestor with `_pos.y`, anchor multiplier `v_mul`, and measured height `h`, its top edge in y-up slide coords is `_pos.y + (1 - v_mul) * h`; this value is threaded down through `_assign` as `ancestor_top_y`. This is what makes `shift((0, 0))` on an inline element a true visual no-op: freezing `_pos` to the measured anchor point and re-emitting overlaps the inline rendering. Typst's `here().position().y` returns the cursor baseline, not the line top, so it cannot be used directly.

Everything is emitted under the same `<bbox>` label and recovered in a single `typst query --ignore-system-fonts ... --field value` call. Telling apart size and x is done by checking which key is present in the JSON entry.

#### Why `--ignore-system-fonts`

Without the flag, Typst scans system fonts on every query (~400 ms). With it, ~25 ms. The cost is no longer being able to refer to local fonts by name, which we do not use today.

## How to extend

### Add an element type (e.g. `Square`)

1. Add `class Square(Element)` to `elements/shapes.py` (for another shape) or create a new file (for a non-shape element). Define `__init__` with size/style and override `_copy(mapping)` to copy your fields.
2. Re-export from `elements/__init__.py` and `mate/__init__.py`.
3. In `backends/typst.py`, add the dispatch in `_bare`, `_shape_markup` (for shapes), and the `_render_node` of both renderer and measurer (the `isinstance` dispatch lives there because the backend is the one that knows how to translate each type). Update the `_render_placed` cascade guard (`isinstance(el, (Rectangle, Circle, Ellipse))`) if your element carries its own fill.

### Add a backend (e.g. SVG)

1. Create `backends/svg.py` exposing `SvgRenderer` and `SvgMeasurer` with the same public interface (`render(presentation)`, `measure()`).
2. Switch the import in `core/presentation.py` (or parametrize the presentation with the backend if runtime swapping is desired).

## Notes

- `.cache/` is created automatically. Deleting it breaks nothing — it is regenerated on the next measurement.
- Default path of `Presentation.write` is `"presentation.typ"` in cwd. The measurement path is internal to the backend (`.cache/measure.typ`).
- `_mid` is global and monotonic. Sufficient as long as a single Presentation is built per process. If isolation is needed later, move it to a per-`Presentation` counter.
