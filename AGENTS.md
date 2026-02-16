# Gilt — Agent Guidelines

Local-only, privacy-first personal finance tool. All processing runs on the user's machine — no network I/O, no external APIs, no cloud services.

## Engineering Principles

Apply these Simple Design Heuristics in priority order:

1. **All tests pass** — Correctness is non-negotiable. Every change keeps the suite green.
2. **Reveals intent** — Code reads like an explanation. Names and structure tell the story.
3. **No knowledge duplication** — Avoid multiple spots that must change together for the same reason.
4. **Minimal entities** — Remove unnecessary indirection. Fight complexity by eliminating the non-essential.

**Functional core, imperative shell**: Pure business logic isolated from I/O and side effects. Push side effects to boundaries.

When circumstances suggest breaking these principles, explicitly consult the user.

## Architecture

- **Data storage**: CSV ledgers (`data/accounts/*.csv`), YAML config (`config/*.yml`)
- **Interfaces**: CLI (Typer/Rich) and GUI (PySide6/Qt6) share business logic through services
- **Privacy model**: Raw financial data never leaves the machine; local LLM inference via `mojentic` for duplicate detection
- **Safety**: All mutation commands default to dry-run; requires explicit `--write` flag

## Directory Layout

| Path | Purpose | Mutability |
|---|---|---|
| `ingest/` | Raw bank CSV exports | **Immutable** — never modified by tools |
| `data/accounts/*.csv` | Processed per-account ledgers | Written only with `--write` |
| `config/accounts.yml` | Account definitions, source patterns, import hints | User-managed |
| `config/categories.yml` | Category hierarchy with budgets | User-managed |
| `reports/` | Generated artifacts (safe to regenerate) | Tool-generated |
| `dist/` | Build artifacts (sdist, wheel) | Tool-generated, gitignored |
| `data/private/` | Private/intermediate artifacts (not committed) | Local only |

## Ledger Schema

Columns in order (source of truth: `gilt.ingest.STANDARD_FIELDS`):

`transaction_id | date | description | amount | currency | account_id | counterparty | category | subcategory | notes | source_file | metadata`

- `date`: YYYY-MM-DD
- `amount`: signed float; debits negative, credits positive
- `currency`: default CAD
- All ledger I/O goes through `gilt.model.ledger_io.{load_ledger_csv, dump_ledger_csv}`

## Transaction ID (Do Not Change)

Deterministic SHA-256 hash, first 16 hex chars:
```
SHA-256("account_id|date|amount|description")[:16]
```
Values exactly as written to output columns. CLI commands accept 8-char prefixes. Any change requires a migration plan for existing ledgers.

## Key Data Models

- `gilt.model.account.py` — `Transaction`, `TransactionGroup`, `Account` (Pydantic v2)
- `gilt.model.category.py` — `Category`, `Subcategory`, `CategoryConfig`
- `gilt.model.duplicate.py` — `TransactionPair`, `DuplicateAssessment`, `DuplicateMatch`

## Environment & Tooling

This project uses **uv** as its package manager, build tool, and task runner. Prefer `uv run` over activating the virtualenv directly.

- Python 3.13, repo-local virtualenv managed by uv (`uv.lock` is committed)
- Install deps: `uv sync` (dev deps included by default), `uv sync --extra gui` for GUI
- Run anything in the venv: `uv run <command>` (e.g. `uv run gilt --help`)
- Lint: `uv run ruff check .` (rules E,F; line-length 100; excludes data/, ingest/, reports/)
- Tests: `uv run pytest` (discovers `*_spec.py` under `src/`)
- Build: `uv build` (produces sdist + wheel in `dist/`)
- Publish: `uv publish` (uploads to PyPI)
- Never use system python, `pip3`, or `python3` directly

## CLI Commands

All commands are local-only. Mutations are dry-run by default; pass `--write` to persist.

- **ingest** — Normalize raw CSV exports to per-account ledgers. Matches `config/accounts.yml` source_patterns, maps bank columns to standard schema, computes transaction IDs idempotently, runs transfer linking post-ingest.
- **note** — Add/update a note on a transaction by ID prefix. `--write` to persist.
- **ytd** — Display year-to-date transactions for an account. Read-only.
- **categorize** — Assign categories to transactions. Supports batch mode with `--description`, `--desc-prefix`, `--pattern`, `--amount`.

Batch operations: always show preview table and count before confirming.

## Transfer Linking

Implemented in `gilt.transfer.linker.link_transfers`, run post-ingest.
- Parameters: `window_days=3`, `epsilon_direct=0.01`, `epsilon_interac=1.75`, `fee_max_amount=3.00`, `fee_day_window=1`
- Writes metadata to matched transactions under `primary.metadata.transfer` with: role, counterparty_account_id, counterparty_transaction_id, amount, method, score, fee_txn_ids
- Idempotent: updates existing transfer blocks non-destructively

## LLM Integration

Uses **mojentic** for local LLM inference (via Ollama). Duplicate detection flow:
1. Find candidate pairs (same account/amount/date, different descriptions)
2. LLM analyzes with structured output → `DuplicateAssessment`
3. Interactive mode records feedback → `PromptManager` for learning

## Test Conventions

Tests are executable specifications alongside source files:

```python
# File: *_spec.py
class DescribeSomething:
    def it_should_do_the_thing(self):
        # arrange-act-assert
```

