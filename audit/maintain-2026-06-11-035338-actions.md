Done. Two transitive patch updates were available and applied:

| Package | Before | After |
|---|---|---|
| `filelock` | 3.29.1 | 3.29.3 |
| `openai` | 2.41.0 | 2.41.1 |

The third candidate (`pydantic-core` 2.46.4 → 2.47.0) wasn't resolved by `uv lock --upgrade` — likely held back by a version constraint in a direct dependency. All quality gates passed: **1819 tests, lint clean, build succeeded**. Changes committed and pushed to `main`.