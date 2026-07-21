Dependency update complete and pushed to `main`.

**Summary:**
- Surveyed the dependency tree with `uv tree --outdated` — only one package had a newer compatible version available: `filelock` (transitive dev dependency via `pip-audit`), 3.31.0 → 3.31.2, a patch bump.
- `pydantic-core` shows `2.47.0` as latest but stays pinned at `2.46.4` since that's the exact build required by `pydantic` 2.13.4 (itself already latest) — not something to force independently.
- No major version bumps were available/needed, so there was nothing requiring a changelog review for breaking changes.
- Ran `uv lock --upgrade-package filelock`, re-synced the environment (including `gui`/`ml` extras, which a plain `uv sync` would otherwise drop), then verified all three quality gates:
  - `uv run pytest` — all tests pass
  - `uv run ruff check .` — all checks passed
  - `uv build` — sdist + wheel built successfully
- Committed only `uv.lock` (matching this repo's established `chore(deps): update uv.lock to latest compatible dependency versions` convention) and pushed directly to `main` per trunk-based workflow.

Note: your working tree still has pre-existing uncommitted changes unrelated to this task (`.claude/worktrees/agent-aa2bf90d89c261498`, `src/gilt/gui/main_window_spec.py`, `src/gilt/gui/views/transactions_view_spec.py`) — I left those untouched since they weren't part of this dependency-update scope.