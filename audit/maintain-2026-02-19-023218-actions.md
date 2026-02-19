The dependency update completed successfully. Here's what hone updated:

| Package | Old Version | New Version | Type |
|---|---|---|---|
| `rich` | 13.x | **14.3.2** | direct dependency |
| `anthropic` | 0.81.0 | **0.82.0** | transitive (via `mojentic`) |
| `mkdocs-material` | 9.7.1 | **9.7.2** | dev dependency |
| `filelock` | 3.24.2 | **3.24.3** | transitive |

**Notable detail:** The `rich` bump from 13.x → 14.x was possible because `pyproject.toml` already declared `>=13,<15` as the constraint — `uv lock --upgrade` simply corrected drift in the lock file that had been holding it at 13.x unnecessarily.

All quality gates passed after the update:
- ✅ **489 tests passed, 6 skipped**
- ✅ **Lint clean**
- ✅ **Build successful**