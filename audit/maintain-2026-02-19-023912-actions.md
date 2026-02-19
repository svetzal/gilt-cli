All three gates pass. Here's a summary of what was updated:

| Package | Old Version | New Version | Type | Notes |
|---|---|---|---|---|
| `anthropic` | 0.81.0 | 0.82.0 | minor | Transitive dep via `mojentic` |
| `filelock` | 3.24.2 | 3.24.3 | patch | Transitive dep |
| `mkdocs-material` | 9.7.1 | 9.7.2 | patch | Dev dep |
| `rich` | 13.9.4 | 14.3.2 | **major** | Within declared `>=13,<15` constraint; `mojentic` loosened its own cap from `<14` → `<15` enabling this |

The `rich` 13→14 bump is the most notable change — it's a major version by semver, but is explicitly within the range your `pyproject.toml` allows (`>=13,<15`). All 489 tests pass with 6 skipped, linting is clean, and the build succeeds cleanly.