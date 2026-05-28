# Command Line Interface (CLI)

The Gilt CLI provides powerful, scriptable commands for managing your financial data.

## Overview

The CLI is designed for:

- **Automation**: Script repetitive tasks
- **Batch operations**: Process multiple transactions at once
- **Server environments**: Works without GUI
- **Power users**: Fast, keyboard-driven workflow

All commands follow the pattern: `gilt <command> [options]`

## Core Principles

### Dry-Run by Default

All commands that modify data default to **dry-run mode**:

```bash
# Preview what would happen (safe)
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment"

# Actually make the change (requires --write)
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment" --write
```

!!! tip "Always Preview First"
    Run commands without `--write` first to see what will happen. Only add `--write` after reviewing the preview.

### Explicit Write Flag

The `--write` flag is required for all mutation operations:

- `ingest --write` - Write normalized ledgers
- `note --write` - Save notes
- `categorize --write` - Save categories
- `category --write` - Save category config
- `recategorize --write` - Update categories

### Rich Output

Commands use Rich formatting for readable output:

- Tables for structured data
- Color coding (red=negative, green=positive)
- Progress indicators
- Clear error messages

## Command Categories

### Account Management

- [`accounts`](accounts.md) - List configured accounts

### Data Import

- [`ingest`](importing.md) - Import and normalize bank CSV files

### Transaction Viewing

