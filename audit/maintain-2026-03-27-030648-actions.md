The dependency update is complete. Here's what happened:

## Dependency Update Summary

**One update applied:**

| Package | Before | After | Type |
|---|---|---|---|
| `ruff` | 0.15.7 | **0.15.8** | patch (dev dep) |

**Everything else was already current** — `uv pip list --outdated` flagged `pydantic-core`, but the uv resolver confirmed 2.41.5 is already the latest version satisfying all transitive constraints in the lockfile.

## Quality Gates — All Green ✅

| Gate | Result |
|---|---|
| `uv run pytest` | 844 passed, 21 skipped, 0 failures |
| `uv run ruff check .` | Zero warnings |
| `uv build` | `gilt_cli-0.5.0.tar.gz` + `.whl` built successfully |

The `uv.lock` has been updated and is ready to commit.