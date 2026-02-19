The maintenance run completed successfully. Here's a summary of what was updated:

| Package | Change | Notes |
|---|---|---|
| `rich` | 13.9.4 → **14.3.2** | Major bump, but within your declared `>=13,<15` constraint; `mojentic` loosened its cap from `<14` to `<15` which enabled this |
| `anthropic` | 0.81.0 → 0.82.0 | Minor — transitive via `mojentic` |
| `mkdocs-material` | 9.7.1 → 9.7.2 | Patch — dev/docs tooling |
| `filelock` | 3.24.2 → 3.24.3 | Patch — transitive |

All 3 quality gates passed on the updated lock file:
- ✅ **489 tests pass** (6 skipped)
- ✅ **Lint clean** (`ruff check`)
- ✅ **Build succeeds** (`uv build`)

The most notable change is `rich` 13→14, which is a semver major but was explicitly allowed by your `pyproject.toml` version constraint (`>=13,<15`) and caused no test or lint regressions.