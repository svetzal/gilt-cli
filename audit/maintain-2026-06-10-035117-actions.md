Dependencies updated, all gates green, pushed to `main`.

**Summary of changes:**

| Package | Old | New | Notes |
|---|---|---|---|
| `anthropic` | 0.107.1 | 0.109.1 | Minor — transitive dep via `mojentic` |
| `tqdm` | 4.68.1 | 4.68.2 | Patch — transitive dep |

**Not updated** (at latest compatible version):
- `pydantic-core` 2.46.4 — `uv lock --upgrade` resolved this correctly; 2.47.0 is paired with a newer pydantic that isn't yet released, so 2.46.4 is the right version for pydantic 2.13.4 (the current latest).

All runtime and dev dependencies are at their latest versions within the declared constraints. 1812 tests pass, lint is clean, build produces valid wheel and sdist.