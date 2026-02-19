`hone maintain` completed successfully. Here's what was updated:

| Package | Old Version | New Version | Type |
|---|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 | transitive (via `mojentic`) |
| `filelock` | 3.24.2 | 3.24.3 | transitive |
| `mkdocs-material` | 9.7.1 | 9.7.2 | dev dep |
| `rich` | 13.9.4 | **14.3.2** | direct dep |

The `rich` upgrade is the most notable — it moved from 13.x to 14.x. This was valid because `pyproject.toml` already allowed `>=13,<15`; the lock file had previously pinned it below 14.x despite the looser constraint. `uv lock --upgrade` corrected that drift.

All quality gates passed cleanly:
- ✅ **489 tests passed, 6 skipped**
- ✅ **Lint clean** (`ruff check .`)
- ✅ **Build successful** (`uv build`)