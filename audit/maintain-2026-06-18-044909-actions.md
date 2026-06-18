Done. Here's the summary:

**Updated (2 packages):**
- `certifi` 2026.5.20 → 2026.6.17 (patch — CA bundle refresh)
- `openai` 2.42.0 → 2.43.0 (minor — transitive via `mojentic`)

**Left at current version (1 package):**
- `pydantic-core` 2.46.4 — can't reach 2.47.0 because `pydantic` is pinned at ≤2.13.x by upstream transitive constraints from `mojentic`/`anthropic`/`openai`; the resolver correctly held it back

**Quality gates:** 1 479 passed, 65 skipped · lint clean · build successful. Committed and pushed to `main`.