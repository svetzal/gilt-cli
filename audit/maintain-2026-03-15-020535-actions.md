All dependencies are up to date! Here's the summary:

## Dependency Update Results

**What changed:** The lockfile was refreshed via `uv lock --upgrade`, but all direct dependencies were already at their latest compatible versions — no version bumps were needed.

**One note on `pydantic-core`:** Version 2.42.0 is available but remains at 2.41.5 — this is expected behaviour since `pydantic-core` is a transitive dependency whose version is controlled by `pydantic` itself. It will update automatically when `pydantic` releases a version that depends on the newer core.

## Quality Gates — All Green ✅

| Gate | Result |
|---|---|
| `uv run pytest` | **572 passed, 21 skipped** |
| `uv run ruff check .` | **All checks passed** |
| `uv build` | **sdist + wheel built successfully** |

The project is in excellent shape — dependencies are current and all quality gates are clean.