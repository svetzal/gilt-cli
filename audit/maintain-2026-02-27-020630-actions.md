The dependency update is complete. Here's a summary of what happened:

## Results

### ✅ Updated
| Package | Version Change | Type |
|---|---|---|
| `ruff` | 0.15.2 → 0.15.4 | Dev dependency (patch) |

### ⏭️ Skipped
| Package | Reason |
|---|---|
| `pydantic-core` | Not independently upgradeable — its version is managed by `pydantic` itself. `pydantic` 2.12.5 is already the latest, and `pydantic-core` will advance automatically when pydantic releases a version requiring it. |

### ✅ All Quality Gates Passed
- **`uv run pytest`** — 527 tests passed (1 pre-existing macOS `sysctl` warning from joblib, unrelated to this update)
- **`uv run ruff check .`** — clean
- **`uv build`** — sdist and wheel built successfully

The project was already well up-to-date. Only a minor ruff patch update was available, and it was applied cleanly. The `uv.lock` file has been updated to reflect the new pinned version.