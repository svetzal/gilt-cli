The dependency update is complete. Here's a summary of what happened:

## Dependency Update Results

**Updated:**
| Package | From | To | Type |
|---|---|---|---|
| `regex` | 2026.2.28 | 2026.3.32 | Transitive (used by tokenizers) |

**Constrained (not updated):**
| Package | Installed | Latest | Reason |
|---|---|---|---|
| `pydantic-core` | 2.41.5 | 2.43.0 | Would require `pydantic >= 2.13`, which doesn't exist as a stable release yet — resolver correctly held this back |

**Quality Gates — All Passed ✅**
- `uv run pytest` — 873 tests pass
- `uv run ruff check .` — lint clean
- `uv build` — produces both sdist and wheel cleanly

The `uv.lock` file has been updated to reflect the `regex` upgrade. Everything is in good shape — the dependency graph is essentially at the latest compatible versions given current stable releases.