# CLAUDE.md

## Commands

```bash
uv pip install -e .        # install in editable mode
weavly build               # compile src/*.wvl → per-file build/*.wvl.json (nodes) + merged build/env.json (declarations)
weavly build --pretty      # human-readable JSON output
weavly init [my-project]   # create a new project
ruff check src/ tests/     # lint
isort --check src/ tests/  # import order check
pytest                     # run tests
```

## Tests

Fixture-based snapshots in `tests/fixtures/<feature>/<case>.wvl` + sibling `<case>.json`. `test_wvl.py` auto-discovers all `.wvl` files — no changes needed to add a test.

### Adding a test

1. Create `tests/fixtures/<feature>/` with a `.wvl` file (minimal source for the feature)
2. Add a sibling `.json` with the exact expected output

## Adding a new statement type

1. Add the rule to [wvl-grammar.lark](src/weavly/resources/wvl-grammar.lark), wire into `?line_statement` or `?block_statement`
2. Add the transformer method to `WvlTransformer` — `__default__` raises immediately if you miss one
3. The returned dict is the JSON output shape; the GDScript runtime is the consumer
4. Decorate it with `@located` and include `"line": meta.line`. Every node, statement, case and option item carries its source line; the build adds `"source"` (path relative to `src/`, POSIX separators) to each `*.wvl.json`

## Variable declarations (`@env`)

Variables are declared in `@env ... @endenv` blocks inside `.wvl` files (sibling of `@node`). Multiple blocks are allowed per file and across the project. The build **merges every declaration project-wide into a single `build/env.json`** (`{"declarations": [...]}`); per-file `build/*.wvl.json` keeps only `{"source": "...", "nodes": [...]}`. Duplicate declaration names anywhere in the project are a compile error naming both source locations.

Note: the `tests/fixtures/env/` snapshots capture the raw transformer output, which *includes* a `declarations` key — that key is split out into `env.json` (and stripped from per-file output) by the build pipeline. The cross-file merge and duplicate detection are covered by `tests/test_env_merge.py`, not the single-file fixture harness.

## Workflow

Issue-driven, squash-merged PRs. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full version. When asked to work on issue N:

1. `gh issue develop N --checkout` — creates and checks out `N-<slug>` branch, links it to the issue
2. Commit freely — intermediate commits get squashed on merge
3. PR title = human sentence (usually the issue title); body must include `Closes #N`
4. Squash merge produces one clean commit on `main`: `<title> (#<pr-number>)`

Never commit directly to `main`. Never use the branch slug as a commit message.
