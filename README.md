# Gilt

A **local-only, privacy-first** command-line tool for managing personal gilt data from multiple bank accounts.

## Core Principles

- **Local-only**: All processing happens on your machine. No network I/O, no cloud services.
- **Privacy-first**: Raw transaction data never leaves your machine. Only you have access to your financial records.
- **Deterministic**: Re-running commands with the same inputs produces identical results.
- **Safe by default**: All commands that modify files are dry-run by default. Use `--write` to persist changes.
- **Minimal dependencies**: Standard Python tooling with a small set of trusted libraries.

## Features

### Transaction Management
- **Normalize** raw bank CSV exports into a standardized format
- **Track** transactions across multiple accounts (checking, savings, credit cards, lines of credit)
- **Link** inter-account transfers automatically with intelligent matching
- **Detect duplicates** using local LLM inference (privacy-preserving)
- **Annotate** transactions with custom notes and categories
- **View** year-to-date transactions in rich formatted tables

### Budgeting & Analysis
- **Categorize** transactions with hierarchical categories and subcategories
- **Auto-categorize** new transactions using machine learning (learns from your categorization history)
- **Track budgets** by category with monthly or yearly periods
- **Monitor spending** against budgets with visual indicators
- **Generate reports** for budget analysis and spending patterns
- **Diagnose issues** with orphaned categories and uncategorized transactions

### Event Sourcing Architecture
- **Complete audit trail** of all transactions and categorizations
- **Time-travel queries** to view historical budget states
- **ML-powered learning** from user feedback to improve duplicate detection
- **Immutable event log** for data integrity and analysis
- **Projection rebuilding** for flexible reporting and experimentation

## Installation

### Prerequisites

- Python 3.13 or higher
- Virtual environment (recommended)

### Setup

1. Clone or navigate to the repository:
```bash
cd /path/to/gilt
```

2. Create and activate a virtual environment:
```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

3. Install the package in editable mode with development tools:
```bash
pip install -e .[dev]
```

4. Verify installation:
```bash
gilt --help
```

## Directory Structure

```
gilt/
├── config/
│   └── accounts.yml          # Account configuration (optional but recommended)
├── ingest/                   # Raw bank CSV exports (immutable inputs)
│   ├── 2025-10-13-mybank-chequing.csv
│   ├── 2025-10-13-mybank-cc.csv
│   └── ...
├── data/
│   └── accounts/             # Normalized per-account ledgers (outputs)
│       ├── MYBANK_CHQ.csv
│       ├── MYBANK_CC.csv
│       ├── BANK2_BIZ.csv
│       └── BANK2_LOC.csv
└── reports/                  # Generated reports/plots (optional)
```

### File Conventions

- **ingest/**: Place raw CSV files exported from your bank here. These files are never modified by the tool.
- **data/accounts/**: Standardized ledger files, one per account. Safe to regenerate via the `ingest` command.
- **config/accounts.yml**: Maps raw CSV filenames to account IDs and provides parsing hints.

## Configuration

Create `config/accounts.yml` to define your accounts:

```yaml
accounts:
  - account_id: MYBANK_CHQ
    description: "MyBank Chequing"
    source_patterns:
      - "*mybank*chequing*.csv"
      - "*mybank*chq*.csv"
    import_hints:
      header_row: 0
      date_format: "%m/%d/%Y"

  - account_id: MYBANK_CC
    description: "MyBank Credit Card"
    source_patterns:
      - "*mybank*cc*.csv"
      - "*mybank*creditcard*.csv"

  - account_id: BANK2_BIZ
    description: "SecondBank Business Chequing"
    source_patterns:
      - "*bank2*business*.csv"

  - account_id: BANK2_LOC
    description: "SecondBank Line of Credit"
    source_patterns:
      - "*bank2*line*.csv"
      - "*bank2*loc*.csv"
```

## Commands

All commands are **local-only** and respect your privacy. Commands that modify files default to **dry-run mode**—use `--write` to persist changes.

### `accounts` - List Available Accounts

Display all configured accounts and their descriptions.

```bash
# List accounts from config
gilt accounts

# Use custom config location
gilt accounts --config /path/to/accounts.yml

