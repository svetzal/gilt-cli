# Finance Local

A **local-only, privacy-first** command-line tool for managing personal finance data from multiple bank accounts.

## Core Principles

- **Local-only**: All processing happens on your machine. No network I/O, no cloud services.
- **Privacy-first**: Raw transaction data never leaves your machine. Only you have access to your financial records.
- **Deterministic**: Re-running commands with the same inputs produces identical results.
- **Safe by default**: All commands that modify files are dry-run by default. Use `--write` to persist changes.
- **Minimal dependencies**: Standard Python tooling with a small set of trusted libraries.

## Features

- **Normalize** raw bank CSV exports into a standardized format
- **Track** transactions across multiple accounts (checking, savings, credit cards, lines of credit)
- **Link** inter-account transfers automatically
- **Annotate** transactions with custom notes
- **View** year-to-date transactions in rich formatted tables

## Installation

### Prerequisites

- Python 3.13 or higher
- Virtual environment (recommended)

### Setup

1. Clone or navigate to the repository:
```bash
cd /path/to/finance
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
finance --help
```

## Directory Structure

```
finance/
├── config/
│   └── accounts.yml          # Account configuration (optional but recommended)
├── ingest/                   # Raw bank CSV exports (immutable inputs)
│   ├── 2025-10-13-rbc-chequing.csv
│   ├── 2025-10-13-rbc-mc.csv
│   └── ...
├── data/
│   └── accounts/             # Normalized per-account ledgers (outputs)
│       ├── RBC_CHQ.csv
│       ├── RBC_MC.csv
│       ├── SCOTIA_CURR.csv
│       └── SCOTIA_LOC.csv
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
  - account_id: RBC_CHQ
    description: "RBC Chequing Account"
    source_patterns:
      - "*rbc*chequing*.csv"
      - "*rbc*chq*.csv"
    import_hints:
      header_row: 0
      date_format: "%m/%d/%Y"

  - account_id: RBC_MC
    description: "RBC Mastercard"
    source_patterns:
      - "*rbc*mc*.csv"
      - "*rbc*mastercard*.csv"

  - account_id: SCOTIA_CURR
    description: "Scotiabank Current Account"
    source_patterns:
      - "*scotia*current*.csv"

  - account_id: SCOTIA_LOC
    description: "Scotiabank Line of Credit"
    source_patterns:
      - "*scotia*line*.csv"
      - "*scotia*loc*.csv"
```

## Commands

All commands are **local-only** and respect your privacy. Commands that modify files default to **dry-run mode**—use `--write` to persist changes.

### `accounts` - List Available Accounts

Display all configured accounts and their descriptions.

```bash
# List accounts from config
finance accounts

# Use custom config location
finance accounts --config /path/to/accounts.yml

# Use custom data directory
finance accounts --data-dir /path/to/ledgers
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
finance ingest

# Actually write the normalized ledgers
finance ingest --write

# Use custom paths
finance ingest --config config/accounts.yml \
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
3. Run `finance ingest` to preview
4. Run `finance ingest --write` to process and save

**Transfer Linking:**
After ingestion, the tool automatically identifies transfers between your accounts (e.g., moving money from checking to credit card) and annotates both sides of the transfer with metadata.

---

### `ytd` - View Year-to-Date Transactions

Display transactions for a specific account in a rich formatted table.

```bash
# Show current year's transactions for RBC_CHQ
finance ytd --account RBC_CHQ

# Show transactions for a specific year
finance ytd --account RBC_MC --year 2024

# Limit to last 20 transactions
finance ytd --account SCOTIA_CURR --limit 20

# Specify default currency for legacy rows
finance ytd --account RBC_CHQ --default-currency CAD
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
finance note --account RBC_CHQ --txid a1b2c3d4 --note "Reimbursable expense"

# Write the note to disk
finance note --account RBC_CHQ --txid a1b2c3d4 --note "Reimbursable expense" --write
```

#### Batch Mode

Use `--description`, `--desc-prefix`, or `--pattern` with optional `--amount` to target multiple recurring transactions:

```bash
# Match exact description
finance note --account RBC_MC \
             --description "SPOTIFY" \
             --note "Music subscription" \
             --write

