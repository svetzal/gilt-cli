All done. Here's a summary of what was updated:

| Package | Old | New | Type |
|---------|-----|-----|------|
| `anthropic` | 0.109.1 | 0.109.2 | patch |
| `anyio` | 4.13.0 | 4.14.0 | minor |
| `openai` | 2.41.1 | 2.42.0 | minor |
| `tqdm` | 4.68.2 | 4.68.3 | patch |

Note: `pydantic-core` (2.46.4 → 2.47.0) was shown as outdated but wasn't updated — this is expected since `pydantic` pins compatible `pydantic-core` versions and the resolver keeps them in sync.

All quality gates passed: **1479 tests passed** (65 skipped), **lint clean**, **build successful**. Committed and pushed to `origin/main`.