# Use custom data directory
gilt accounts --data-dir /path/to/ledgers
```

**Options:**
- `--config PATH`: Path to accounts.yml (default: `config/accounts.yml`)
- `--data-dir PATH`: Directory containing ledger CSVs (default: `data/accounts`)

---

### `ingest` - Normalize Raw Bank CSVs

Convert raw bank CSV exports into standardized per-account ledger files. This command:
- Discovers CSV files in `ingest/` directory
- Maps them to accounts using patterns from `config/accounts.yml`
- Normalizes column names and formats to a standard schema
- Generates deterministic transaction IDs
- Links inter-account transfers automatically

```bash
# Dry-run (preview what would happen)
gilt ingest

# Actually write the normalized ledgers
gilt ingest --write

# Use custom paths
gilt ingest --config config/accounts.yml \
               --ingest-dir ingest \
               --output-dir data/accounts \
               --write
```

**Options:**
- `--config PATH`: Path to accounts.yml (default: `config/accounts.yml`)
- `--ingest-dir PATH`: Directory with raw bank CSVs (default: `ingest`)
- `--output-dir PATH`: Directory to write ledgers (default: `data/accounts`)
- `--write`: Persist changes (default: dry-run)

**Workflow:**
1. Export CSVs from your bank's website
2. Place them in `ingest/` directory
3. Run `gilt ingest` to preview
4. Run `gilt ingest --write` to process and save

**Transfer Linking:**
After ingestion, the tool automatically identifies transfers between your accounts (e.g., moving money from checking to credit card) and annotates both sides of the transfer with metadata.

---

### `ytd` - View Year-to-Date Transactions

Display transactions for a specific account in a rich formatted table.

```bash
# Show current year's transactions for MYBANK_CHQ
gilt ytd --account MYBANK_CHQ

# Show transactions for a specific year
gilt ytd --account MYBANK_CC --year 2024

# Limit to last 20 transactions
gilt ytd --account BANK2_BIZ --limit 20

# Specify default currency for legacy rows
gilt ytd --account MYBANK_CHQ --default-currency CAD
```

**Options:**
- `--account, -a ACCOUNT`: Account ID to display (required)
- `--year, -y YEAR`: Year to filter (default: current year)
- `--limit, -n N`: Maximum number of rows to show
- `--default-currency CURR`: Fallback currency for legacy rows (e.g., CAD)
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)

**Output:**
A rich formatted table showing:
- Transaction ID (first 8 characters)
- Date
- Description
- Amount (with currency)
- Category/Subcategory
- Notes

---

### `note` - Annotate Transactions

Attach or update notes on one or more transactions. Supports both single-transaction and batch modes.

#### Single Transaction Mode

Use `--txid` to target one specific transaction by its ID prefix (as shown in `ytd` output):

```bash
# Dry-run: preview the change
gilt note --account MYBANK_CHQ --txid a1b2c3d4 --note "Reimbursable expense"

# Write the note to disk
gilt note --account MYBANK_CHQ --txid a1b2c3d4 --note "Reimbursable expense" --write
```

#### Batch Mode

Use `--description`, `--desc-prefix`, or `--pattern` with optional `--amount` to target multiple recurring transactions:

```bash
# Match exact description
gilt note --account MYBANK_CC \
             --description "SPOTIFY" \
             --note "Music subscription" \
             --write

# Match by description prefix (case-insensitive)
gilt note --account MYBANK_CHQ \
             --desc-prefix "TRANSFER FROM" \
             --note "Inter-account transfer" \
             --write

# Match by regex pattern (case-insensitive)
gilt note --account MYBANK_CHQ \
             --pattern "Payment - WWW Payment - \d+ EXAMPLE UTILITY" \
             --note "Hydro bill" \
             --write

# Match description and specific amount
gilt note --account BANK2_BIZ \
             --description "Monthly Fee" \
             --amount -12.95 \
             --note "Account maintenance" \
             --write

# Batch mode with auto-confirm (skip prompts)
gilt note --account MYBANK_CC \
             --desc-prefix "AMAZON" \
             --note "Online purchases" \
             --yes \
             --write
```

**Options:**
- `--account, -a ACCOUNT`: Account ID containing the transaction (required)
- `--txid, -t ID`: Transaction ID prefix (single mode)
- `--description, -d TEXT`: Exact description match (batch mode)
- `--desc-prefix, -p TEXT`: Description prefix match, case-insensitive (batch mode)
- `--pattern TEXT`: Regex pattern to match description, case-insensitive (batch mode)
- `--amount, -m AMOUNT`: Exact amount match (batch mode, optional)
- `--note, -n TEXT`: Note text to set (required)
- `--yes, -y, -r`: Skip confirmations in batch mode
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)
- `--write`: Persist changes (default: dry-run)

---

## Budgeting & Categorization

The gilt tool includes powerful budgeting features for tracking and categorizing spending across all your accounts.

### `categories` - List Categories

Display all defined categories with usage statistics from your transactions.

```bash
# List all categories with usage counts and totals
gilt categories

