The dependency maintenance run completed successfully. Here's what was updated in `uv.lock` — all three quality gates (test, lint, build) stayed green throughout:

| Package | Before | After | Type | Notes |
|---|---|---|---|---|
| `rich` | 13.9.4 | **14.3.2** | Direct dep | Major version, but within the `>=13,<15` constraint already in `pyproject.toml` — the lock was just stale |
| `anthropic` | 0.81.0 | 0.82.0 | Transitive | Patch bump via `mojentic` |
| `filelock` | 3.24.2 | 3.24.3 | Transitive | Patch bump via `mojentic` |
| `mkdocs-material` | 9.7.1 | 9.7.2 | Dev dep | Patch bump |

**Key point on `rich` 13 → 14:** this looks like a major bump but it was already pre-approved by the `>=13,<15` bound in `pyproject.toml` — the lockfile had just been resolved against an older pre-14 release. All 489 tests pass with the new version, confirming no breaking changes for this project. Only `uv.lock` was modified; `pyproject.toml` required no constraint changes.