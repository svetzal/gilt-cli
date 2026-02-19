The dependency maintenance run completed successfully. Here's a summary of what was updated in `uv.lock`:

| Package | Before | After | Type | Notes |
|---|---|---|---|---|
| `rich` | 13.9.4 | **14.3.2** | Direct dep | Major-looking bump, but already within the `>=13,<15` constraint in `pyproject.toml` — the lockfile was just stale |
| `anthropic` | 0.81.0 | 0.82.0 | Transitive (via `mojentic`) | Patch |
| `filelock` | 3.24.2 | 3.24.3 | Transitive (via `mojentic`) | Patch |
| `mkdocs-material` | 9.7.1 | 9.7.2 | Dev dep | Patch |

**All 3 quality gates stayed green throughout** (`uv run pytest` → 489 tests passing, `uv run ruff check .`, `uv build`).

**Note on `rich` 13 → 14:** While this appears to be a major bump, it was already pre-approved by the `>=13,<15` bound in `pyproject.toml` — the lockfile had simply been resolved against an older pre-14 release at some point. No breaking changes were introduced for this project.

Only `uv.lock` was modified; `pyproject.toml` required no constraint changes.