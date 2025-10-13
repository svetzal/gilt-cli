# Mojility Finance — Project Guidelines (Local, Privacy‑First)

Last updated: 2025-08-22 06:47
Scope: /Users/svetzal/Work/Mojility/finance

Purpose: Keep this repository private, local-only, and consistent. These guidelines codify the conventions already used in the codebase so future changes remain aligned with the current track.


## Core Principles
- Local-only by default. No network I/O; all processing runs on local files.
- Privacy-first. Do not expose raw transaction rows outside this machine. Prefer summaries/aggregates when sharing.
- Deterministic, reproducible outputs in data/accounts/.
- Dry-run safety by default for any command that can write; require explicit --write.
- Minimal dependencies, standard Python tooling (pyproject.toml).


## Repository Truths (what the code already does)
- CLI: Typer app with commands ingest, note, ytd; entry point "finance" (finance.cli.app:app).
- Inputs: ingest/*.csv (immutable raw exports).
- Processed outputs: data/accounts/{ACCOUNT_ID}.csv (per-account ledgers).
- Config (optional): config/accounts.yml (accounts with source_patterns, hints).
- Transfer enrichment: metadata stored onto ledger rows via finance.transfer.linker.
- Standard processed schema (order fixed):
  transaction_id, date, description, amount, currency, account_id, counterparty, category, subcategory, notes, source_file
- Transaction ID (frozen spec): sha256 of "account_id|date|amount|description" (values as written), hex[:16]. Do not change without a migration plan.
- Python: 3.13; tests discovered as *_spec.py under src; lint via Ruff (E,F) with line-length 100.


## Directory & File Conventions
- Raw inputs: ingest/ (never modified by tools; treat as immutable).
- Ledgers (processed): data/accounts/*.csv (safe to overwrite/append by tools when --write).
- Config: config/accounts.yml (optional; drives source_patterns and hints for account inference).
- Reports/plots (optional): reports/ (artifacts safe to regenerate).
- Private/intermediate artifacts (if needed): data/private/ (not committed).


## Environment & Tooling
- Use the repo-local virtualenv.
  - Activate: `source .venv/bin/activate` (prefer) or `source venv/bin/activate`.
  - Use `python` and `pip` from the venv (avoid system python).
- Install in editable mode with dev extras if developing:
  - `pip install -e .[dev]`
- Run CLI:
  - `python -m finance.cli.app --help` or `finance --help`
- Lint: `ruff check .`
- Tests: `pytest` (discovers *_spec.py under src, quiet mode by default).


## CLI Commands (defaults and safety)
All commands are local-only. Commands that modify files are dry-run by default; pass --write to persist.

- Ingest: normalize raw CSV exports to per-account ledgers.
  - `finance ingest --config config/accounts.yml --ingest-dir ingest --output-dir data/accounts` (dry-run)
  - `finance ingest ... --write` (writes outputs)
  - Behavior:
    - Discovers candidate files by matching config.accounts[].source_patterns against filenames, or all *.csv if none.
    - Maps common bank columns to the standard schema (date/description/amount/currency) using heuristics.
    - Computes transaction_id (frozen spec) and appends new rows idempotently.
    - Sorting is deterministic by [date, amount, description].
    - Post-ingest, runs transfer linking to mark inter-account transfers in metadata.

- Note: add/update a note on a specific transaction in a ledger (by transaction ID prefix shown in tables).
  - `finance note --account RBC_CHQ --txid <TxnID8> --note "Text"` (dry-run)
  - `finance note ... --write` to persist.

- YTD: display year-to-date transactions for a single account.
  - `finance ytd --account RBC_CHQ [--year 2025] [--limit N] [--default-currency CAD]`
  - Read-only; renders a Rich table in the terminal.


## Privacy & Redaction Rules
- Never send raw ledger rows or raw ingest CSVs to external services or LLMs.
- If examples are required for documentation or bug reports, use synthetic data or redact:
  - Mask identifiers: account numbers/card numbers -> keep last 4; emails/addresses masked.
  - Tokenize counterparties (e.g., Vendor_12) and keep any mapping private under data/private/.
- Do not log raw descriptions outside local console; prefer aggregated summaries.


## Processed Schema (Target)
Columns (in order):
1) transaction_id
2) date (YYYY-MM-DD)
3) description
4) amount (signed float; debits negative, credits positive)
5) currency (default CAD)
6) account_id
7) counterparty (initially same as description; may be refined later)
8) category
9) subcategory
10) notes
11) source_file (origin CSV filename)

Schema source of truth: finance.ingest.STANDARD_FIELDS. Keep downstream tools compatible with this order.


## Transaction ID Spec (Do Not Change Lightly)
- HASH_ALGO_SPEC: v1 sha256("account_id|date|amount|description"). Hex digest truncated to 16 chars.
- Values exactly as written to the output columns (date in YYYY-MM-DD; amount via Python str(); description as-is).
- Any change requires a migration plan for existing ledgers.


## Transfer Linking
- Implemented in finance.transfer.linker.link_transfers and used post-ingest.
- Purely local: reads data/accounts/*.csv and writes back only when write=True (caller controls write).
- Parameters (defaults in ingest command):
  - window_days=3, epsilon_direct=0.01, epsilon_interac=1.75, fee_max_amount=3.00, fee_day_window=1
- Metadata written to each matched primary transaction under primary.metadata.transfer with:
  - role, counterparty_account_id, counterparty_transaction_id, amount, method, score, fee_txn_ids
- Idempotent behavior: updates existing transfer block non-destructively.


## Config: config/accounts.yml
- Optional but recommended for accurate file-to-account mapping.
- `accounts[].source_patterns`: glob patterns matched against ingest filenames (e.g., "*rbc*chequing*.csv").
- `accounts[].import_hints`: loose hints to aid CSV parsing; see finance.model.account.ImportHints.
- If config is missing, simple filename heuristics may infer RBC_CHQ, SCOTIA_CURR, SCOTIA_LOC.


## Data Handling Guarantees
- ingest/ is never modified by the tools; only read from.
- data/accounts/*.csv are the only files overwritten/created by ingestion or linking, and only when --write is used.
- All operations are local and deterministic; re-running with the same inputs is idempotent.


## Do & Don’t Checklist
- Do: run commands without --write first to preview changes.
- Do: keep processed schema and transaction_id spec intact.
- Do: keep transfer linking parameters in ingest consistent unless you consciously tune them.
- Don’t: commit private mapping files; keep them under data/private/ and out of VCS.
- Don’t: expose raw rows in issues/PRs; share masked aggregates instead.


## Testing & QA
- Run tests: `pytest` (discovers src/**/**/*_spec.py).
- Quick lints: `ruff check .` (targets Python 3.13; excludes data/, ingest/, reports/).
- When changing ingestion or ledger serialization, add/adjust specs under src/** to cover edge cases (missing columns, RBC quirks, idempotency).


## Change Control
- Any relaxation of privacy rules or external integrations must be documented here before adoption.
- Any change to processed schema or transaction ID requires a migration note and backfill plan.


## Notes for Contributors
- Prefer small, local, testable changes.
- Keep CLI safety consistent: dry-run defaults; explicit --write to persist.
- Avoid adding network calls; if absolutely necessary, discuss and document privacy implications here first.
