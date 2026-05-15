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
│   └── text.py
├── backends/          # backend-specific renderers/measurers
│   └── typst.py
└── .cache/            # regenerated artifacts (measurement); safe to delete
```

## Model

### `core/vec.py` — `Vec`

A 2D `np.ndarray` subclass with `.x` and `.y`. Use it whenever something has "two coordinates" (position, size, center). Inherits numpy arithmetic and broadcasting for free.

### `core/element.py` — `Element`

Base class of **everything** that appears on a slide. Attributes:

| Attribute | Meaning |
|---|---|
| `center` | Visual center `Vec` in slide coordinates (cm). Public, read via property: returns the bbox center (measuring for `"inline"` elements, and overridden in `Group` to always return the union-bbox center). Writes go to `_center`. |
| `_center` | Storage backing `center`. Internal hot paths (`_translate`, backend) read/write this directly to avoid measurement. For `"fixed"` Rectangle/Text it equals the visual center by construction; for a freshly built `Group` it is the constructor value `(0, 0)` until the first `move_to`/`shift`. |
| `placement` | `"fixed"` (drawn with body center at `_center`), `"inline"` (flows in parent's content), or `"omitted"` (not rendered, not measured). |
| `parent` | Owning `Element` (set automatically when adopted via `_take_children`); `None` for root elements directly attached to a `Slide`. |
| `hidden` | If `True`, the element takes space but is not drawn. Propagates through ancestors via `get_effective_hidden()` — `hidden=True` on a Group hides the whole subtree at render time. |
| `children` | List of sub-`Element`s. Forms a tree. |
| `_mid` | Globally unique id, used by the backend for metadata. |
| `_bbox` | Cached `(x, y, w, h)` or `None` (not measured). |

Public API: `move_to / shift / get_bbox / get_bbox_center / copy` plus the `center` property. Both movers force `placement = "fixed"` and invalidate the bbox cache of the whole tree.

All `Element` constructor parameters (`center`, `placement`, `id`) are **keyword-only** — subclasses keep their intrinsic positional args (`Rectangle(width, height, ...)`, `Circle(radius, ...)`, `Text(source, ...)`, `Group(children, ...)`) but everything else flows as `**kwargs`. The split is enforced by the `*` in each `__init__`.

- `move_to(p)` — sets `_center = p`. Computes the visual delta against the element's current `center` (measured if it was `"inline"` or a `Group`) and translates every fixed descendant by that delta, so the subtree moves as a unit. `el.move_to(el.center)` is the identity.
- `shift(d)` — adds `d` to `_center` (accumulates over repeated calls). When the element is `"inline"`, freezes `_center` to its measured visual center first, so the increment is taken from the flowed position. Same propagation: every fixed descendant gets `+= d`.
- `get_bbox_center()` — always measures (cache miss → subprocess) and returns the bbox center. Use `center` when the cheaper "anchor or measured" reading is enough.

**Inline → fixed freeze.** Inline elements have no anchor of their own — their visible position only exists after Typst lays them out. The freeze captures the bbox center and stores it in `_center` before applying the increment, which makes `shift((0, 0))` a true visual no-op (the element is re-emitted at exactly the position it was already showing). The cost is one measurement when the bbox cache is cold. `move_to` follows the same pattern but the increment computation is `p - center`, so the propagation delta is the visual delta.

**Movement propagates by default.** Mutating an element's position translates every fixed descendant by the same delta (`_translate` walks the subtree). `"inline"` descendants are not touched (their `_center` is meaningless under flow), but the recursion descends through them so fixed grand-descendants still follow.

**Cache invalidation is geometric only.** `move_to` and `shift` call `_invalidate_tree`, which clears `_bbox` on every node in the tree (a position change can shift the flowed `x` of inline siblings, so the whole tree must be re-measured). Visual-only mutators (color, opacity, stroke, hidden) leave the cache alone, since they do not affect typesetting size.

**Placement semantics.** The renderer skips `"omitted"` elements at every level. `"inline"` only makes sense as a descendant of a fixed element — at the slide root it is treated like `"omitted"` for rendering, since there is no parent flow to participate in. The parser in `Text` produces `"inline"` subs by default; users opt into placement explicitly with `move_to` or `shift`.

**`Group.center` overrides the base property.** A `Group` has no rendered body, so its visual center is the union of children's bboxes — not the stored `_center`. The `center` property is overridden to measure on every read. The stored `_center` only exists so `move_to`/`shift` arithmetic is uniform across subclasses; it is not a meaningful query of "where is the group".

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

Only `fill_color` / `fill_opacity` reach Typst (as `#text(fill: ...)` wraps); `stroke_*` is accepted but currently ignored for text rendering.

**`_copy()`** override re-maps the `subs` list using the shared `mapping` from `Element._copy`, so the cloned subs point at the cloned descendants. Clones inherit structure but are not registered in `id_registry`: the registry indexes user-tagged originals.

### `elements/shapes.py` — `Rectangle`, `Circle`, `Ellipse`

