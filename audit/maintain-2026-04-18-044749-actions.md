The dependency update is complete. Here's what happened:

## Updates Applied

| Package | From | To | Type |
|---|---|---|---|
| `pydantic` | 2.13.1 | 2.13.2 | patch |
| `pydantic-core` | 2.46.1 | 2.46.2 | patch |

All other packages — including `pandas 3.0.2`, `numpy 2.4.4`, `scikit-learn 1.8.0`, `typer 0.24.1`, `rich 15.0.0`, `PySide6 6.11.0`, `mojentic 1.2.1`, `pytest 9.0.3`, and `ruff 0.15.11` — were already at their latest compatible versions.

## Quality Gates ✅

- **Tests**: 1040 passed, 58 skipped
- **Lint**: clean
- **Build**: `gilt_cli-0.5.2` wheel and sdist produced successfully

The `uv.lock` file has been updated with the new pinned versions.