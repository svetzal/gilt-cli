# Gilt — Agent Guidelines

Local-only, privacy-first personal finance tool. All processing runs on the user's machine — no network I/O, no external APIs, no cloud services.

See [CHARTER.md](CHARTER.md) for the project's purpose, vision, and guiding constraints. Read the charter before assessing priorities or proposing new directions — it defines what Gilt is for and what it will not compromise on.

## Engineering Principles

Apply these Simple Design Heuristics in priority order:

1. **All tests pass** — Correctness is non-negotiable. Every change keeps the suite green.
2. **Reveals intent** — Code reads like an explanation. Names and structure tell the story.
3. **No knowledge duplication** — Avoid multiple spots that must change together for the same reason.
4. **Minimal entities** — Remove unnecessary indirection. Fight complexity by eliminating the non-essential.

**Functional core, imperative shell**: Pure business logic isolated from I/O and side effects. Push side effects to boundaries.

When circumstances suggest breaking these principles, explicitly consult the user.

## Development Workflow

Trunk-based development: `main` is the only long-lived branch. All work lands on `main` via direct commit. Feature branches are not pushed to `origin`. Pull requests are not used. Short-lived local working branches (e.g. hopper worktrees) are merged to `main` and deleted locally before work is considered complete.

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

Columns in order (source of truth: `gilt.model.ledger_io.STANDARD_FIELDS`):

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

- Python >=3.13, repo-local virtualenv managed by uv (`uv.lock` is committed)
- Dev deps (pytest, ruff, mkdocs) are in `[dependency-groups]` — installed automatically by `uv sync`
- Optional extras (gui, ml) are in `[project.optional-dependencies]` — part of published package metadata
- Install deps: `uv sync` (dev deps included by default), `uv sync --extra gui` for GUI, `uv sync --extra ml` for ML
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

### GUI Mutation Pattern (The Dual-Write Rule)

Every GUI mutation that writes to CSV must follow this three-step sequence in order:

1. **Write to CSV** (and optionally record event to event store)
2. **Call `self._sync_projections()`** — rebuilds projections DB from new events so the read layer is consistent
3. **Call `self.reload_transactions()`** — reloads the view from the now-consistent projections DB

Skipping step 2 means the view reloads stale data and the user sees no change until the next restart.

**Reference implementation**: `_apply_categorization` in `src/gilt/gui/controllers/transaction_mutation_controller.py`.

### QThread Worker Lifecycle

Improper worker lifecycle causes segfaults when a worker emits signals to a widget that Qt has already destroyed. Follow these rules without exception:

- Always declare the worker attribute with a `None` default: `self.worker: WorkerType | None = None`
- Always implement `cleanupPage()` on `QWizardPage` subclasses that start workers; or override `reject()`/`closeEvent()` on dialogs that start workers
- Before requesting interruption, **disconnect all signals** from the worker to prevent callbacks firing on destroyed objects
- After `requestInterruption()`, call `worker.wait(2000)` to block until the OS thread exits (or times out)
- Never use `except Exception: pass` in worker `run()` methods — emit the `error` signal instead so failures are visible
- When filtering `_old_workers`, call `w.wait(0)` on stopped workers before discarding to fully join the OS thread

**Reference implementation**: worker interrupt handling in `src/gilt/gui/controllers/intelligence_scan_controller.py`; `cleanupPage` in `src/gilt/gui/views/categorization_review_page.py` and `src/gilt/gui/views/import_wizard/pages/execute_page.py`; `ImportWizard.reject` in `src/gilt/gui/views/import_wizard/wizard.py`.

## CLI Command Module Layout

Complex CLI commands are split into three cohesive modules following the **functional core, imperative shell** pattern:

| Module | Responsibility |
|---|---|
| `<name>.py` | Orchestration only — `run()` and pure helpers. Imports from view/review modules. No `Table(`, `Prompt`, or `rich.progress` at the top level. |
| `<name>_view.py` | Rich rendering — `display_*`, `print_*`, and progress-bar builders. No user prompts, no persistence. |
| `<name>_review.py` | Interactive input loops — `Prompt.ask` calls, decision handling, feedback recording. Calls view functions for output. |