Three filled-shape primitives extending `Drawable` with intrinsic dimensions and no children. With the `Drawable` defaults they render as solid black with no stroke; pass `fill_opacity=0` to make a layout placeholder, and `stroke_width > 0` to draw an outline.

- `Rectangle(width, height, ...)` → `#rect(width: Wcm, height: Hcm, fill: ..., stroke: ...)`. Bbox is `(width, height)`.
- `Circle(radius, ...)` → `#circle(radius: Rcm, fill: ..., stroke: ...)`. Bbox is `(2 radius, 2 radius)`.
- `Ellipse(width, height, ...)` → `#ellipse(width: Wcm, height: Hcm, fill: ..., stroke: ...)`. Bbox is `(width, height)`; semi-axes are `width/2` and `height/2`.

Measurement returns Typst's `measure()` of the emitted body, which matches the intrinsic dimensions for all three. The backend dispatches them through a single `_shape_markup(el)` helper that branches on the concrete type and resolves the four `Drawable` fields via `_typst_fill` / `_typst_stroke`.

### `elements/group.py` — `Group`

`Group` extends `Drawable` with no markup of its own. It is a real tree node (children are reparented on construction) and its bbox is the **union** of children's bboxes (omitted children excluded), so `group.center` (and `group.get_bbox_center()`) returns the visual center of all the contained content.

A Group has no rendered body, so its own `fill_color` / `stroke_color` / `fill_opacity` / `stroke_width` are inert at render time. Their purpose is to serve as the receiver for the `set_*` bulk setters, which walk and rewrite every `Drawable` descendant.

Movement (`move_to`, `shift`) is inherited from `Element`: every fixed descendant follows the group's translation. `Group(children=[...])` adopts the iterable at construction; `group.add(el)` appends later (reparents and invalidates the tree's bbox cache). The backend recognises `Group` in `_render_node` (renders children, with fixed ones as placeholders just like a `Text` composite) and in `_assign` (overrides the metadata-derived size with the union).

### `hidden` propagation

`hidden` lives on `Element` (so it applies to nodes without a body too) and propagates through the parent chain via `Element.get_effective_hidden()`. The renderer applies it at every fixed `#place` block (`_render_placed` wraps the body in `#hide[...]` when an ancestor is hidden), so the flag reaches fixed descendants that have escaped lexical scope.

### Why a uniform tree

A `Text` with subs is internally a tree of `Text`s. When `Square`, `Triangle`, `Line`, etc. are added later they all live in the same tree under an `Element` root. Renderer and measurer walk `children` without knowing the concrete type (except where type-specific dispatch is needed, like Text → glyphs).

## Backend

### `backends/typst.py`

Two classes with separate responsibilities:

**`TypstRenderer`** — writes the final `.typ` the user compiles to PDF. Each fixed element becomes a `#context { let __b = [body]; let __s = measure(__b); place(top + left, dx: _center.x - __s.width/2, dy: _center.y - __s.height/2, __b) }` block, which centers the body's measured size on `_center`. Other emitted forms: `#text(fill:)[...]`, `#hide[...]`, `#pagebreak()`. Measurement runs inside Typst (via `measure(...)`), so the renderer does not need a Python pre-measure pass.

**`TypstMeasurer`** — writes an auxiliary `.typ` (at `.cache/measure.typ`) and runs `typst query` to obtain bboxes. Constructed with a list of root elements (any subtree, attached to a slide or not) and writes results into `el._bbox` for every reachable node. The aux document opens with `#set page(margin: 0cm)` — page width/height are intentionally left at Typst's default (measurement is page-size agnostic) but the margin must be zero so that `#place(top + left, dx, dy)` (body-relative) and `here().position()` (page-absolute) share the same coordinate system.

Module-level helpers (shared by both classes):
- `_collect_fixed(el)` — recursively gathers descendants with `placement == "fixed"`.
- `_render_placed(el, render_node)` — emits the `#place` and recurses. The body-render function is passed as a callable; it is the only thing that differs between renderer and measurer.
- `_escape`, `_bare`, `_write` — utilities.

#### Measurement logic (the subtle part)

For each `Element` (other than `"omitted"`, which is pruned everywhere) we need:

- **(w, h)**: the *isolated* size of the element. Obtained by writing a `#context [ ... ]` block with one `#metadata((id, w: measure(...).width/1cm, h: ...))<bbox>` per element.
- **x**: the *actual* horizontal position after parent flow, only for inline elements. Obtained by injecting `#context { let p = here().position(); [#metadata((id, x: p.x/1cm))<bbox>] }` right before the inline child, inside the page-rendered tree.
- **y**: by convention, `bbox.y` of an inline element equals the top-left `y` of the nearest fixed ancestor's rendered body (= the line top under top-aligned placement). Equivalently, for a fixed ancestor with center `_center.y` and measured height `h`, the line top is `_center.y - h/2`. This is what makes `shift((0, 0))` on an inline element a true visual no-op: freezing `_center` to the bbox center and re-emitting overlaps the inline rendering. Typst's `here().position().y` returns the cursor baseline, not the line top, so it cannot be used directly.

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
