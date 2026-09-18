# Contributing

## Workflow

All work happens on issue branches and lands on `main` via squash-merged PRs. Every change should trace back to a GitHub issue.

### 1. Create the branch from the issue

```bash
gh issue develop <number> --checkout
```

This creates a branch named `<number>-<slugified-issue-title>` (e.g. `3-add-github-actions-ci-lint-test-smoke-build`), links it to the issue on GitHub, and checks it out locally.

### 2. Commit freely while working

Intermediate commits are squashed away on merge, so they don't need to follow any convention. Use whatever helps you work (`wip`, `fix typo`, `add fixture`).

### 3. Rebase before opening (or if main moved ahead)

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

This keeps history linear — no merge commits. GitHub will also block the merge button if your branch is behind `main`, so you'll need to do this before merging even if you skipped it at PR creation time.

### 4. Open the PR

```bash
gh pr create --title "<human-readable sentence>" --body "Closes #<number>"
```

- **Title** is a real sentence — usually identical to the issue title. It becomes the squash commit message on `main`.
- **Body** must include `Closes #<number>` so the issue auto-closes when the PR merges.

### 5. Squash merge

Use **Squash and merge** in the GitHub UI. The result on `main` looks like:

```
Add GitHub Actions CI: lint, test, smoke build (#7)
```

The `(#7)` is added automatically by GitHub.

## Repo settings (one-time)

Under Settings → General → Pull Requests:

- Allow **squash merging** only (disable merge commits and rebase merging)
- Enable **"Default to PR title for squash merge commits"**
- Enable **"Automatically delete head branches"**

Under Settings → Branches → Add protection rule for `main`:

- Enable **"Require linear history"** — blocks merge commits at the GitHub level
- Enable **"Require branches to be up to date before merging"** — PR must be rebased on current `main` before the merge button activates

These make the workflow above just work without manual fiddling.

## Local checks before opening a PR

```bash
ruff check src/ tests/
isort --check src/ tests/
pytest
```

CI runs the same checks — running them locally first saves a round-trip.
