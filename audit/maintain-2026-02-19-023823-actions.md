`hone maintain` completed successfully. Here's a summary of what was updated:

| Package | Old Version | New Version | Type |
|---|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 | minor |
| `filelock` | 3.24.2 | 3.24.3 | patch |
| `mkdocs-material` | 9.7.1 | 9.7.2 | patch |
| `rich` | 13.9.4 | 14.3.2 | major (within allowed range) |

**Key notes:**
- The `rich` 13→14 bump is semantically a major version, but it's explicitly within the declared `>=13,<15` constraint in `pyproject.toml` — no manual intervention needed.
- The `anthropic` update came in as a transitive dependency via `mojentic`, which itself loosened its `rich` cap from `<14` to `<15`, enabling the `rich` upgrade.
- All **489 tests pass** (6 skipped), linting is clean, and the build succeeds.