# Use custom config location
gilt categories --config /path/to/categories.yml
```

**Options:**
- `--config PATH`: Path to categories.yml (default: `config/categories.yml`)
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)

**Output:**
Shows a table with:
- Category and subcategory names
- Descriptions
- Budget amounts (if set)
- Transaction count per category
- Total spending per category

---

### `category` - Manage Categories

Add, remove, or set budgets for categories.

```bash
# Add a new category
gilt category --add "Housing" --description "Housing and utilities" --write

# Add a subcategory
gilt category --add "Housing:Utilities" --description "Electric, gas, water" --write

# Set a budget
gilt category --set-budget "Dining Out" --amount 400 --period monthly --write

# Remove a category (requires confirmation if used)
gilt category --remove "Old Category" --write

# Force remove without confirmation
gilt category --remove "Housing:Utilities" --force --write
```

**Options:**
- `--add CATEGORY`: Add a new category (supports "Category:Subcategory" syntax)
- `--remove CATEGORY`: Remove a category
- `--set-budget CATEGORY`: Set budget amount for a category
- `--description TEXT`: Description for new category
- `--amount FLOAT`: Budget amount (required with --set-budget)
- `--period monthly|yearly`: Budget period (default: monthly)
- `--force`: Skip confirmations when removing used categories
- `--config PATH`: Path to categories.yml (default: `config/categories.yml`)
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)
- `--write`: Persist changes (default: dry-run)

---

### `categorize` - Categorize Transactions

Assign categories to one or many transactions.

#### Single Transaction Mode

```bash
# Categorize one transaction by ID
gilt categorize --account MYBANK_CHQ --txid a1b2c3d4 --category "Housing:Utilities" --write
```

#### Batch Mode

```bash
# Categorize all matching transactions by description prefix
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write

# Categorize exact description match
gilt categorize --account MYBANK_CC --description "Monthly Fee" --category "Banking:Fees" --write

# Categorize by regex pattern
gilt categorize --pattern "Payment.*EXAMPLE UTILITY" --category "Housing:Utilities" --yes --write

# Categorize across all accounts
gilt categorize --desc-prefix "AMAZON" --category "Shopping:Online" --yes --write

# With amount filter
gilt categorize --account MYBANK_CHQ --description "Service Fee" --amount -12.95 --category "Banking:Fees" --write
```

**Options:**
- `--account, -a ACCOUNT`: Account ID (omit to categorize across all accounts)
- `--txid, -t ID`: Transaction ID prefix (single mode)
- `--description, -d TEXT`: Exact description match (batch mode)
- `--desc-prefix, -p TEXT`: Description prefix match, case-insensitive (batch mode)
- `--pattern TEXT`: Regex pattern to match description, case-insensitive (batch mode)
- `--amount, -m AMOUNT`: Exact amount match (batch mode, optional)
- `--category, -c CATEGORY`: Category name (supports "Category:Subcategory" syntax)
- `--subcategory, -s SUBCAT`: Subcategory name (alternative to colon syntax)
- `--yes, -y`: Skip confirmations in batch mode
- `--config PATH`: Path to categories.yml (default: `config/categories.yml`)
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)
- `--write`: Persist changes (default: dry-run)

**Category Syntax:**
- `--category "Housing"` - Category only
- `--category "Housing:Utilities"` - Category with subcategory (shorthand)
- `--category "Housing" --subcategory "Utilities"` - Alternative syntax

---

### `auto-categorize` - Auto-Categorize Transactions with ML

Uses a machine learning classifier trained on your categorization history (from event store) to automatically categorize uncategorized transactions. Supports interactive review mode for approving predictions.

```bash
# Dry-run to see what would be auto-categorized
gilt auto-categorize

# Interactive mode - review and approve each prediction
gilt auto-categorize --interactive

# Apply auto-categorizations with default confidence threshold
gilt auto-categorize --write