# Match by description prefix (case-insensitive)
finance note --account RBC_CHQ \
             --desc-prefix "TRANSFER FROM" \
             --note "Inter-account transfer" \
             --write

# Match by regex pattern (case-insensitive)
finance note --account RBC_CHQ \
             --pattern "Payment - WWW Payment - \d+ HYDRO ONE" \
             --note "Hydro bill" \
             --write

# Match description and specific amount
finance note --account SCOTIA_CURR \
             --description "Monthly Fee" \
             --amount -12.95 \
             --note "Account maintenance" \
             --write

# Batch mode with auto-confirm (skip prompts)
finance note --account RBC_MC \
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

The finance tool includes powerful budgeting features for tracking and categorizing spending across all your accounts.

### `categories` - List Categories

Display all defined categories with usage statistics from your transactions.

```bash
# List all categories with usage counts and totals
finance categories

# Use custom config location
finance categories --config /path/to/categories.yml
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
finance category --add "Housing" --description "Housing and utilities" --write

# Add a subcategory
finance category --add "Housing:Utilities" --description "Electric, gas, water" --write

# Set a budget
finance category --set-budget "Dining Out" --amount 400 --period monthly --write

# Remove a category (requires confirmation if used)
finance category --remove "Old Category" --write

# Force remove without confirmation
finance category --remove "Housing:Utilities" --force --write
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
finance categorize --account RBC_CHQ --txid a1b2c3d4 --category "Housing:Utilities" --write
```

#### Batch Mode

```bash
# Categorize all matching transactions by description prefix
finance categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write

# Categorize exact description match
finance categorize --account RBC_MC --description "Monthly Fee" --category "Banking:Fees" --write

# Categorize by regex pattern
finance categorize --pattern "Payment.*HYDRO ONE" --category "Housing:Utilities" --yes --write

# Categorize across all accounts
finance categorize --desc-prefix "AMAZON" --category "Shopping:Online" --yes --write

# With amount filter
finance categorize --account RBC_CHQ --description "Service Fee" --amount -12.95 --category "Banking:Fees" --write
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

### `recategorize` - Rename Categories in Ledgers

Rename a category across all ledger files. Useful when renaming categories in `categories.yml` to update existing transaction categorizations.

```bash
# Rename a category
finance recategorize --from "Business" --to "Mojility" --write

# Rename a category with subcategory
finance recategorize --from "Business:Subscriptions" --to "Mojility:Subscriptions" --write

# Preview changes without writing (dry-run)
finance recategorize --from "Old Category" --to "New Category"
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
finance diagnose-categories

# Use custom config location
finance diagnose-categories --config /path/to/categories.yml
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
finance diagnose-categories

# 2a. If legitimate category, add it to config
finance category --add "NewCategory" --write

# 2b. If typo, fix all transactions
finance recategorize --from "Transporation" --to "Transportation" --write

# 3. Re-run diagnostic to verify
finance diagnose-categories
```

---

### `uncategorized` - Find Uncategorized Transactions

Display transactions that haven't been categorized yet.

```bash
# Show all uncategorized transactions
finance uncategorized

# Filter by account
finance uncategorized --account RBC_CHQ

# Filter by year
finance uncategorized --year 2025

# Show only large transactions
finance uncategorized --min-amount 100

# Limit results
finance uncategorized --limit 50
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
finance budget

# Specific year
finance budget --year 2025

# Specific month
finance budget --year 2025 --month 10

# Single category detail
finance budget --category "Dining Out" --year 2025
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

## Standard Ledger Schema

All normalized ledger files follow this schema (column order is fixed):

| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | string | Deterministic hash (first 16 chars of SHA-256) |
| `date` | date | Transaction date (YYYY-MM-DD) |
| `description` | string | Transaction description from bank |
| `amount` | float | Signed amount (debits negative, credits positive) |
| `currency` | string | Currency code (e.g., CAD, USD) |
| `account_id` | string | Account identifier (e.g., RBC_CHQ) |
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

