Hone ran two maintain passes and all quality gates are green. Here's what was updated:

---

## Dependency Updates — Summary

### First pass (runtime constraints)
| Package | Old | New |
|---|---|---|
| `rich` | `13.9.4` | `14.3.2` |

The version constraint in `pyproject.toml` was widened from `>=13,<14` to `>=13,<15` to allow the 14.x series. The changelog was reviewed — the only behavioural changes (`NO_COLOR`/`FORCE_COLOR` empty-string handling, `typing_extensions` dropped as a runtime dep) don't affect gilt at all.

### Second pass (lock-file upgrades)
| Package | Old | New |
|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 |
| `filelock` | 3.24.2 | 3.24.3 |
| `mkdocs-material` | 9.7.1 | 9.7.2 |

All other runtime dependencies (`pandas`, `pyyaml`, `pydantic`, `mojentic`, `typer`, `scikit-learn`, `numpy`) were already at their latest compatible versions.

### Quality gates — all green ✅
- **test** — 489 passed, 6 skipped
- **lint** — zero warnings
- **build** — sdist + wheel built successfully

The `uv.lock` file has been updated — you can commit it to lock in these versions.