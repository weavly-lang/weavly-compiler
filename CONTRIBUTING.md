# Contributing

## Workflow

Every change starts from a GitHub issue and lands on `main` as one squashed commit.

1. `gh issue develop <number> --checkout` creates and links the `<number>-<slug>` branch.
2. Commit freely. Commits are squashed on merge.
3. Rebase on `main` before merging (`git rebase origin/main`, `git push --force-with-lease`). Branch protection requires it.
4. `gh pr create --title "<sentence, usually the issue title>" --body "Closes #<number>"`. The title becomes the commit message on `main`.
5. Squash and merge.

## Checks

```bash
ruff check src/ tests/
isort --check src/ tests/
pytest
```

CI also runs `weavly build` in `ci-smoke/` and fails if `ci-smoke/build/` changes. When the output changes, rebuild it and commit the result. When the language changes, extend `ci-smoke/src/` to cover it.

## Tests

- Output snapshots: `tests/fixtures/<feature>/<case>.wvl` with the expected `<case>.json` next to it. `tests/test_wvl.py` finds them automatically.
- Source that must fail to parse: `tests/fixtures/<feature>/invalid/<case>.wvl`, without a `.json`.
- Errors found after parsing (undeclared names, types, references): tests through `build_all_files`, in `tests/test_type_checker.py` or `tests/test_env_merge.py`. Warnings: `tests/test_warnings.py`.

## Changing the language or the output

- While Weavly is at 0.x there's no backward compatibility. Change things cleanly, without fallbacks for the old form, and label the issue `breaking`.
- A new rule needs a `WvlTransformer` method (`__default__` raises for any rule without one). Every node, statement, case and option item carries `"line"`.
- The [Godot addon](https://github.com/weavly-lang/weavly-godot-addon) reads the output, so output changes need a matching addon issue.

## Releasing

1. Bump `version` in `pyproject.toml` in a PR and merge it.
2. Tag the merge commit and push the tag: `git tag v<version>` and `git push origin v<version>`.
3. The [release workflow](.github/workflows/release.yml) checks the tag against `pyproject.toml`, runs lint and tests and builds the package.
4. Approve the `pypi` deployment. It publishes to PyPI and creates a GitHub release.

A version can be uploaded to PyPI only once. Yank a broken release and publish a new patch version.

## Repository settings

- Pull requests: squash merging only, "Default to PR title for squash merge commits" and "Automatically delete head branches".
- `main` protection: "Require linear history" and "Require branches to be up to date before merging".
- Releases: a PyPI trusted publisher (project `weavly`, owner `weavly-lang`, repository `weavly-compiler`, workflow `release.yml`, environment `pypi`), and a `pypi` environment with a required reviewer.