**Note**: `<name>_review.py` is omitted when a command has no interactive input loop — confirmation is delegated entirely to `mutations.run_confirmed_mutation` / `run_persisted_mutation`. Commands like `categorize` and `recategorize` are two-module (orchestration + view), not three.

**Mutation flow rule**: every preview → confirm → dry-run → persist sequence routes through `mutations.run_confirmed_mutation` or `mutations.run_persisted_mutation`. Never hand-roll this pattern inline.

**Dry-run contract**: when `write=False`, the command MUST call `print_dry_run_message()` (provided by the mutation helpers) and return without emitting any events or modifying any files.

**Shared formatting**: the 5-column base row for transaction tables is `base_match_row(account_id, txn)` from `formatting.py`. The 6-column category-preview row is `category_preview_row(account_id, txn, category_path)` — use it instead of inline tuple construction.

**Reference implementations**:
- `categorize.py` / `auto_categorize.py` — mutation helper usage and dry-run pattern
- `categorize.py` / `categorize_view.py` — two-module split (no review; confirmation via mutation helpers)
- `recategorize.py` / `recategorize_view.py` — two-module split (no review; confirmation via mutation helpers)
- `auto_categorize_view.py` / `auto_categorize_review.py` — view/review split
- `duplicates_view.py` / `duplicates_review.py` — progress-bar isolation in view module

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
pipx install "gilt[gui]"
# or
uv tool install "gilt[gui]"
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

## Skill Distribution

The gilt skill for Claude Code is distributed alongside the CLI package.

- **Source of truth**: `src/gilt/skills/gilt/` directory in the repo (no version in frontmatter)
- **Install locally**: `gilt skill-init` — copies to `.claude/skills/gilt/` in CWD
- **Install globally**: `gilt skill-init --global` — copies to `~/.claude/skills/gilt/`
- **Force overwrite**: `gilt skill-init --force` — bypasses version guard
- **Version stamping**: `gilt-version: <VERSION>` is added to SKILL.md frontmatter at install time from the package version
- **Version guard**: Refuses to overwrite if the installed version is newer than the running binary (prevents downgrade). `--force` bypasses this.

**Pre-release checklist addition**: After bumping version in `pyproject.toml`, verify `gilt skill-init` stamps the correct version.

## Naming Conventions

Function verb prefixes are standardised across the codebase. Follow these rules when naming new functions or renaming existing ones:

| Operation | Standard verb | Rationale |
|---|---|---|
| Read from disk / DB | `load_` | All file/DB reads; `read_` is a violation |
| Query in-memory state | `get_` | Accessors, computed properties, in-memory lookups |
| Search / filter a collection | `find_` | Semantically distinct from `get_`; implies a search |
| Serialize to string / format | `dump_` | Pure serialization, no I/O side-effect |
| Write to disk (I/O-inclusive) | `save_` | When the call itself writes a file |
| Write + emit event + rebuild | `persist_` | The three-step write-through mutation pattern |
| Orchestrate a domain action | `run_` | Service-level orchestration; use instead of `execute_` or `process_` |
| Construct objects from data | `build_` | Logic-bearing factory; `make_` for test helpers only |

The `find_projection_by_prefix` / `find_by_id_prefix` split in `TransactionOperationsService` exemplifies the rule that two methods doing similar things on *different types* must have names that reveal the type they operate on.

**Remediation history:** Commit `4eab73a` applied `scan_→find_` and `rebuild_→build_` conventions across storage and service layers. A subsequent refactor extended the full convention set (`filter_→find_`, `plan_→build_`, `apply_→run_`, `calculate_→get_`, `generate_→build_`, `resolve_→find_/build_/run_`, `parse_→build_/load_`) to all remaining layers (services, CLI commands, GUI views, transfer, ingest). All old verb prefixes have been eliminated from the codebase.

## Storage Projection Module Layout

