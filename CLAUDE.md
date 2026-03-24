# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode (required for development)
uv pip install -e .

# Build all source files to JSON
weavly build
weavly build --pretty   # human-readable JSON output

# Watch src/ for changes and rebuild on save
weavly watch

# Create a new project
weavly init
weavly init my-project  # in a named subdirectory

# Lint
ruff check src/
isort --check src/
```

There are no automated tests. Manual testing is done by running `weavly build` against files in `examples/`.

## Architecture

This is a **compiler** for the Weavly dialog scripting DSL. It parses `.wvl` and `.wenvl` source files and outputs JSON consumed by a separate GDScript runtime in Godot.

### Pipeline

```
src/*.wvl   → Lark (LALR) → WvlTransformer   → build/*.wvl.json
src/*.wenvl → Lark (LALR) → WenvlTransformer → build/*.wenvl.json
```

`build_all_files()` in [parsing/parser.py](src/weavly/parsing/parser.py) orchestrates this: it wipes `build/`, then iterates source files for each extension, running parse → transform → JSON write.

### Two file types

- **`.wvl`** — dialog script nodes. Grammar: [wvl-grammar.lark](src/weavly/resources/wvl-grammar.lark). Transformer: [wvl_transformer.py](src/weavly/parsing/wvl_transformer.py).
- **`.wenvl`** — typed variable declarations (number/string/flag). Grammar: [wenvl-grammar.lark](src/weavly/resources/wenvl-grammar.lark). Transformer: [wenvl_transformer.py](src/weavly/parsing/wenvl_transformer.py).

### JSON output shape

`WvlTransformer` produces:
```json
{
  "nodes": [
    { "id": "node_id", "body": [ ...statements ] }
  ]
}
```

Statement types in body: `narration`, `character`, `set`, `goto`, `finish`, `command`, `if`, `option`, `random`.

Expressions are serialized as nested dicts: `{"op": "+", "left": ..., "right": ...}` or `{"variable": "id"}` or a literal value.

### Grammar conventions

- All keywords are `@`-prefixed (`@node`, `@if`, `@options`, etc.)
- Variables are `$`-prefixed
- `->` is inline goto shorthand
- `>` prefix marks a named character line (name is a literal string, not a variable)
- `@command` catches any unknown `@keyword` not reserved by the grammar

### Adding a new statement type

1. Add the rule to [wvl-grammar.lark](src/weavly/resources/wvl-grammar.lark) and wire it into `?line_statement` or `?block_statement`
2. Add the corresponding transformer method to `WvlTransformer` — the `__default__` override will raise immediately if you miss one
3. The output JSON shape is whatever dict the transformer method returns; the GDScript runtime is the consumer

### CLI

[cli.py](src/weavly/cli.py) uses Typer. Commands: `build`, `init`, `watch`. The `weavly` entry point is registered in `pyproject.toml`.