# Use stricter confidence threshold (0.0-1.0, default 0.6)
gilt auto-categorize --confidence 0.8 --write

# Force retraining the model before predictions
gilt auto-categorize --retrain --write
```

**Options:**
- `--data-dir PATH`: Directory containing ledger files (default: `data/accounts`)
- `--confidence FLOAT`: Minimum confidence threshold (0.0-1.0, default: 0.6)
- `--interactive`: Review predictions interactively before applying
- `--retrain`: Force retraining the model from event store
- `--write`: Persist approved categorizations (default: dry-run)

**How it works:**
1. Loads the trained classifier (or trains from event store if `--retrain` specified)
2. Scans all ledger files for transactions without categories
3. Predicts categories based on description and amount patterns
4. In interactive mode, shows each prediction with confidence score and prompts for approval
5. With `--write`, persists approved categorizations to ledger files

**Interactive commands:**
- `a` - Approve prediction
- `r` - Reject prediction
- `m` - Modify category manually
- `q` - Quit and save approved categorizations

**Use case:**
After manually categorizing some transactions, train the classifier to automatically categorize new transactions. Review predictions interactively to ensure accuracy, then apply with `--write`.

---

### `recategorize` - Rename Categories in Ledgers

Rename a category across all ledger files. Useful when renaming categories in `categories.yml` to update existing transaction categorizations.

```bash
# Rename a category
gilt recategorize --from "Business" --to "Work" --write

# Rename a category with subcategory
gilt recategorize --from "Business:Subscriptions" --to "Work:Subscriptions" --write

# Preview changes without writing (dry-run)
gilt recategorize --from "Old Category" --to "New Category"
```

**Options:**
- `--from TEXT`: Original category name (supports "Category:Subcategory" syntax) (required)
- `--to TEXT`: New category name (supports "Category:Subcategory" syntax) (required)
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)
- `--write`: Persist changes (default: dry-run)

**How it works:**
1. Searches all ledger files for transactions with the specified category
2. Shows a preview table of all matching transactions
3. In dry-run mode (default), displays what would be changed
4. With `--write`, prompts for confirmation and updates all matching transactions

**Use case:**
When you rename a category in `config/categories.yml`, existing transactions in ledger files still reference the old category name. Use this command to bulk-update all historical transactions to use the new category name.

---

### `diagnose-categories` - Find Orphaned Categories

Diagnose category issues by finding categories used in transactions that aren't defined in `categories.yml`. Helps identify orphaned, misspelled, or forgotten categories.

```bash
# Check all ledgers for orphaned categories
gilt diagnose-categories

# Use custom config location
gilt diagnose-categories --config /path/to/categories.yml
```

**Options:**
- `--config PATH`: Path to categories.yml (default: `config/categories.yml`)
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)

**Output:**
- Exit code 0: All categories in transactions are defined in config (no issues)
- Exit code 1: Found orphaned categories (issues require attention)

Displays a table showing:
- Category and subcategory names found in transactions but not in config
- Transaction count for each orphaned category
- Suggested actions (add to config or fix typo)
- Similar category names if potential typos detected

**Use case:**
After categorizing many transactions, this command helps you discover:
- Categories that need to be added to `categories.yml`
- Typos in category names that should be fixed with `recategorize`
- Subcategories that exist in transactions but not in the parent category definition

**Example workflow:**
```bash
# 1. Run diagnostic
gilt diagnose-categories

# 2a. If legitimate category, add it to config
gilt category --add "NewCategory" --write

# 2b. If typo, fix all transactions
gilt recategorize --from "Transporation" --to "Transportation" --write

# 3. Re-run diagnostic to verify
gilt diagnose-categories
```

---

### `uncategorized` - Find Uncategorized Transactions

Display transactions that haven't been categorized yet.

```bash
# Show all uncategorized transactions
gilt uncategorized

# Filter by account
gilt uncategorized --account MYBANK_CHQ

# Filter by year
gilt uncategorized --year 2025

# Show only large transactions
gilt uncategorized --min-amount 100

# Limit results
gilt uncategorized --limit 50
```

**Options:**
- `--account, -a ACCOUNT`: Account ID to filter (omit for all accounts)
- `--year, -y YEAR`: Year to filter
- `--limit, -n N`: Max number of transactions to show
- `--min-amount AMOUNT`: Minimum absolute amount to include
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)

**Output:**
Transactions are sorted by description (to group similar ones), then date. This makes it easy to identify patterns and batch categorize recurring expenses.

---

### `budget` - Budget Reporting

View budget vs actual spending by category.

```bash
# Current year summary
gilt budget

