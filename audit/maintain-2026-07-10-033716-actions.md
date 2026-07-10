Dependency update complete and pushed to `main`.

**Summary:**
- Ran `uv lock --upgrade --dry-run` — only 3 packages had newer compatible versions available, all patch/minor bumps within existing `pyproject.toml` constraints:
  - `openai` 2.44.0 → 2.45.0 (transitive, via `mojentic`)
  - `ruff` 0.15.20 → 0.15.21 (dev dependency)
  - `websockets` 16.0 → 16.1 (transitive)
- No major-version updates were available for any dependency, so there was nothing requiring a changelog/breaking-change review.
- `pyproject.toml` needed no edits — the version ranges already permitted these bumps.
- Quality gates, all green:
  - `uv run pytest` → 2302 passed
  - `uv run ruff check .` → all checks passed
  - `uv build` → sdist + wheel built cleanly
  - `uvx pip-audit` → no known vulnerabilities
- Committed `uv.lock` only (`chore(deps): bump openai..., ruff..., websockets... via uv lock --upgrade`, matching the repo's existing commit style) and pushed directly to `main` per trunk-based workflow. Left the unrelated stray `.claude/worktrees/agent-aa2bf90d89c261498` modification untouched since it's from another session, not part of this change.

This is a Python-only project managed by uv — there's no separate npm/other ecosystem to update.