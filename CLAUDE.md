# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Finance Local is a **local-only, privacy-first** Python CLI tool for personal finance management. It normalizes bank CSV exports into standardized ledger files, links inter-account transfers, and provides budgeting and categorization features.

**Core Principles:**
- Local-only: No network I/O, all processing happens on the user's machine
- Privacy-first: Raw transaction data never leaves the machine
- Deterministic: Re-running commands with identical inputs produces identical results
- Safe by default: All mutation commands are dry-run by default (require `--write` to persist)
- Minimal dependencies: Standard Python tooling with trusted libraries only

## Development Setup

### Prerequisites
- Python 3.13 or higher
- Virtual environment (recommended)

### Installation
```bash
# Create and activate virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e .[dev]

# Verify installation
finance --help
```

## Testing

### Running Tests
```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a single test file
pytest src/finance/cli/command/note_spec.py

# Run tests matching a pattern
pytest -k "test_pattern"
```

### Test Discovery
- Test files: `*_spec.py` (not `test_*.py`)
- Test classes: `Describe*` (not `Test*`)
- Test functions: `it_should_*` (not `test_*`)
- Location: Tests live alongside source files in `src/` (not in separate `tests/` directory)

### Test Conventions
- Use descriptive test names that explain the behavior being tested
- Example: `it_should_update_note_with_write_and_be_dry_run_by_default`
- Use `tmp_path` fixture from pytest for file system operations
- Tests should be deterministic and isolated (no shared state)

## Linting

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .
```

## Architecture

### Directory Structure
```
finance/
├── config/
│   ├── accounts.yml      # Account configuration (source patterns, import hints)
│   └── categories.yml    # Category definitions with budgets
├── ingest/               # Raw bank CSV exports (immutable inputs, never committed)
├── data/accounts/        # Normalized ledger files (outputs, never committed)
├── src/finance/
│   ├── cli/
│   │   ├── app.py        # Typer CLI entry point with all command registrations
│   │   └── command/      # Individual command implementations (one file per command)
│   ├── model/            # Pydantic models and I/O logic
│   ├── ingest/           # CSV normalization logic
│   └── transfer/         # Transfer linking logic
```

### Key Architectural Patterns

#### Command Structure (Flat, Not Nested)
- Commands use **flat verbs** (e.g., `finance categorize`, not `finance category add-transaction`)
- Each command has its own file in `src/finance/cli/command/`
- Command registration happens in `src/finance/cli/app.py` using Typer decorators
- Each command module exports a `run()` function that returns an exit code (int)

#### Dry-Run Safety Pattern
All commands that modify files follow this pattern:
- Default: dry-run mode (shows what would happen, makes no changes)
- Use `--write` flag to persist changes
- Interactive confirmations for destructive operations (can be skipped with `--yes`)
- Commands should clearly indicate dry-run vs. write mode in output

Example:
```python
def run(..., write: bool = False) -> int:
    # ... determine changes ...
    if not write:
        console.print("[yellow]DRY-RUN:[/] Would modify X transactions")
        console.print("Use --write to persist changes.")
        return 0
    # ... persist changes ...
