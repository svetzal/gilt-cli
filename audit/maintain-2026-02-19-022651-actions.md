All three quality gates are green. Here's the summary of what was updated:

---

## Dependency Updates — gilt-cli

**4 packages updated** (all within existing `pyproject.toml` constraints, no changes to `pyproject.toml` itself):

| Package | Old | New | Type | Notes |
|---|---|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 | Minor | Transitive via `mojentic` |
| `filelock` | 3.24.2 | 3.24.3 | Patch | Transitive via `mojentic` |
| `mkdocs-material` | 9.7.1 | 9.7.2 | Patch | Dev dependency |
| `rich` | 13.9.4 | 14.3.2 | Major* | *Within the declared `>=13,<15` constraint |

The `rich` 13→14 jump is a major version, but `pyproject.toml` already explicitly allows it (`rich>=13,<15`), so this was an intended upgrade path.

**Quality gates:** ✅ 489 passed, 6 skipped · ✅ Lint clean · ✅ Build succeeded