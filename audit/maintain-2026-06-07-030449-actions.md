All done. Here's a summary of what happened:

**Changes made:**
- `anthropic` bumped **0.106.0 → 0.107.0** (patch update — only change in the lockfile; this is a transitive dependency via `mojentic`)
- `pydantic-core` was listed as outdated (2.46.4 → 2.47.0) but `uv lock --upgrade` didn't update it, likely due to a compatible version constraint from another dep

**Quality gates:** All passed — 1771 tests pass, ruff reports zero issues, build succeeded.

**Note:** Running bare `uv sync` during the process temporarily dropped PySide6 (the gui extra isn't included by default). Restored with `uv sync --extra gui` before running the test suite.