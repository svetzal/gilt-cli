Here's a summary of what was updated in `uv.lock`:

| Package | Old | New | Type |
|---|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 | transitive (via `mojentic`) |
| `filelock` | 3.24.2 | 3.24.3 | transitive |
| `mkdocs-material` | 9.7.1 | 9.7.2 | dev dep |
| `rich` | 13.9.4 | 14.3.2 | direct dep |

The `rich` update is the most significant — from 13.x to 14.x — and was possible because the lock file had been recording the old `>=13,<14` constraint even though `pyproject.toml` already specified `>=13,<15`. `uv lock --upgrade` corrected this drift and resolved `rich` to its latest 14.x release.

All quality gates passed: **489 tests passed, 6 skipped · lint clean · build successful**.