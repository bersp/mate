# mate — architecture

A Python-driven presentation tool.

## Design principles

1. **All logic in Python.** The backend is dumb: it receives "draw this here" and "measure this" instructions.
2. **Backend-agnostic.** To add another backend (LaTeX, SVG, canvas, etc.) only `backends/` is touched. The rest of the project knows nothing about Typst syntax.
3. **Uniform bbox.** Every `Element` (text, shapes, lines, ...) exposes `(x, y, w, h)` in cm. Without this there is no coherent layout.
4. **Lazy, cached measurement.** Measuring spawns a Typst subprocess (~25 ms with `--ignore-system-fonts`); results are cached until something changes.

## Folder structure

```
mate/
├── __init__.py        # public re-exports
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
│   └── layout.py
└── .cache/            # regenerated artifacts (measurement); safe to delete
```

## Model

### `core/vec.py` — `Vec`

A 2D `np.ndarray` subclass with `.x` and `.y`. Use it whenever something has "two coordinates" (position, size, center). Inherits numpy arithmetic and broadcasting for free.

### `core/element.py` — `Element`

Base class of **everything** that appears on a slide. Attributes:

| Attribute | Meaning |
|---|---|
| `pos` | Stored anchor point `Vec` in slide coordinates (cm). Public, read via property; writes go to `_pos`. Never measures. |
| `_pos` | Storage backing `pos`. Internal hot paths (`_translate`, backend) read/write this directly. |
| `anchor` | Which point of the bbox sits at `_pos`. One of the nine `Anchor` strings: `"top-left"`, `"top-center"`, `"top-right"`, `"center-left"`, `"center"` (default), `"center-right"`, `"bottom-left"`, `"bottom-center"`, `"bottom-right"`. Resolved into `(h_mul, v_mul)` multipliers by `anchor_offsets(anchor)` such that `bbox.top_left = _pos - (h_mul * w, v_mul * h)`. |
| `_anchor` | Storage backing `anchor`. |
| `center` | Visual bbox center `Vec`. Property: fast path returns `_pos` when `_anchor == "center"` and the element is not inline; otherwise measures. `Group` overrides it to always return the union-bbox center. |
| `placement` | `"fixed"` (drawn with the body's `_anchor` point at `_pos`), `"inline"` (flows in parent's content), or `"omitted"` (not rendered, not measured). |
| `parent` | Owning `Element` (set automatically when adopted via `_take_children`); `None` for root elements directly attached to a `Slide`. |
| `hidden` | If `True`, the element takes space but is not drawn. Propagates through ancestors via `get_effective_hidden()` — `hidden=True` on a Group hides the whole subtree at render time. |
| `children` | List of sub-`Element`s. Forms a tree. |
| `_mid` | Globally unique id, used by the backend for metadata. |
| `_bbox` | Cached `(x, y, w, h)` or `None` (not measured). |

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

### `utils/layout.py` — `arrange`

`arrange(elements, line_height=False)` stacks elements in a single column, top-to-bottom, bboxes flush against each other and sharing the first element's left `x`. The first element keeps its position; the rest are moved via `move_to`, which honors each element's own anchor.

Performance is the reason this helper exists as a single function rather than a couple of inlined lines. Before the positioning loop it identifies which elements will end up needing a real bbox — non-left-anchored elements (require width) plus elements without an intrinsic height (`Text` under `line_height=False`, or custom subclasses) — and runs `measure_all` over that subset, so the worst case is one Typst subprocess for the whole call. A stack of left-anchored shape primitives pays zero subprocesses; a stack of left-anchored `Text`s with `line_height=True` pays one subprocess to seed the line-height cache for a given `(font, size)` and zero afterwards.

### Why a uniform tree

A `Text` with subs is internally a tree of `Text`s. When `Square`, `Triangle`, `Line`, etc. are added later they all live in the same tree under an `Element` root. Renderer and measurer walk `children` without knowing the concrete type (except where type-specific dispatch is needed, like Text → glyphs).

## Backend

### `backends/typst.py`

Two classes with separate responsibilities:

**`TypstRenderer`** — writes the final `.typ` the user compiles to PDF. Each fixed element with `_anchor == "top-left"` becomes a plain `#place(top + left, dx: _pos.x cm, dy: _pos.y cm, [body])` — no inline measure. Every other anchor becomes a `#context { let __b = [body]; let __s = measure(__b); place(top + left, dx: _pos.x cm - h_mul * __s.width, dy: _pos.y cm - v_mul * __s.height, __b) }` block, where `(h_mul, v_mul) = anchor_offsets(_anchor)`. Typst evaluates `measure(...)` at compile time, so Python never measures to render. Other emitted forms: `#text(font:, size:, fill:)[...]`, `#hide[...]`, `#pagebreak()`.

**`TypstMeasurer`** — writes an auxiliary `.typ` (at `.cache/measure.typ`) and runs `typst query` to obtain bboxes. Constructed with a list of root elements (any subtree, attached to a slide or not) and writes results into `el._bbox` for every reachable node. The aux document opens with `#set page(margin: 0cm)` — page width/height are intentionally left at Typst's default (measurement is page-size agnostic) but the margin must be zero so that `#place(top + left, dx, dy)` (body-relative) and `here().position()` (page-absolute) share the same coordinate system.

Module-level helpers (shared by both classes):
- `_collect_fixed(el)` — recursively gathers descendants with `placement == "fixed"`.
- `_render_placed(el, render_node)` — emits the `#place` and recurses. The body-render function is passed as a callable; it is the only thing that differs between renderer and measurer.
- `_escape`, `_bare`, `_write` — utilities.

#### Measurement logic (the subtle part)

For each `Element` (other than `"omitted"`, which is pruned everywhere) we need:

- **(w, h)**: the *isolated* size of the element. Obtained by writing a `#context [ ... ]` block with one `#metadata((id, w: measure(...).width/1cm, h: ...))<bbox>` per element.
- **x**: the *actual* horizontal position after parent flow, only for inline elements. Obtained by injecting `#context { let p = here().position(); [#metadata((id, x: p.x/1cm))<bbox>] }` right before the inline child, inside the page-rendered tree.
- **y**: by convention, `bbox.y` of an inline element equals the top-left `y` of the nearest fixed ancestor's rendered body (= the line top under top-aligned placement). Equivalently, for a fixed ancestor with `_pos.y`, anchor multiplier `v_mul`, and measured height `h`, the line top is `_pos.y - v_mul * h`. This is what makes `shift((0, 0))` on an inline element a true visual no-op: freezing `_pos` to the measured anchor point and re-emitting overlaps the inline rendering. Typst's `here().position().y` returns the cursor baseline, not the line top, so it cannot be used directly.

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
