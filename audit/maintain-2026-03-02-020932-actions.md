Here's the update report for **gilt-cli**:

---

### Dependency Update Results

**Good news** — all direct dependencies were already at their latest compatible versions. One transitive dependency picked up a patch bump:

| Package | Old | New | Type |
|---|---|---|---|
| `filelock` | 3.24.3 | 3.25.0 | transitive (via `mojentic`) |

### Direct dependencies — all current

| Package | Version | Constraint |
|---|---|---|
| `pydantic` | 2.12.5 | `>=2,<3` |
| `pandas` | 3.0.1 | unconstrained |
| `typer` | 0.24.1 | `>=0.12,<1` |
| `rich` | 14.3.3 | `>=13,<15` |
| `scikit-learn` | 1.8.0 | `>=1.3,<2` |
| `numpy` | 2.4.2 | `>=1.24,<3` |
| `mojentic` | 1.2.1 | unconstrained |
| `ruff` | 0.15.4 | unconstrained |
| `pytest` | 9.0.2 | unconstrained |
| `mkdocs` | 1.6.1 | unconstrained |

### Version constraints — no changes needed

All upper-bound constraints were reviewed and remain appropriate (`pydantic<3`, `typer<1`, `rich<15`, `scikit-learn<2`, `numpy<3` — none of these next major versions have shipped yet).

### Quality gates ✅

| Gate | Result |
|---|---|
| `uv run pytest` | **512 passed**, 15 skipped |
| `uv run ruff check .` | **Clean** — zero warnings |
| `uv build` | **Success** — sdist + wheel produced |

The `uv.lock` has been updated and the project is in excellent shape.