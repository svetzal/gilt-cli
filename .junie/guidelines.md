# Junie Guidelines (Concise)

Date: 2025-08-21
Scope: /Users/svetzal/Work/Mojility/finance

Purpose: Keep your finance data private and safe while enabling local Python/GenAI-assisted workflows.

1) Defaults (privacy-first)
- Local-only by default. Do not send raw data or PII to external services or LLMs.
- No raw row dumps in outputs without explicit approval; prefer summaries and aggregates.
- Treat transactions/*.csv as immutable raw inputs; never modify in place.

2) Redaction basics
- Mask account/card numbers (keep last 4 only) and emails/addresses.
- Tokenize counterparties (e.g., Vendor_12). Keep a private mapping if needed.
- If any data must leave this machine, use redacted/synthetic examples only.

3) Minimal working conventions
- Raw inputs: transactions/
- Processed outputs (optional): data/processed/
- Private/intermediate artifacts: data/private/
- Config: config/
- Reports (summaries/charts): reports/
- Environment: Always use the repo-local virtualenv for Python.
  - Activate: `source .venv/bin/activate` (if `.venv/` exists), otherwise `source venv/bin/activate`.
  - Use `python` and `pip` from the venv (do not use `python3`/`pip3` in commands).
  - Examples:
    - `python scripts/ingest_normalize.py` (dry-run default)
    - `python scripts/ingest_normalize.py --write` (writes outputs)

4) Standardized processed schema (target)
- transaction_id, date (YYYY-MM-DD), description, amount (signed), currency, account_id,
  counterparty, category, subcategory, notes, source_file

5) GenAI usage
- Default: external LLMs disallowed for raw data.
- If needed, summarize patterns and use redacted tokens; never paste raw CSV rows.
- No logging of sensitive prompts.

6) Assistant operating rules
- Ask before exposing raw samples. Prefer masked previews.
- Explain file changes before writing. Keep changes minimal.
- When unsure, ask for clarification.
- Scripts default to dry-run; writing requires explicit --write flag (e.g., scripts/ingest_normalize.py --write).

7) Change control
- Any relaxation (e.g., allow provider X for task Y) must be added here explicitly.

— End —