# Specific year
gilt budget --year 2025

# Specific month
gilt budget --year 2025 --month 10

# Single category detail
gilt budget --category "Dining Out" --year 2025
```

**Options:**
- `--year, -y YEAR`: Year to report (default: current year)
- `--month, -m MONTH`: Month to report (1-12, requires --year)
- `--category, -c CATEGORY`: Filter to specific category
- `--config PATH`: Path to categories.yml (default: `config/categories.yml`)
- `--data-dir PATH`: Directory containing ledgers (default: `data/accounts`)

**Output:**
Shows a table with:
- Category and subcategory breakdowns
- Budgeted amount (automatically prorated for monthly/yearly reports)
- Actual spending
- Remaining budget (or over-budget amount in red)
- Percentage of budget used (color-coded: green < 90%, yellow 90-100%, red > 100%)

**Budget Proration:**
- Monthly reports use monthly budgets directly, or divide yearly budgets by 12
- Yearly reports use yearly budgets directly, or multiply monthly budgets by 12

---

### `backfill-events` - Migrate Existing Data to Event Store

Generate historical events from existing CSV ledgers and YAML configuration, enabling the full event-sourced architecture with complete audit trail.

```bash
# Preview migration (dry-run)
gilt backfill-events

# Execute migration with validation
gilt backfill-events --write

# Skip validation (faster, use with caution)
gilt backfill-events --write --no-validate

# Custom paths
gilt backfill-events \
  --data-dir custom/data \
  --categories-config custom/categories.yml \
  --event-store custom/events.db \
  --write
```

**Options:**
- `--data-dir PATH`: Ledger CSV directory (default: `data/accounts`)
- `--categories-config PATH`: Categories configuration (default: `config/categories.yml`)
- `--event-store PATH`: Event store database (default: `data/events.db`)
- `--projections-db PATH`: Transaction projections (default: `data/projections.db`)
- `--budget-projections-db PATH`: Budget projections (default: `data/budget_projections.db`)
- `--write`: Execute migration (default: dry-run)
- `--validate`: Validate projections after backfill (default: true)

**What it does:**
1. Generates `TransactionImported` and `TransactionCategorized` events from ledger CSVs
2. Generates `BudgetCreated` events from categories.yml
3. Infers import timestamps from source filenames
4. Validates that rebuilt projections match original data exactly
5. Provides detailed migration statistics

**Migration Statistics Example:**
```
TransactionImported events: 1016
TransactionCategorized events: 446
BudgetCreated events: 6
Total events: 1468

✓ Transaction count matches: 1016
✓ Budget count matches: 6
✓ Sample transaction validation passed
✓ All validations passed
```

**Use case:**
One-time migration to convert existing CSV/YAML data into the event-sourced architecture. Enables complete audit trail, time-travel queries, and ML-powered learning from user feedback.

---

### `rebuild-projections` - Rebuild Transaction Projections from Events

Rebuild the transaction projection database from the event store. Useful after event store corruption or to experiment with new projection logic.

```bash
# Rebuild from scratch
gilt rebuild-projections --from-scratch

# Incremental rebuild (only new events)
gilt rebuild-projections

# Custom paths
gilt rebuild-projections \
  --event-store custom/events.db \
  --projections-db custom/projections.db \
  --from-scratch
```

**Options:**
- `--event-store PATH`: Event store database (default: `data/events.db`)
- `--projections-db PATH`: Projections database (default: `data/projections.db`)
- `--from-scratch`: Full rebuild instead of incremental

**Use case:**
Recovery from projection database issues or testing new projection logic.

---

### `prompt-stats` - View ML Learning Statistics

Display statistics about the duplicate detection learning system, including accuracy metrics and description preferences learned from user feedback.

```bash
# Show learning statistics
gilt prompt-stats

