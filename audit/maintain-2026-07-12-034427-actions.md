## Summary

**Python dependencies (uv ecosystem):** Already fully current. `uv lock --upgrade` produced no changes — `uv.lock` was already pinned to the latest versions resolvable under the existing `pyproject.toml` constraints. The one nominally "outdated" package, `pydantic-core` (2.46.4 → 2.47.0), can't be bumped independently: it's pinned by `pydantic` itself, and `pydantic` 2.13.4 (already installed, and the latest release) hasn't updated its pin yet. Nothing actionable there.

**CI tooling (GitHub Actions):** Found three actions pinned to stale major versions and bumped them after checking each changelog for breaking changes relevant to this repo's usage:
- `actions/checkout` v4 → v7 — no relevant breaking changes (Node 24 runtime bump only)
- `astral-sh/setup-uv` v7 → v8.3.2 — v8 stopped publishing floating major/minor tags for supply-chain security, so it's now pinned to the exact immutable release `v8.3.2` instead of `@v8`; the only breaking change (manifest-file format) doesn't apply here
- `softprops/action-gh-release` v2 → v3 — Node 24 runtime bump only, `@v3` remains a floating major tag

Applied to both `.github/workflows/ci.yml` and `.github/workflows/release.yml`.

**Quality gates — all green:**
- `uv run pytest` — all tests pass
- `uv run ruff check .` — zero warnings
- `uv build` — sdist + wheel built successfully

Committed as `a367534` and pushed to `origin/main` (trunk-based, per your global instructions). One unrelated pre-existing dirty submodule (`.claude/worktrees/agent-aa2bf90d89c261498`) was left untouched since it's out of scope for this change.