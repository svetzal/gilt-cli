# User Guide

Welcome to the Gilt User Guide. This section helps you use Gilt effectively for managing your personal finances.

## What is Gilt?

Gilt is a **local-only, privacy-first** financial management tool that helps you:

- Import and normalize transactions from multiple bank accounts
- Categorize and annotate your spending
- Track budgets and monitor spending against goals
- Generate reports and insights
- All while keeping your data completely private on your own machine

## Two Ways to Use Gilt

### Command Line Interface (CLI)

The CLI provides powerful, scriptable commands perfect for:

- Automation and batch processing
- Quick terminal workflows
- Server or headless environments
- Advanced power users

[Learn about the CLI →](cli/index.md)

### Graphical User Interface (GUI)

The GUI offers a modern, visual interface ideal for:

- Interactive exploration of transactions
- Visual budget tracking with charts
- Drag-and-drop workflows
- Users who prefer graphical tools

[Learn about the GUI →](gui/index.md)

!!! tip "Use Both"
    The CLI and GUI work with the same data files and can be used interchangeably. Many users use the CLI for imports and the GUI for analysis.

## Key Concepts

### Accounts

Accounts represent your financial institutions:

- Checking accounts
- Savings accounts
- Credit cards
- Lines of credit

Each account has:
- A unique ID (e.g., `MYBANK_CHQ`)
- A description
- Source patterns for matching CSV files

### Transactions

Transactions are individual financial events with:

- Date and amount
- Description from the bank
- Category and subcategory
- Optional notes
- Automatic transfer linking

### Categories

Categories organize your spending:

- Hierarchical structure (category → subcategories)
- Optional budgets (monthly or yearly)
- Descriptions for clarity
- Usage tracking

### Budgets

Budgets help you track spending:

- Set amount per category
- Monthly or yearly periods
- Automatic prorating
- Visual indicators (green/yellow/red)

## Common Workflows

### Initial Setup

1. [Install Gilt](installation.md)
2. Configure accounts and categories
3. Import your first bank CSV files
4. Verify data loaded correctly

[Detailed setup guide →](workflows/initial-setup.md)

### Monthly Review

1. Import new transactions
2. Categorize uncategorized spending
3. Review budget status
4. Add notes to significant transactions
5. Generate monthly report

[Monthly review workflow →](workflows/monthly-review.md)

### Budget Tracking

1. Define spending categories
2. Set budgets for each category
3. Categorize all transactions
4. Monitor budget vs actual
5. Adjust spending or budgets as needed

[Budget tracking workflow →](workflows/budget-tracking.md)

## Privacy & Safety

Gilt is designed with privacy as a core principle:

### Privacy Features

- ✅ **No network access**: Never connects to internet
- ✅ **Local storage**: All data in CSV files on your machine
- ✅ **No telemetry**: Zero tracking or analytics
- ✅ **You own the data**: Full control to backup, encrypt, or delete

### Safety Features

- ✅ **Dry-run default**: Preview changes before writing
- ✅ **Explicit confirmation**: `--write` flag required for changes
- ✅ **Preview dialogs**: See exactly what will change (GUI)
- ✅ **Duplicate detection**: Automatic prevention of double-imports
- ✅ **Deterministic IDs**: Same input always produces same output

### Best Practices

!!! warning "Keep Data Private"
    - Never commit `ingest/` or `data/` to public repositories
    - Use `.gitignore` to exclude sensitive directories
    - Consider full-disk encryption
    - Be careful when sharing screen recordings or screenshots

## Getting Help

### Documentation

- **[CLI Guide](cli/index.md)**: Command-line reference and examples
- **[GUI Guide](gui/index.md)**: Graphical interface walkthrough
- **[Workflows](workflows/initial-setup.md)**: Step-by-step common tasks

### Troubleshooting

Common issues and solutions:

- [Installation problems](installation.md#troubleshooting)
- [Import errors](cli/importing.md#troubleshooting)
- [Category issues](cli/categorization.md#troubleshooting)

### Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/svetzal/gilt-cli/issues)
- **Documentation**: This site covers most use cases
- **Code**: Explore the source for advanced usage

## What's Next?

New to Gilt? Start here:

1. [Install Gilt](installation.md)
2. [CLI Overview](cli/index.md) or [GUI Overview](gui/index.md)
3. [Initial Setup Workflow](workflows/initial-setup.md)

Already set up? Jump to:

- [Categorization Guide](cli/categorization.md)
- [Budget Tracking Guide](cli/budgeting.md)
- [Monthly Review Workflow](workflows/monthly-review.md)
