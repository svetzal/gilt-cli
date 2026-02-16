# Gilt - Privacy-First Financial Management

Welcome to **Gilt**, a local-only, privacy-first tool for managing your personal finances across multiple accounts.

## Core Principles

Gilt is built on four key principles:

- **Local-only**: All processing happens on your machine. No network I/O, no cloud services.
- **Privacy-first**: Raw transaction data never leaves your machine. Only you have access to your financial records.
- **Deterministic**: Re-running commands with the same inputs produces identical results.
- **Safe by default**: All commands that modify files are dry-run by default. Use `--write` to persist changes.

## Features

### Transaction Management
- **Normalize** raw bank CSV exports into a standardized format
- **Track** transactions across multiple accounts (checking, savings, credit cards, lines of credit)
- **Link** inter-account transfers automatically
- **Annotate** transactions with custom notes

### Budgeting & Categorization
- **Categorize** transactions with hierarchical categories
- **Track budgets** by category with monthly or yearly periods
- **Monitor spending** against budgets with visual indicators
- **Generate reports** to analyze spending patterns

### Dual Interface
- **Command Line Interface (CLI)**: Powerful, scriptable commands for advanced users
- **Graphical User Interface (GUI)**: Modern Qt6-based desktop application for visual interaction

## Quick Start

Get started with Gilt in minutes:

1. **Install**: Install Python 3.13+ and Gilt
2. **Configure**: Set up your accounts and categories
3. **Import**: Load your bank CSV exports
4. **Analyze**: View transactions, categorize spending, and track budgets

See the [Getting Started Guide](getting-started.md) for detailed instructions.

## Documentation Structure

### User Guide
Learn how to use Gilt for your daily financial management:

- [Installation](user/installation.md)
- [CLI Guide](user/cli/index.md) - Command-line interface reference
- [GUI Guide](user/gui/index.md) - Graphical interface guide
- [Workflows](user/workflows/initial-setup.md) - Common use cases and patterns

### Developer Guide
Understand the architecture and contribute to Gilt:

- [System Architecture](developer/architecture/system-design.md)
- [Technical Details](developer/technical/cli-implementation.md)
- [Development Setup](developer/development/setup.md)
- [Implementation History](developer/history/phase2-summary.md)

## Privacy & Security

Gilt takes your privacy seriously:

- ✅ **No network access**: This tool never connects to the internet or external services
- ✅ **Local storage only**: All data remains on your machine in plain CSV files
- ✅ **No tracking**: No telemetry, analytics, or usage reporting
- ✅ **You control the data**: Backup, encrypt, or delete your data as you see fit

!!! warning "Keep Your Data Private"
    - Keep `ingest/` and `data/` directories private
    - Use `.gitignore` to exclude sensitive directories from version control
    - Consider encrypting your file system or using encrypted volumes

## Community

- **Repository**: [github.com/svetzal/gilt-cli](https://github.com/svetzal/gilt-cli)
- **Issues**: Report bugs or request features on GitHub
- **License**: Private, personal use tool

## Next Steps

Ready to get started? Head over to the [Getting Started Guide](getting-started.md) to set up Gilt on your system.