Config: `python_files = "*_spec.py"`, `python_classes = "Describe*"`, `python_functions = "it_should_*"`, `testpaths = ["src"]`

**Red-Green-Refactor workflow:**
1. Write failing test describing desired behavior
2. Implement simplest solution to make test pass
3. Refactor to reveal intent, eliminate duplication
4. Keep tests green after each step

Use `pytest-mock` for isolation, `pytest-cov` for coverage.

## GUI Patterns

GUI business logic lives in `src/gilt/gui/services/`:
- `transaction_service.py`, `category_service.py`, `budget_service.py`, `import_service.py`

Services are UI-agnostic and testable independently (functional core). Views/dialogs handle I/O (imperative shell). Dependencies are explicit through injection.

## Common Tasks

### Adding a CLI Command
1. Create `src/gilt/cli/command/<name>_spec.py` with failing test
2. Create `src/gilt/cli/command/<name>.py` with `run()` function
3. Implement simplest solution to pass test
4. Register in `src/gilt/cli/app.py` via Typer
5. Follow dry-run pattern (default `write=False`)
6. Refactor, keep tests green

### Adding a GUI View
1. Create view in `src/gilt/gui/views/<name>.py` as QWidget/QMainWindow
2. Use service layer (never direct file I/O in views)
3. Connect signals/slots for async operations
4. Add to navigation in `main_window.py`

### Modifying Ledger Schema
1. Update `gilt/model/account.py` — `Transaction` model
2. Update `gilt/model/ledger_io.py` — CSV parsing/writing
3. Update all commands that read/write ledgers
4. Plan migration path for existing data

### Building & Publishing

**Package**: `gilt` on PyPI. Build backend: **hatchling** (src layout). Test files (`*_spec.py`) are excluded from both sdist and wheel.

```bash
# Build sdist + wheel into dist/
uv build

# Publish to PyPI
uv publish

# Publish to TestPyPI first (for testing)
uv publish --index-url https://test.pypi.org/simple/
```

**Version management**: Update `version` in `pyproject.toml` `[project]` section before each release. Follow semver — bump minor for features, patch for fixes.

**End-user install** (via pipx or uv):
```bash
pipx install gilt
# or
uv tool install gilt
```

**Pre-release checklist**:
1. All tests pass (`uv run pytest`)
2. Lint clean (`uv run ruff check .`)
3. Version bumped in `pyproject.toml`
4. Clean build (`rm -rf dist && uv build`)
5. No real financial data in any tracked file

## Privacy & Redaction

**This is a public repository. Real financial and personally identifying data MUST NEVER appear in tracked files.**

### No Real Data in Code or Git History

- **Source code**: Never embed real bank names, account IDs, institution names, transaction descriptions, employer names, or budget amounts in source files, test fixtures, or docstrings. Use synthetic/generic placeholders (e.g., `MYBANK_CHQ`, `EXAMPLE UTILITY`, `Exampleville`).
- **Tests**: All test fixtures must use fictional data — fake account IDs, fake descriptions, fake amounts. No real transaction references, no real merchant names, no real locations that could identify the user.
- **Documentation**: Examples in README, docs/, and CLI help text must use generic names. Never reference real financial institutions by their actual name or real account structures.
- **Config files**: `config/` is gitignored. Starter templates in `init.py` must use only generic placeholder values.
- **Git history**: If real data is accidentally committed, it must be scrubbed from history before pushing (orphan branch strategy). A `git grep` pass is insufficient — force-push with clean history is required.

### Runtime Privacy

- Never send raw ledger rows or ingest CSVs to external services or LLMs (local LLM only).
- For documentation or bug reports, use synthetic data or redact: mask account/card numbers (keep last 4), tokenize counterparties (e.g., `Vendor_12`), keep mappings under `data/private/`.
- Do not log raw descriptions outside local console; prefer aggregated summaries.

### Adding Examples or Fixtures

When writing new tests, docs, or CLI examples, use these conventions:

| Real concept | Generic replacement |
|---|---|
| Bank names | `MyBank`, `SecondBank` |
| Account IDs | `MYBANK_CHQ`, `MYBANK_CC`, `BANK2_BIZ`, `BANK2_LOC` |
| Merchants | `EXAMPLE UTILITY`, `SAMPLE STORE`, `ACME CORP` |
| Locations | `Exampleville`, `Anytown`, `Othertown` |
| Employers | `Work` (as category name) |
| Transaction refs | `REF1234ABCD`, `TX9876WXYZ` |

Any relaxation of privacy rules or external integrations must be documented here first.

## Anti-Patterns

- **No real financial data in tracked files** — no real bank names, account IDs, merchant names, employer names, budget amounts, or locations in source, tests, or docs
- No network I/O or external API calls
- No temporary files for short operations (use in-memory)
- No silent data mutation without dry-run preview
- No hardcoded file paths (use Path objects)
- No generic test names (`test_*`); use BDD style (`it_should_*`)
- No implementation before tests
- No commits with failing tests or lint errors
- No speculative features (YAGNI)

## Quality Checklist

Before declaring work complete:
- **No real financial data** in any tracked file (grep for institution names, real account IDs, real merchant names)
- All tests pass (`pytest`)
- Linting clean (`ruff check .`)
- Coverage adequate for critical paths
- Documentation updated in sync with code
- Virtual environment used
- Dry-run pattern followed for mutations
- Changes are small, atomic, and focused