# Use custom event store
gilt prompt-stats --event-store custom/events.db
```

**Options:**
- `--event-store PATH`: Event store database (default: `data/events.db`)

**Output:**
- Current prompt version and update count
- Accuracy metrics (TP/FP/TN/FN, precision, recall, F1 score)
- Description preference patterns
- Learned duplicate detection heuristics

**Use case:**
Monitor how well the duplicate detection system is learning from your feedback.

---

## Standard Ledger Schema

All normalized ledger files follow this schema (column order is fixed):

| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | string | Deterministic hash (first 16 chars of SHA-256) |
| `date` | date | Transaction date (YYYY-MM-DD) |
| `description` | string | Transaction description from bank |
| `amount` | float | Signed amount (debits negative, credits positive) |
| `currency` | string | Currency code (e.g., CAD, USD) |
| `account_id` | string | Account identifier (e.g., MYBANK_CHQ) |
| `counterparty` | string | Initially same as description; can be refined |
| `category` | string | Transaction category |
| `subcategory` | string | Transaction subcategory |
| `notes` | string | User-added notes |
| `source_file` | string | Original CSV filename |

Additional metadata (like transfer links) is stored in a JSON `metadata` field when present.

## Transaction IDs

Transaction IDs are **deterministic** and generated from:
```
SHA-256(account_id|date|amount|description)
```

The first 16 characters of the hex digest are used as the ID. This ensures:
- Same transaction always gets the same ID
- Idempotent ingestion (re-running won't create duplicates)
- Easy referencing in commands (8-char prefix is usually unique)

## Privacy & Security

- **No network access**: This tool never connects to the internet or external services. Even LLM inference runs locally via Ollama.
- **Local storage only**: All data remains on your machine in plain CSV files and SQLite databases.
- **No tracking**: No telemetry, analytics, or usage reporting.
- **You control the data**: Backup, encrypt, or delete your data as you see fit.
- **Privacy-preserving ML**: Duplicate detection uses local LLM models (via `mojentic` and Ollama) — your data never leaves your machine.

### Local LLM Setup (Optional)

For duplicate detection features, install Ollama and a compatible model:

```bash
# Install Ollama (see https://ollama.ai)
brew install ollama  # macOS

# Pull a recommended model
ollama pull qwen3:30b

# Verify it's working
ollama list
```

**Note**: Duplicate detection is optional. All core features work without LLM setup.

### Best Practices

- Keep `ingest/` directory private (do not commit to public repositories)
- Keep `data/accounts/` directory private
- Use `.gitignore` to exclude sensitive directories if version-controlling your workflow
- Consider encrypting your file system or using encrypted volumes for additional security

## Development

### Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=gilt --cov-report=term-missing
```

Tests are discovered automatically from `*_spec.py` files under `src/`.

**Test Statistics:**
- **196 tests** (all passing)
- Covers: Events, projections, CLI commands, services, duplicate detection, budgets
- Test pattern: BDD-style with `it_should_*` naming

### Linting

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Project Guidelines

For detailed development conventions, architecture decisions, and contribution guidelines, see the `.github/copilot-instructions.md` file and the event sourcing architecture documented in `EVENT_SOURCING.md`.

**Architecture Highlights:**
- **Event Sourcing**: Immutable audit log with materialized projections
- **11 Event Types**: Transaction imports, categorizations, duplicates, budgets, prompts
- **SQLite Storage**: Event store + projection databases
- **Local LLM**: Privacy-preserving duplicate detection via Ollama
- **Functional Core, Imperative Shell**: Pure business logic isolated from I/O

## Architecture Overview

Gilt uses an **event-sourced architecture** for transaction management:

```
CSV Exports → Events (Immutable) → Projections (Derived) → Views (Queries)
```

### Key Components

**Event Store** (`data/events.db`):
- Append-only log of all transaction and categorization events
- 11 event types: TransactionImported, TransactionCategorized, DuplicateSuggested, BudgetCreated, etc.
- Complete audit trail with timestamps

**Projections** (`data/projections.db`, `data/budget_projections.db`):
- Materialized views rebuilt from events
- Transaction ledgers with current state
- Budget tracking with time-travel capability
- Can be rebuilt at any time from events

**Learning System**:
- Captures user feedback on duplicate detection
- Adapts prompts based on decision patterns
- Tracks accuracy metrics (precision, recall, F1)
- All processing happens locally (privacy-first)

### Benefits

- **Auditability**: Every change is recorded with who/what/when
- **Time-travel**: Query historical state at any point
- **Flexibility**: Experiment with new categorization logic without data loss
- **Learning**: ML training from user decisions (local-only)
- **Recovery**: Rebuild projections if corrupted

## Common Workflows

### Initial Setup

