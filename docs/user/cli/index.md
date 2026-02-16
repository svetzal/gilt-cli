# Command Line Interface (CLI)

The Finance CLI provides powerful, scriptable commands for managing your financial data.

## Overview

The CLI is designed for:

- **Automation**: Script repetitive tasks
- **Batch operations**: Process multiple transactions at once
- **Server environments**: Works without GUI
- **Power users**: Fast, keyboard-driven workflow

All commands follow the pattern: `finance <command> [options]`

## Core Principles

### Dry-Run by Default

All commands that modify data default to **dry-run mode**:

```bash
# Preview what would happen (safe)
finance categorize --desc-prefix "SPOTIFY" --category "Entertainment"

# Actually make the change (requires --write)
finance categorize --desc-prefix "SPOTIFY" --category "Entertainment" --write
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
- [`uncategorized`](categorization.md#finding-uncategorized) - Find transactions without categories

### Categorization

- [`categories`](categorization.md#listing-categories) - List all categories
- [`category`](categorization.md#managing-categories) - Add/remove/manage categories
- [`categorize`](categorization.md#categorizing-transactions) - Assign categories to transactions
- [`recategorize`](categorization.md#renaming-categories) - Rename categories in ledgers
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
finance categorize --desc-prefix "UTILITY CO" --category "Housing:Utilities"

# 2. Review output
# ... check that it looks correct ...

# 3. Write
finance categorize --desc-prefix "UTILITY CO" --category "Housing:Utilities" --write
```

### Batch Operations

Process multiple transactions at once:

```bash
# Categorize all Spotify charges
finance categorize --desc-prefix "SPOTIFY" \
  --category "Entertainment:Music" --yes --write

# Add notes to all gym payments
finance note --desc-prefix "GOODLIFE" \
  --note "Gym membership" --yes --write
```

The `--yes` flag skips confirmation prompts (use carefully).

### Filtering

Most commands support filtering:

```bash
# By account
finance ytd --account MYBANK_CHQ

# By year
finance uncategorized --year 2025

# By amount
finance uncategorized --min-amount 100

# Combined
finance ytd --account MYBANK_CHQ --year 2025 --limit 50
```

### Multi-Account Operations

Some commands work across all accounts:

```bash
# Categorize in all accounts
finance categorize --desc-prefix "NETFLIX" \
  --category "Entertainment:Video" --yes --write

# Find uncategorized in all accounts
finance uncategorized

# Budget across all accounts
finance budget --year 2025 --month 10
```

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
if finance ingest --write; then
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
finance cat<TAB>
# Completes to: finance categorize
```

### Aliases

Create aliases for common commands:

```bash
# In ~/.bashrc or ~/.zshrc
alias fin='finance'
alias fin-import='finance ingest --write'
alias fin-budget='finance budget --year 2025'
```

### Piping

Some commands support piping:

```bash
# Find large transactions
finance ytd --account MYBANK_CHQ | grep -E '\$[0-9]{3,}'

# Export to CSV
finance ytd --account MYBANK_CHQ --format csv > transactions.csv
```

## Troubleshooting

### Command Not Found

```bash
finance: command not found
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
