The dependency update is complete. Here's a summary:

## Update Results

**One package updated:**

| Package | Old Version | New Version | Type |
|---------|-------------|-------------|------|
| `typer` | 0.24.0 | **0.24.1** | Patch |

All other dependencies were already at their latest versions within the constraints defined in `pyproject.toml`.

**Quality gates — all green ✅**
- `uv run pytest` → **512 passed**, 15 skipped
- `uv run ruff check .` → **Zero warnings**
- `uv build` → Built `gilt_cli-0.3.5.tar.gz` + `gilt_cli-0.3.5-py3-none-any.whl`

Only `uv.lock` was modified (as expected — it's the pinned lockfile managed by uv). No changes to `pyproject.toml` were needed since the existing version constraints already permitted the patch update.