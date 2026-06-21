Dependency update complete. Here's a summary of what was done:

**Updated packages** (minor/patch only):
| Package | Old | New |
|---|---|---|
| griffelib | 2.0.2 | 2.1.0 |
| pytest | 9.1.0 | 9.1.1 |
| scipy | 1.17.1 | 1.18.0 |

`pydantic-core` (2.46.4 → 2.47.0) was not independently upgradable — it's pinned by pydantic's own constraints and will update when pydantic releases a compatible version.

**Quality gates:** ✅ 1479 tests passed (66 skipped), lint clean, build successful. Changes committed and pushed to `main`.