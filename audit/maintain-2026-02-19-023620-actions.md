All three gates green. ✅ Here's the summary of what changed:

| Package | Before | After | Type |
|---|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 | patch |
| `filelock` | 3.24.2 | 3.24.3 | patch |
| `mkdocs-material` | 9.7.1 | 9.7.2 | patch |
| `rich` | 13.9.4 | 14.3.2 | **major** (within `<15` bound) |

The `rich` bump is the notable one — 13 → 14 is a major version, but your `pyproject.toml` already declared `>=13,<15`, so it's within the approved range. All 489 tests pass, lint is clean, and the build succeeds, so there are no breaking changes affecting this project. The `uv.lock` is now updated and ready to commit.