1. Configure accounts in `config/accounts.yml`
2. Configure categories in `config/categories.yml`
3. Export CSVs from your banks
4. Place CSVs in `ingest/` directory
5. Run `gilt ingest --write`
6. Backfill events: `gilt backfill-events --write`
7. Verify with `gilt accounts` and `gilt ytd --account <ACCOUNT_ID>`

### Regular Updates

1. Download new transactions as CSV exports
2. Place new CSVs in `ingest/` directory (can overwrite old ones or use new filenames)
3. Run `gilt ingest --write`
4. Review recent transactions with `gilt ytd --account <ACCOUNT_ID> --limit 50`
5. Categorize new transactions (see below)

### Categorizing Transactions

#### Find What Needs Categorizing
```bash
# Show all uncategorized transactions
gilt uncategorized

# Filter by account
gilt uncategorized --account MYBANK_CHQ

# Show only large amounts
gilt uncategorized --min-amount 100
```

#### Categorize in Batch
```bash
# Recurring subscriptions
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
gilt categorize --desc-prefix "NETFLIX" --category "Entertainment:Streaming" --yes --write

# Utilities
gilt categorize --pattern "Payment.*EXAMPLE UTILITY" --category "Housing:Utilities" --yes --write

# Banking fees
gilt categorize --description "Monthly Fee" --category "Banking:Fees" --write

# Transit
gilt categorize --desc-prefix "PRESTO" --category "Transportation:Transit" --yes --write
```

#### Auto-Categorize with ML (After Manual Training)
```bash
# 1. First, manually categorize some transactions to build training data
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
gilt categorize --desc-prefix "NETFLIX" --category "Entertainment:Streaming" --yes --write
# ... continue for various patterns

# 2. Preview what the ML classifier would auto-categorize
gilt auto-categorize

# 3. Review predictions interactively
gilt auto-categorize --interactive
# (Approve, reject, or modify each prediction)

# 4. Apply approved auto-categorizations
gilt auto-categorize --write

# 5. Use stricter confidence threshold for higher precision
gilt auto-categorize --confidence 0.8 --write
```

**Tip**: Combine manual batch categorization for clear patterns (subscriptions, utilities) with auto-categorization for transactions that need contextual understanding.

#### Categorize Individual Transactions
```bash
# 1. View transactions
gilt ytd --account MYBANK_CHQ --limit 50

# 2. Note transaction ID (first 8 chars)
# 3. Categorize
gilt categorize --account MYBANK_CHQ --txid a1b2c3d4 --category "Housing:Rent" --write
```

### Annotating Transactions

#### Single Transaction Notes
```bash
# View transactions
gilt ytd --account <ACCOUNT_ID>

# Add note using transaction ID
gilt note --account <ACCOUNT_ID> --txid <TXID> --note "Your note" --write
```

#### Batch Annotation for Recurring Expenses
```bash
# Add notes to all Spotify charges
gilt note --account MYBANK_CC --desc-prefix "SPOTIFY" --note "Music subscription" --yes --write

# Mark all gym membership fees
gilt note --account MYBANK_CHQ --description "GoodLife Fitness" --note "Gym membership" --yes --write

# Annotate transfer payments
gilt note --account MYBANK_CHQ --desc-prefix "TRANSFER FROM" --note "Inter-account transfer" --yes --write
```

### Monthly Budget Review

1. **Import new transactions**
   ```bash
   gilt ingest --write
   ```

2. **Check categorization status**
   ```bash
   # How many need categorization?
   gilt uncategorized | head
   ```

3. **Categorize uncategorized spending**
   ```bash
   # Focus on larger amounts first
   gilt uncategorized --min-amount 50

   # Categorize patterns
   gilt categorize --desc-prefix "AMAZON" --category "Shopping:Online" --yes --write
   ```

4. **View budget status**
   ```bash
   # Current month
   gilt budget --year 2025 --month 11

   # Specific category detail
   gilt budget --category "Dining Out" --year 2025 --month 11
   ```

5. **Generate monthly report (optional)**
   ```bash
   # Create markdown report
   gilt budget --year 2025 --month 11 > reports/budget_2025_11.md
   ```

6. **Review over-budget categories**
   - Look for red indicators in budget output
   - Check if over-budget is recurring pattern
   - Adjust spending or increase budget as needed

7. **Add notes to significant transactions**
   ```bash
   gilt note --account MYBANK_CHQ --txid <large-txid> --note "Reason for expense" --write
   ```

