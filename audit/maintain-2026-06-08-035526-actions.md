Dependency update complete. Here's a summary of what happened:

- **Updated**: `anthropic` 0.107.0 → 0.107.1 (patch update)
- **All other dependencies** were already at their latest compatible versions within the pyproject.toml constraints
- **Quality gates**: All passed — 1809 tests pass, lint clean, build succeeds
- **Committed & pushed** the lockfile update to `origin/main`

One note: `uv sync` without `--extra gui` strips PySide6 from the environment (it's an optional extra). I restored it with `uv sync --extra gui` — the dev environment is back to the full state with GUI support.