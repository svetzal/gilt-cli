All done. Here's a summary of what was done:

**One update available: `rich` 13.9.4 → 14.3.2**

- Checked the rich 14.x changelog for breaking changes — the only impactful ones are empty `NO_COLOR`/`FORCE_COLOR` env vars now being treated as disabled (gilt doesn't set these), and `typing_extensions` being dropped as a runtime dep (not relied on transitively by gilt)
- All of gilt's rich usage (`Table`, `Console`, `Progress`, `Prompt`, `Panel`, `Text`) uses stable APIs untouched by the 14.x release
- Updated the constraint in `pyproject.toml` from `>=13,<14` to `>=13,<15` to allow the 14.x series
- Updated `uv.lock` via `uv lock --upgrade-package rich`

**All quality gates passed after the update:**
- ✅ test — 489 passed, 6 skipped
- ✅ lint — zero warnings
- ✅ build — sdist + wheel built successfully

All other runtime dependencies (`pandas`, `pyyaml`, `pydantic`, `mojentic`, `typer`, `scikit-learn`, `numpy`) were already at their latest compatible versions within their current constraints.