All done! Here's what hone updated in the gilt-cli project:

| Package | Old → New | Type | Notes |
|---|---|---|---|
| `anthropic` | 0.81.0 → 0.82.0 | Minor | Transitive via `mojentic` |
| `filelock` | 3.24.2 → 3.24.3 | Patch | Transitive via `mojentic` |
| `mkdocs-material` | 9.7.1 → 9.7.2 | Patch | Dev dependency |
| `rich` | 13.9.4 → 14.3.2 | Major* | Within declared `>=13,<15` constraint |

The `rich` jump from 13→14 looks like a major bump, but `pyproject.toml` already declared `rich>=13,<15`, so this was an explicitly permitted upgrade path.

**All quality gates passed cleanly:**
- ✅ **Test** — 489 passed, 6 skipped
- ✅ **Lint** — Zero warnings
- ✅ **Build** — sdist + wheel produced successfully