- **No network access**: This tool never connects to the internet or external services.
- **Local storage only**: All data remains on your machine in plain CSV files.
- **No tracking**: No telemetry, analytics, or usage reporting.
- **You control the data**: Backup, encrypt, or delete your data as you see fit.

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
```

Tests are discovered automatically from `*_spec.py` files under `src/`.

### Linting

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Project Guidelines

For detailed development conventions, architecture decisions, and contribution guidelines, see `PATTERNS.md` (for code patterns) and the guidelines document referenced in the repository.

## Common Workflows

### Initial Setup

1. Configure accounts in `config/accounts.yml`
2. Export CSVs from your banks
3. Place CSVs in `ingest/` directory
4. Run `finance ingest --write`
5. Verify with `finance accounts` and `finance ytd --account <ACCOUNT_ID>`

### Regular Updates

1. Download new transactions as CSV exports
2. Place new CSVs in `ingest/` directory (can overwrite old ones or use new filenames)
3. Run `finance ingest --write`
4. Review recent transactions with `finance ytd --account <ACCOUNT_ID> --limit 50`

### Annotating Transactions

1. View transactions: `finance ytd --account <ACCOUNT_ID>`
2. Note the transaction ID (first 8 chars)
3. Add note: `finance note --account <ACCOUNT_ID> --txid <TXID> --note "Your note" --write`

### Batch Annotation for Recurring Expenses

```bash
# Add notes to all Spotify charges
finance note --account RBC_MC --desc-prefix "SPOTIFY" --note "Music subscription" --yes --write

# Mark all gym membership fees
finance note --account RBC_CHQ --description "GoodLife Fitness" --note "Gym membership" --yes --write
```

### Setting Up Budget Tracking

1. Define categories in `config/categories.yml` (or use the provided defaults)
2. Review categories: `finance categories`
3. Add custom categories if needed: `finance category --add "Custom Category" --description "..." --write`
4. Set budgets: `finance category --set-budget "Dining Out" --amount 400 --period monthly --write`

### Categorizing Transactions

1. Find uncategorized transactions: `finance uncategorized`
2. Categorize recurring expenses in batch:
   ```bash
   finance categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
   finance categorize --desc-prefix "UBER" --category "Transportation" --yes --write
   ```
3. Categorize individual transactions:
   ```bash
   finance categorize --account RBC_CHQ --txid a1b2c3d4 --category "Housing:Rent" --write
   ```
4. Check progress: `finance uncategorized` (should show fewer transactions)

### Monthly Budget Review

1. View current month's spending:
   ```bash
   finance budget --year 2025 --month 10
   ```
2. Check which categories are over budget
3. Review large uncategorized expenses:
   ```bash
   finance uncategorized --min-amount 100 --year 2025
   ```
4. Categorize any remaining transactions
5. Re-run budget report to see updated totals

## Troubleshooting

### Command not found: `finance`

Make sure you've activated your virtual environment and installed the package:
```bash
source .venv/bin/activate
pip install -e .
```

### Ingestion fails to match files

Check your `config/accounts.yml` and ensure `source_patterns` match your CSV filenames. You can use wildcards:
```yaml
source_patterns:
  - "*rbc*chequing*.csv"
  - "*RBC*CHQ*.csv"
```

### Transfer links not detected

The transfer linker uses specific parameters (date window, amount tolerance). If legitimate transfers aren't linked, you may need to review the parameters in `finance/cli/command/ingest.py` and adjust `epsilon_direct`, `epsilon_interac`, or `window_days`.

### Encoding issues with CSV files

The tool expects UTF-8 encoded CSVs. If your bank exports in a different encoding, convert them first:
```bash
iconv -f ISO-8859-1 -t UTF-8 input.csv > output.csv
```

## License

This is a private, local-only tool. No license is provided for public distribution.

## Support

This tool is designed for personal use. For questions or issues, consult the project guidelines and source code documentation.