- [`ytd`](viewing.md#viewing-transactions) - View year-to-date transactions
- [`show`](viewing.md#inspecting-a-transaction) - Inspect all fields of a single transaction
- [`history`](viewing.md#categorization-history) - Look up how similar transactions were categorized
- [`uncategorized`](categorization.md#finding-uncategorized) - Find transactions without categories
- [`status`](#status-dashboard) - Per-account freshness and coverage dashboard
- [`receipts`](#receipt-coverage-report) - Receipt attachment coverage by category or account

### Categorization

- [`categories`](categorization.md#listing-categories) - List all categories
- [`category`](categorization.md#managing-categories) - Add/remove/manage categories
- [`categorize`](categorization.md#categorizing-transactions) - Assign categories to transactions
- [`recategorize`](categorization.md#renaming-categories) - Rename categories or recategorize a filtered selection
- [`diagnose-categories`](categorization.md#diagnosing-issues) - Find orphaned categories

### Budgeting

- [`budget`](budgeting.md#budget-reports) - View budget vs actual spending

### Notes

- [`note`](viewing.md#adding-notes) - Add/edit transaction notes

## Common Patterns

### Preview → Write Workflow

Always preview before writing:

```bash
# 1. Preview
gilt categorize --desc-prefix "UTILITY CO" --category "Housing:Utilities"

# 2. Review output
# ... check that it looks correct ...

# 3. Write
gilt categorize --desc-prefix "UTILITY CO" --category "Housing:Utilities" --write
```

### Batch Operations

Process multiple transactions at once:

```bash
# Categorize all Spotify charges
gilt categorize --desc-prefix "SPOTIFY" \
  --category "Entertainment:Music" --yes --write

# Add notes to all gym payments (`--write` persists directly; no prompt)
gilt note --desc-prefix "GOODLIFE" \
  --note "Gym membership" --write
```

The `--yes` flag skips confirmation prompts for batch categorization
(use carefully). For `gilt note`, `--write` alone is sufficient — the command
no longer prompts interactively, and `--yes` is accepted as a no-op for
backwards compatibility.

### Filtering

Most commands support filtering:

```bash
# By account
gilt ytd --account MYBANK_CHQ

# By fiscal year (Nov 1 – Oct 31; accepts FY25, fy25, FY2025)
gilt uncategorized --fy FY25

# By calendar year
gilt uncategorized --year 2025

# By amount
gilt uncategorized --min-amount 100

# Combined
gilt ytd --account MYBANK_CHQ --year 2025 --limit 50
```

### Multi-Account Operations

Some commands work across all accounts:

```bash
# Categorize in all accounts
gilt categorize --desc-prefix "NETFLIX" \
  --category "Entertainment:Video" --yes --write

# Find uncategorized across all accounts (with per-account summary)
gilt uncategorized
gilt uncategorized --fy FY25   # fiscal year filter (Nov 1 – Oct 31)

# Budget across all accounts
gilt budget --year 2025 --month 10
```

## Status Dashboard

`gilt status` shows a per-account summary of data freshness and coverage at a glance.

```bash
# Show status for all accounts
gilt status

# Scope Mojility columns to a fiscal year
gilt status --fy FY25

# Raise the stale threshold to 30 days
gilt status --stale-threshold 30
```

Accounts whose latest transaction is older than `--stale-threshold` days (default 14) are
highlighted in red with a warning marker.

| Column | Description |
|--------|-------------|
| `account_id` | Account identifier (red + ⚠ when stale) |
| `latest_txn` | Date of most recent transaction |
| `days_since` | Days since latest transaction |
| `total_txns` | Total non-duplicate transactions |
| `uncategorized` | Transactions with no category assigned |
| `mojility_txns` | Mojility-category transactions (FY-filtered when `--fy` given) |
| `mojility_w_receipt` | Mojility transactions with a receipt attached |
| `mojility_receipt_pct` | Receipt coverage percentage (`—` when no Mojility transactions) |

## Receipt Coverage Report

`gilt receipts` reports which transactions have receipts attached and which are still missing one.
Defaults to the `Mojility` category, making it easy to identify business transactions that need
receipts before a bookkeeping cycle.

```bash
# Summary table grouped by subcategory (default)
gilt receipts

# Scope to a fiscal year
gilt receipts --fy FY25

# Group by account instead of subcategory
gilt receipts --by-account

# List individual transactions that are missing a receipt
gilt receipts --missing

# Report for a different category
gilt receipts --category "Work"

# Combine flags
gilt receipts --fy FY25 --missing --category "Work"
```

**Options:**

- `--fy FY`: Fiscal year filter (e.g. FY25, fy2025). Same format as `status` and `uncategorized`.
- `--by-account`: Group by `account_id` instead of `subcategory`.
- `--missing`: Switch from the summary table to a per-transaction list of those without a receipt.
- `--category, -c NAME`: Category to report on (default: `Mojility`).

**Default output (summary table):**

| Column | Description |
|--------|-------------|
| `category` | Category name (same for all rows) |
| `subcategory` / `account_id` | Grouping column (subcategory by default, account when `--by-account`) |
| `total_txns` | Total transactions in the group |
| `with_receipt` | Transactions with a receipt file attached |
| `without_receipt` | Transactions without a receipt |
| `coverage_pct` | Percentage with receipt (rounded to whole %) |
| `net_amount` | Signed sum of transaction amounts |

**`--missing` output:**

A flat table of transactions without receipts, showing: `txid`, `date`, `description`, `amount`,
`account_id`. Useful as input to a future bulk-attach workflow.

Read-only — no `--write` flag needed.

## Global Options

Available on all commands:

```bash
--data-dir PATH       # Directory containing ledger CSVs
                      # Default: data/accounts

--config PATH         # Path to accounts.yml or categories.yml
                      # Default: config/accounts.yml or config/categories.yml

--help                # Show command help
```

## Output Format

### Tables

Most commands output Rich tables:

```
┌──────────────┬────────────┬──────────────────┬──────────┐
│ Date         │ Account    │ Description      │ Amount   │
├──────────────┼────────────┼──────────────────┼──────────┤
│ 2025-11-16   │ MYBANK_CHQ    │ GROCERY STORE    │ -$45.67  │
│ 2025-11-15   │ MYBANK_CHQ    │ SALARY DEPOSIT   │ $3000.00 │
└──────────────┴────────────┴──────────────────┴──────────┘
```

### Color Coding

- **Red**: Negative amounts (expenses)
- **Green**: Positive amounts (income)
- **Yellow**: Warnings
- **Blue**: Information

### Progress Indicators

Long operations show progress:

```
Importing transactions... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
```

## Exit Codes

Commands return standard exit codes:

- `0` - Success
- `1` - Error (generic)
- `2` - Invalid arguments

Useful for scripting:

```bash
if gilt ingest --write; then
    echo "Import successful"
else
    echo "Import failed"
    exit 1
fi
```

## Environment Variables

None currently supported, but configuration can be customized via:

- `--data-dir` flag
- `--config` flag

## Shell Integration

### Bash/Zsh Completion

Tab completion for commands (if supported by your shell):

```bash
gilt cat<TAB>
# Completes to: gilt categorize
```

### Aliases

Create aliases for common commands:

```bash
# In ~/.bashrc or ~/.zshrc
alias fin='gilt'
alias fin-import='gilt ingest --write'
alias fin-budget='gilt budget --year 2025'
```

### Piping

Some commands support piping:

```bash
# Find large transactions
gilt ytd --account MYBANK_CHQ | grep -E '\$[0-9]{3,}'

# Export to CSV
gilt ytd --account MYBANK_CHQ --format csv > transactions.csv
```

## Troubleshooting

### Command Not Found

```bash
gilt: command not found
```

**Solution**: Activate virtual environment:
```bash
source .venv/bin/activate
```

### Permission Denied

```bash
PermissionError: [Errno 13] Permission denied: 'data/accounts/MYBANK_CHQ.csv'
```

**Solution**: Check file permissions:
```bash
chmod 644 data/accounts/*.csv
```

### Invalid Config

```bash
ValidationError: Invalid category configuration
```

**Solution**: Check YAML syntax in `config/categories.yml`:
```bash
# Validate YAML
python -c "import yaml; yaml.safe_load(open('config/categories.yml'))"
```

### Import Errors

```bash
Could not determine account for file: unknown.csv
```

**Solution**: Add source patterns to `config/accounts.yml`

## Next Steps

Explore individual command guides:

- [Account Management](accounts.md)
- [Importing Data](importing.md)
- [Categorization](categorization.md)
- [Budgeting](budgeting.md)
- [Viewing & Reporting](viewing.md)