### Setting Up Budget Tracking

1. **Review existing categories**
   ```bash
   gilt categories
   ```

2. **Add custom categories if needed**
   ```bash
   gilt category --add "Custom Category" --description "Category description" --write
   gilt category --add "Custom:Subcategory" --description "Subcategory description" --write
   ```

3. **Set budgets for each category**
   ```bash
   gilt category --set-budget "Dining Out" --amount 400 --period monthly --write
   gilt category --set-budget "Groceries" --amount 600 --period monthly --write
   gilt category --set-budget "Entertainment" --amount 200 --period monthly --write
   ```

4. **Categorize existing transactions** (see Categorizing Transactions above)

5. **Monitor spending**
   ```bash
   # Current month
   gilt budget

   # Year-to-date
   gilt budget --year 2025
   ```

### Duplicate Detection Workflow

Gilt provides two ways to handle duplicate transactions:

#### 1. Automatic Scanning (find duplicates you don't know about)

Use `gilt duplicates` to scan all transactions for potential duplicates:

```bash
# ML-based detection (fast, learns from feedback)
gilt duplicates

# Interactive mode - review each match
gilt duplicates --interactive

# High-confidence only
gilt duplicates -i --min-confidence 0.8

# Force LLM analysis (slower, no training needed)
gilt duplicates --llm --interactive
```

**What it detects:**
- Same account + same amount + within 1 day
- Different descriptions (bank variations)
- ML model trained from your previous feedback

#### 2. Manual Marking (when you spot a specific duplicate)

Use `gilt mark-duplicate` when you discover a duplicate in reports or listings:

```bash
# Preview marking a duplicate
gilt mark-duplicate --primary a1b2c3d4 --duplicate e5f6g7h8

# Confirm and persist (you'll choose which description to keep)
gilt mark-duplicate -p a1b2c3d4 -d e5f6g7h8 --write
```

**When to use this:**
- You found a duplicate while reviewing transactions
- Don't want to scan through 100 candidates
- Want to directly mark a specific pair

**View transaction IDs:**
```bash
gilt ytd --account MYBANK_CHQ --limit 50
```

**View learning statistics:**
```bash
gilt prompt-stats
```

### Category Management

#### Add New Categories
```bash
# Category with budget
gilt category --add "Housing" --description "Housing expenses" --write
gilt category --set-budget "Housing" --amount 2500 --period monthly --write

# Add subcategories
gilt category --add "Housing:Utilities" --description "Electric, gas, water" --write
gilt category --add "Housing:Rent" --description "Monthly rent" --write
```

#### Rename Categories
```bash
# Update category definition in config/categories.yml
# Then update all existing transactions:
gilt recategorize --from "Old Category" --to "New Category" --write
gilt recategorize --from "Business:Subscriptions" --to "Work:Subscriptions" --write
```

#### Diagnose Category Issues
```bash
# Find orphaned categories (used but not defined)
gilt diagnose-categories

# Add missing categories or fix typos based on output
gilt category --add "MissingCategory" --write
# or
gilt recategorize --from "Typo" --to "Correct" --write
```

#### Remove Unused Categories
```bash
# Safe removal (prompts if used)
gilt category --remove "Old Category" --write

# Force removal (skip confirmation)
gilt category --remove "Unused Category" --force --write
```

## Troubleshooting

### Command not found: `gilt`

Make sure you've activated your virtual environment and installed the package:
```bash
source .venv/bin/activate
pip install -e .
```

### Ingestion fails to match files

Check your `config/accounts.yml` and ensure `source_patterns` match your CSV filenames. You can use wildcards:
```yaml
source_patterns:
  - "*mybank*chequing*.csv"
  - "*MYBANK*CHQ*.csv"
```

### Transfer links not detected

The transfer linker uses specific parameters (date window, amount tolerance). If legitimate transfers aren't linked, you may need to review the parameters in `gilt/cli/command/ingest.py` and adjust `epsilon_direct`, `epsilon_interac`, or `window_days`.

### Encoding issues with CSV files

The tool expects UTF-8 encoded CSVs. If your bank exports in a different encoding, convert them first:
```bash
iconv -f ISO-8859-1 -t UTF-8 input.csv > output.csv
```

## License

This is a private, local-only tool. No license is provided for public distribution.

## Support

This tool is designed for personal use. For questions or issues, consult the project guidelines and source code documentation.