```

#### Ledger Schema & I/O
- Ledger files use a **flat CSV schema** defined in `src/finance/model/ledger_io.py`
- Standard fields (in order): `transaction_id`, `date`, `description`, `amount`, `currency`, `account_id`, `counterparty`, `category`, `subcategory`, `notes`, `source_file`, `metadata_json`
- Forward schema supports split transactions via `row_type` column (`primary` or `split`)
- Backward compatible: legacy ledgers without `row_type` are treated as all-primary rows
- Use `load_ledger_csv()` and `dump_ledger_csv()` for all ledger I/O (handles validation)

#### Transaction IDs (FROZEN SPEC - Do Not Change Without Migration Plan)
Transaction IDs are **deterministic hashes** using a frozen specification:
```python
SHA-256(account_id|date|amount|description)[:16]
```

**Important Details:**
- Values are hashed exactly as written to output columns:
  - `date` in YYYY-MM-DD format
  - `amount` via Python `str()` (e.g., "-10.5")
  - `description` as-is (preserves exact text)
  - `account_id` as configured
- The hex digest is truncated to **16 characters** (not 8)
- First 8 characters (`TxnID8`) are used in UI for easy reference
- Users can specify prefixes in commands (e.g., `--txid a1b2c3d4`)
- **Any change to this spec requires a migration plan for existing ledgers**
- Ensures idempotent ingestion (same transaction → same ID)
- Sorting is deterministic by `[date, amount, description]`

#### Configuration Files

**config/accounts.yml** (optional but recommended):
- Maps raw CSV filenames to account IDs for accurate ingestion
- `accounts[].source_patterns`: Glob patterns matched against ingest filenames
  - Example: `"*rbc*chequing*.csv"` matches files with "rbc" and "chequing" in name
  - Multiple patterns supported per account
- `accounts[].import_hints`: Optional hints to aid CSV parsing (see `finance.model.account.ImportHints`)
  - `header_row`: Which row contains column headers (default: 0)
  - `date_format`: strptime format string (default: "%Y-%m-%d")
- If config is missing, simple filename heuristics may infer RBC_CHQ, SCOTIA_CURR, SCOTIA_LOC
- Model defined in `finance.model.account`, loaded via `finance.ingest.load_accounts_config()`

**config/categories.yml**:
- Category/subcategory definitions with optional budgets
- Categories can have descriptions, budgets (amount + period), and subcategories
- Model defined in `finance.model.category`
- YAML loading/saving logic in `finance.model.category_io`

#### Batch vs. Single Transaction Operations
Many commands support both modes:
- **Single mode**: `--txid <prefix>` targets one transaction by ID
- **Batch mode**: `--description`, `--desc-prefix`, or `--pattern` targets multiple transactions
  - Batch mode requires `--yes` for auto-confirmation (otherwise prompts)
  - Shows preview table before changes

Examples: `note`, `categorize`

#### Rich Output
- Use `rich.console` for all user-facing output (imported from `finance.cli.command.util`)
- Tables for transaction listings (`ytd`, `uncategorized`, `budget`)
- Color coding: green for success, yellow for warnings, red for errors
- Syntax: `console.print("[green]Success[/]")`

### Important Models

#### Transaction & TransactionGroup
- `Transaction`: Primary transaction with all standard fields
- `SplitLine`: Split transaction (for multi-category splits)
- `TransactionGroup`: Container with one primary + zero or more splits
- Defined in `src/finance/model/account.py`

#### Category
- `Category`: Top-level category with optional subcategories and budget
- `Subcategory`: Child category
- `Budget`: Amount + period (monthly/yearly)
- Defined in `src/finance/model/category.py`

### Command Implementation Guidelines

When adding a new command:

1. **Create command file**: `src/finance/cli/command/<command_name>.py`
   - Implement `run()` function with appropriate parameters
   - Return exit code: 0 for success, 1 for errors
   - Use `console` from `.util` for output
   - Follow dry-run pattern if command mutates data

2. **Create test file**: `src/finance/cli/command/<command_name>_spec.py`
   - Use `it_should_*` naming convention
   - Test both dry-run and `--write` modes
   - Use `tmp_path` for file system operations

3. **Register in app.py**: Add `@app.command()` decorator
   - Use Typer's `Option()` for parameters
   - Consistent help text style
   - Call `run()` and exit with its return code

4. **Update README.md**: Add command documentation with examples

### Transfer Linking
The `ingest` command automatically identifies and annotates inter-account transfers:
- Implemented in `finance.transfer.linker.link_transfers()`
- Runs post-ingestion when `--write` is specified
- Purely local: reads `data/accounts/*.csv` and writes back when `write=True`

**Default Parameters** (set in ingest command):
- `window_days=3`: Maximum days apart for matching transactions
- `epsilon_direct=0.0`: Amount tolerance for direct transfers (exact match)
- `epsilon_interac=0.0`: Amount tolerance for Interac e-Transfers (exact match)
- `fee_max_amount=3.00`: Maximum fee amount to consider
- `fee_day_window=1`: Days to search for associated fees

**Transfer Metadata Structure** (stored in `primary.metadata.transfer`):
```json
{
  "transfer": {
    "role": "source" | "destination",
    "counterparty_account_id": "OTHER_ACCT",
    "counterparty_transaction_id": "abc123...",
    "amount": 100.00,
    "method": "direct" | "interac",
    "score": 1.0,
    "fee_txn_ids": ["def456..."]
  }
}
```

**Behavior:**
- Idempotent: updates existing transfer block non-destructively
- Matches transactions across accounts by amount and date
- Handles direct transfers and Interac e-Transfers separately
- Detects and links associated fees (e.g., Interac fees)

### Category Syntax
Categories support hierarchical structure with shorthand:
- Category only: `--category "Housing"`
- With subcategory (shorthand): `--category "Housing:Utilities"`
- With subcategory (explicit): `--category "Housing" --subcategory "Utilities"`

Parsing logic splits on `:` to extract category and subcategory.

## Privacy & Security Considerations

**CRITICAL**: This tool is designed for privacy-first financial data management.

### Non-Negotiable Rules
- **Never add network I/O code** (no HTTP requests, API calls, telemetry)
- **Never send raw ledger rows or raw ingest CSVs to external services or LLMs**
- **Never log or print raw transaction data** without explicit user control
- `ingest/` and `data/accounts/` directories must remain in `.gitignore`
- All processing must be deterministic and reproducible
- Only trusted dependencies: pandas, pyyaml, pydantic, typer, rich

### Privacy & Redaction Rules

**When creating examples for documentation or bug reports:**
- Use synthetic data whenever possible
- If real data is needed, redact:
  - **Account/card numbers**: Keep last 4 digits only (e.g., `****1234`)
  - **Emails/addresses**: Mask or tokenize (e.g., `user***@example.com`)
  - **Counterparties**: Tokenize (e.g., `Vendor_12`) and keep mapping private under `data/private/`
- **Do not log raw descriptions** outside local console
- Prefer aggregated summaries (e.g., "45 transactions totaling $1,234.56")

### Data Immutability & Safety
- `ingest/` directory is **never modified** by tools (treat as immutable)
- `data/accounts/*.csv` are the **only files** overwritten/created by ingestion or linking
- Modifications only occur when `--write` is explicitly used
- All operations are idempotent: re-running with same inputs produces identical results

### Change Control
- Any relaxation of privacy rules or external integrations must be documented before adoption
- Any change to processed schema or transaction ID spec requires migration note and backfill plan
- Discuss privacy implications before adding network calls (avoid if possible)

## Common Tasks

### Adding a New Command
1. Determine if command mutates data (if yes, use dry-run pattern with `--write`)
2. Create `src/finance/cli/command/<name>.py` with `run()` function
3. Create `src/finance/cli/command/<name>_spec.py` with tests
4. Register in `src/finance/cli/app.py` with `@app.command()`
5. Update `README.md` with usage examples

### Modifying Ledger Schema
- Update `LEDGER_COLUMNS` in `src/finance/model/ledger_io.py`
- Update `load_ledger_csv()` and `dump_ledger_csv()` functions
- Ensure backward compatibility with existing ledgers
- Add migration guide to README if needed
- Update tests

### Adding a New Category Field
- Update `Category` model in `src/finance/model/category.py`
- Update YAML loading/saving in `src/finance/model/category_io.py`
- Update `categories` command to display new field
- Update tests

## Code Style

- Target Python 3.13 syntax/features
- Type hints: Use modern syntax (`list[str]`, not `List[str]`)
- Imports: Use `from __future__ import annotations` at top of file
- Line length: 100 characters (Ruff configured)
- Docstrings: Module-level docstrings explain purpose and privacy considerations
- Comments: Explain "why" not "what"; use for complex logic only

## Exit Codes

Commands should return:
- `0`: Success
- `1`: Error or user-initiated cancellation
- Typer automatically converts these to process exit codes

## File Paths

- Use `pathlib.Path` for all file operations
- Default paths defined as constants in `src/finance/cli/app.py`:
  - `DEFAULT_DATA_DIR = Path("data/accounts")`
  - `DEFAULT_INGEST_DIR = Path("ingest")`
  - `DEFAULT_CONFIG_PATH = Path("config/accounts.yml")`
- Always use absolute paths when reading/writing files
- Check file existence before operations and provide helpful error messages

## Data Handling Guarantees

**Immutability:**
- `ingest/` is **never modified** by the tools; only read from
- `data/accounts/*.csv` are the **only files** overwritten/created by ingestion or linking
- Only when `--write` is used
- All other directories are safe from tool modification

**Determinism:**
- All operations are local and deterministic
- Re-running with the same inputs is idempotent
- Transaction IDs are consistently computed from the same fields
- Sorting order is stable and predictable

**Privacy:**
- Private/intermediate artifacts (if needed) go in `data/private/` (not committed)
- Reports/plots (if needed) go in `reports/` (safe to regenerate, not committed)
- Never commit `ingest/` or `data/` to version control

## Do & Don't Checklist

**Do:**
- ✅ Run commands without `--write` first to preview changes
- ✅ Keep processed schema and transaction_id spec intact
- ✅ Keep transfer linking parameters in ingest consistent unless consciously tuning
- ✅ Use dry-run mode to verify changes before persisting
- ✅ Add tests when changing ingestion or ledger serialization
- ✅ Cover edge cases (missing columns, bank-specific quirks, idempotency)

**Don't:**
- ❌ Commit private mapping files (keep under `data/private/` and out of VCS)
- ❌ Expose raw rows in issues/PRs (share masked aggregates instead)
- ❌ Add network calls without discussion and documentation
- ❌ Change transaction ID spec without migration plan
- ❌ Modify files in `ingest/` directory
- ❌ Skip dry-run testing before persisting changes
