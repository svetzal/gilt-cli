Dependencies are up to date and pushed to `main`. Summary:

## What was updated
Single ecosystem (Python/uv) — only two packages had newer compatible versions within the existing `pyproject.toml` constraints:
- `lightgbm` 4.6.0 → 4.7.0
- `regex` 2026.7.10 → 2026.7.19 (transitive, via `mojentic`/tooling)

No major-version bumps were available or needed — everything else was already at the latest version permitted by its constraint (e.g. `pydantic-core` 2.47.0 exists upstream but `pydantic` 2.13.4, already latest, pins it to 2.46.4 exactly, so it wasn't touched).

## Quality gates — all green
- `uv run pytest` — 2352 passed
- `uv run ruff check .` — all checks passed
- `uv build` — sdist + wheel built cleanly
- `uv run pip-audit` — no known vulnerabilities

## Note (not fixed, out of scope for this change)
`lightgbm` 4.7.0 emits a new `LGBMDeprecationWarning` for the `eval_set` kwarg used in `src/gilt/ml/duplicate_classifier.py:107`, recommending `eval_X`/`eval_y` instead. It's a warning, not a failure, and fixing it is unrelated to a dependency-version bump, so I left it as a follow-up rather than bundling it into this commit.

## Commit
Committed only `uv.lock` (`da24e81`) and pushed to `origin/main` per trunk-based workflow. I left the pre-existing unstaged changes to `categorize.py`, `recategorize.py`, `filtering.py`, `filtering_spec.py`, and the `.claude/worktrees/...` submodule untouched — those are unrelated dirty state from another session, not part of this dependency update.