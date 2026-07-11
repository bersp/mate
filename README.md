# mate

`mate` is a Python application for creating presentations by writing Markdown files. The goal is to build aesthetically pleasing presentations in a short amount of time while staying highly customizable and versatile: the content is plain Markdown, and the details can be tweaked with a short, clean syntax (or at least that's the intention).

The idea behind `mate` is to create slides fast, in a declarative and programmatic way, and let the template take care of arranging things and giving them their look. Since the content knows nothing about the aesthetics, restyling a whole presentation amounts to switching its template.

Templates get a lot of freedom and tools, and they are constructive: a template can be as small as a background change or as ambitious as a full visual identity, with its own functions and slide designs, and a deck can combine several of them.

## Features

- Slides are written in plain Markdown: `#` opens a slide, and bold, italics, code and math work as usual.
- Whatever Markdown cannot express, the extended syntax can: any element of a slide can be created, styled, positioned and aligned.
- Templates control fonts, colors, backgrounds and slide logic. Use a built-in one, or write your own as a small Python file next to your deck.
- Slides reveal their content in stages, with a versatile system of pauses, in-place reveals and overwrites.
- There is a drawing API as well: shapes, Bézier curves, images and gradients can go on a slide alongside the text.
- `mate` is fast: everything is heavily cached, so builds stay quick even for large decks.
- There is nothing else to install: no LaTeX, no external tools. The rendering backend ships inside the package.

## Getting started

_To get_ `mate`, _all you need is_ `yerba`:

```bash
pip install yerba
```

Write a deck:

```markdown
# A slide title

Some content with **bold**, _italic_ and inline $x^2$ math.

Words can be styled in place: [this is red][color="red"], and
[this is translucent and smaller][opacity=0.4, fontsize=7].

> pause

- Bullet points work as usual
- and this list appears after the pause.

# Another slide
## With a subtitle

More content.
```

and build it:

```bash
mate slides.md
```

The PDF lands next to the source, as `slides.pdf`.

See the [docs](https://github.com/bersp/mate/blob/master/docs/README.md) for the full Markdown syntax, front matter, templates, and the Python API.

## Backends

The code is built to support different backends. Typst is the only one supported today; new backends will follow once the current one is fully functional and free of known bugs.

## License

MIT. The bundled fonts keep their own licenses (SIL OFL 1.1, under `fonts/`).
