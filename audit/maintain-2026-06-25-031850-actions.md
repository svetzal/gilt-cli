Dependencies updated and pushed. Here's a summary of what changed:

**Updated (transitive dependencies only — no direct dep version ranges needed changing):**
- `anthropic` 0.111.0 → 0.112.0
- `anyio` 4.14.0 → 4.14.1
- `click` 8.4.1 → 8.4.2
- `openai` 2.43.0 → 2.44.0

**Not updated:** `pydantic-core` showed as outdated in `pip list --outdated` but the resolver didn't pick up a newer version — likely constrained by the `pydantic>=2,<3` pin and current solver resolution.

All quality gates pass: **1684 tests, lint clean, build clean**.