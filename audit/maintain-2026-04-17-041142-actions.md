All dependencies have been updated successfully. Here's what changed:

## Dependency Updates — gilt-cli

All updates were minor/patch bumps — no breaking changes.

| Package | Before | After |
|---|---|---|
| `anthropic` | 0.95.0 | **0.96.0** |
| `openai` | 2.31.0 | **2.32.0** |
| `pydantic` | 2.13.0 | **2.13.1** |
| `pydantic-core` | 2.46.0 | **2.46.1** |
| `ruff` | 0.15.10 | **0.15.11** |

## Quality Gate Results

| Gate | Result |
|---|---|
| `uv run pytest` | ✅ 1,034 passed, 58 skipped (pre-existing) |
| `uv run ruff check .` | ✅ Zero warnings |
| `uv build` | ✅ sdist + wheel built cleanly |

**Note:** PySide6 was already at its latest version (6.11.0) — no update needed there. The `uv.lock` is updated with the pinned versions; commit it to keep builds reproducible.