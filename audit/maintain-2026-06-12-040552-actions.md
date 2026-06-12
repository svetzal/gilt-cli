Done. Here's the summary:

**Update applied:** `ruff` 0.15.16 → 0.15.17 (patch bump)

**What was skipped:** `pydantic-core` 2.46.4 → 2.47.0 appeared in `uv pip list --outdated` but the resolver held it back — a transitive constraint from another dependency pins it, so it wasn't touched.

**Side note caught:** `uv sync` without `--extra gui` had silently dropped PySide6 during the sync step. Restored it with `uv sync --extra gui` before running the gates — all 1839 tests pass (5 skipped, all pre-existing), lint clean, build successful. Committed and pushed to `main`.