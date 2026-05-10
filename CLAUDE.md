# CLAUDE.md

## Commands

```bash
uv pip install -e .        # install in editable mode
weavly build               # compile all src/ files to build/*.json
weavly build --pretty      # human-readable JSON output
weavly watch               # watch src/ and rebuild on save
weavly init [my-project]   # create a new project
ruff check src/            # lint
isort --check src/         # import order check
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

## Workflow

Issue-driven, squash-merged PRs. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full version. When asked to work on issue N:

1. `gh issue develop N --checkout` — creates and checks out `N-<slug>` branch, links it to the issue
2. Commit freely — intermediate commits get squashed on merge
3. PR title = human sentence (usually the issue title); body must include `Closes #N`
4. Squash merge produces one clean commit on `main`: `<title> (#<pr-number>)`

Never commit directly to `main`. Never use the branch slug as a commit message.
