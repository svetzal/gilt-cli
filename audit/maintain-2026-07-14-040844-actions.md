Done. Summary:

**Dependency update result**: the `uv.lock` was already nearly fully current. The one actionable update was a transitive dependency — **narwhals 2.23.0 → 2.24.0** (patch bump, pulled in via `scikit-learn`). Everything else (direct deps, dev/lint/docs groups, `PySide6`, `lightgbm`) was already at latest compatible version within the existing `pyproject.toml` constraints, so no manifest edits were needed. `pydantic-core` shows a newer release available, but it's not independently movable — `pydantic` 2.13.4 (itself latest) hard-pins its exact `pydantic-core` build.

**Quality gates**: all green after the update
- `uv run pytest` — all tests pass
- `uv run ruff check .` — zero warnings
- `uv build` — sdist + wheel built cleanly
- (bonus) `uv run pip-audit` — no known vulnerabilities

**Committed and pushed** to `main` (trunk-based, per your global instructions): `74f5b7b chore(deps): upgrade narwhals to 2.24.0`.

Note: I left `.claude/worktrees/agent-aa2bf90d89c261498` untouched — it's a pre-existing dirty submodule-pointer artifact unrelated to this task, so it wasn't staged or committed.