The `projection.py` module fused schema, write-side reducer, and read-side queries into one class. It has been split into cohesive units following the **extract-collaborators-behind-facade** pattern:

| Module | Responsibility |
|---|---|
| `projection_schema.py` | `ensure_projection_schema` — DDL, migrations |
| `projection_reducer.py` | `apply_events` and per-event `_apply_*` functions — write side |
| `projection_queries.py` | `get_transaction`, `get_all_transactions`, etc. — read side |
| `duplicate_normalization.py` | Pure duplicate-group repair: `build_duplicate_corrections`, `find_root_primary`, `normalize_duplicate_groups` |
| `projection.py` | `ProjectionBuilder` facade — orchestrates the above; re-exports all public names so existing callers need no changes |

**Rule:** When adding new projection behaviour, place it in the appropriate collaborator module — not back into `projection.py`. Schema changes go to `projection_schema.py`, new event handlers to `projection_reducer.py`, new queries to `projection_queries.py`.

## Budget Projection Module Layout

The `budget_projection.py` module fused schema, write-side reducer, and read-side queries into one class (same pattern as `projection.py`). It has been split into cohesive units following the same **extract-collaborators-behind-facade** pattern:

| Module | Responsibility |
|---|---|
| `budget_projection_schema.py` | `ensure_budget_projection_schema` — DDL for `budget_projections` and `budget_history` tables |
| `budget_projection_reducer.py` | `apply_budget_events` and per-event `_apply_*` functions — write side |
| `budget_projection_queries.py` | `BudgetProjection` type, `get_budget`, `get_active_budgets`, `get_budgets_at_date`, `get_budget_history` — read side |
| `budget_projection.py` | `BudgetProjectionBuilder` facade — orchestrates the above; re-exports `BudgetProjection` and `BudgetProjectionBuilder` so existing callers need no changes |

**Rule:** When adding new budget projection behaviour, place it in the appropriate collaborator module — not back into `budget_projection.py`. Schema changes go to `budget_projection_schema.py`, new event handlers to `budget_projection_reducer.py`, new queries to `budget_projection_queries.py`.

## Ingest Module Layout

The `ingest/__init__.py` module fused column detection, normalization, model mapping, account matching, config I/O, event emission, and ledger I/O into one file. It has been split into cohesive units following the **extract-collaborators-behind-facade** pattern:

| Module | Responsibility |
|---|---|
| `column_mapping.py` | Pure column detection: `_first_match`, `_detect_columns`, `_RBC_REQUIRED_COLS`, `_detect_rbc_overrides`, `find_missing_columns` |
| `normalization.py` | Pure DataFrame normalization: `build_transaction_id`, `HASH_ALGO_SPEC`, `_resolve_date_series`, `_resolve_description_series`, `_resolve_amount_series`, `_build_transaction_dataframe` |
| `transaction_mapping.py` | Pure DataFrame ↔ model mapping: `_opt_str`, `_groups_to_dataframe`, `_dataframe_to_groups`, `build_groups_from_dataframe`, `build_transactions_from_dataframe` |
| `account_matching.py` | Pure account matching: `infer_account_for_file`, `build_normalization_plan` |
| `config_loader.py` | Config I/O (reads YAML from disk): `load_accounts_config` |
| `events.py` | Event emission side effects: `_emit_description_observed_event`, `_emit_transaction_imported_event`, `_emit_transaction_events` |
| `ledger_pipeline.py` | Ledger I/O (reads/merges CSV files): `load_file`, `_merge_with_existing_ledger` |
| `__init__.py` | Facade — `normalize_file` orchestration; re-exports all public names so existing callers need no changes |

**Rule:** When adding new ingest behaviour, place it in the appropriate collaborator module — not back into `__init__.py`. New pure transforms (no I/O) go in the core modules (`column_mapping.py`, `normalization.py`, `transaction_mapping.py`, `account_matching.py`). New I/O or side-effect logic goes in the shell modules (`config_loader.py`, `events.py`, `ledger_pipeline.py`).

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
