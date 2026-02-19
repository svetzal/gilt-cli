The dependency update completed successfully. Here's what `hone maintain` updated in `uv.lock`:

| Package | Old Version | New Version | Type |
|---|---|---|---|
| `rich` | 13.9.4 | **14.3.2** | direct dependency |
| `anthropic` | 0.81.0 | **0.82.0** | transitive (via `mojentic`) |
| `mkdocs-material` | 9.7.1 | **9.7.2** | dev dependency |
| `filelock` | 3.24.2 | **3.24.3** | transitive |

**Notable:** The `rich` jump from 13.x → 14.x was safe because `pyproject.toml` already declared `rich >=13,<15` — the lock file had simply been holding it back at 13.x unnecessarily. `uv lock --upgrade` corrected that drift.

All three quality gates passed after the update:
- ✅ **489 tests passed, 6 skipped**
- ✅ **Lint clean**
- ✅ **Build successful**