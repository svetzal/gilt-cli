Dependency update complete — all quality gates passed cleanly on the first attempt. Here's a summary of what happened:

## Update Summary

| Package | Before | After | Type |
|---|---|---|---|
| `ruff` | 0.15.7 | **0.15.8** | patch (dev dep) |

All other dependencies were already at their latest compatible versions. (`pydantic-core` appeared flagged by `pip list --outdated` but the uv resolver confirmed 2.41.5 is already the latest version satisfying the lockfile constraints.)

## Quality Gates — All Green ✅

| Gate | Result |
|---|---|
| `uv run pytest` | 844 passed, 21 skipped, 0 failures |
| `uv run ruff check .` | Zero warnings |
| `uv build` | `gilt_cli-0.5.0.tar.gz` + wheel built successfully |

The `uv.lock` has been updated in place. Ready to commit whenever you'd like.