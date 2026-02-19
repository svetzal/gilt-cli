All three quality gates pass cleanly. Here's a summary of what was updated:

| Package | Old Version | New Version | Type |
|---|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 | patch |
| `filelock` | 3.24.2 | 3.24.3 | patch |
| `mkdocs-material` | 9.7.1 | 9.7.2 | patch |
| `rich` | 13.9.4 | 14.3.2 | major (within `>=13,<15` constraint) |

**Rich 14.x note**: The `pyproject.toml` already declares `rich>=13,<15`, so this major bump was always in-scope. The Rich 14.x changelog shows no API removals affecting gilt's usage (`Console`, `Table`, `Panel`, `Prompt`, `Progress`, `Text`). The only changes are environmental (empty `NO_COLOR`/`FORCE_COLOR` now treated as disabled) and visual (Markdown heading styles) — neither relevant here.

All 489 tests pass (6 skipped as before), lint is clean, and the build succeeds.