from __future__ import annotations

"""
Finance CLI Wrapper (Typer + Rich)

Local-only, privacy-first CLI for interacting with per-account ledgers under data/accounts/.

Command implemented:
- ytd: Show year-to-date transactions for a single account as a friendly Rich table.

This CLI performs only local file reads and prints to the console. It does not
send data anywhere. Defaults follow the repo conventions described in guidelines.
"""

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import typer

# Common defaults and help texts to avoid duplicated string literals
DEFAULT_DATA_DIR = Path("data/accounts")
DEFAULT_INGEST_DIR = Path("ingest")
DEFAULT_CONFIG_PATH = Path("config/accounts.yml")

HELP_LEDGER_DIR = "Directory containing ledger CSVs"
HELP_WRITE = "Persist changes (default: dry-run)"

APP_HELP = "Finance CLI (local-only)"
HELP_ACCOUNT_DISPLAY = "Account ID to display (e.g., RBC_CHQ)"
HELP_ACCOUNT_WITH_TX = "Account ID containing the transaction (e.g., RBC_CHQ)"

app = typer.Typer(no_args_is_help=True, add_completion=False, help=APP_HELP)




@app.command()
def accounts(
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config", help="Accounts config YAML path"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
):
    """List available accounts (IDs and descriptions)."""
    from finance.cli.command import accounts as cmd_accounts

    code = cmd_accounts.run(
        config=config,
        data_dir=data_dir,
    )
    raise typer.Exit(code=code)


@app.command()
def categories(
    config: Path = typer.Option(Path("config/categories.yml"), "--config", help="Categories config YAML path"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
):
    """List all defined categories with usage statistics."""
    from finance.cli.command import categories as cmd_categories

    code = cmd_categories.run(
        config=config,
        data_dir=data_dir,
    )
    raise typer.Exit(code=code)


@app.command()
def category(
    add: Optional[str] = typer.Option(None, "--add", help="Add a new category (supports 'Category:Subcategory')"),
    remove: Optional[str] = typer.Option(None, "--remove", help="Remove a category"),
    set_budget: Optional[str] = typer.Option(None, "--set-budget", help="Set budget for a category"),
    description: Optional[str] = typer.Option(None, "--description", help="Description for new category"),
    amount: Optional[float] = typer.Option(None, "--amount", help="Budget amount"),
    period: str = typer.Option("monthly", "--period", help="Budget period (monthly or yearly)"),
    force: bool = typer.Option(False, "--force", help="Skip confirmations when removing used categories"),
    config: Path = typer.Option(Path("config/categories.yml"), "--config", help="Categories config YAML path"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Manage categories: add, remove, or set budget.
    
    Examples:
      finance category --add "Housing" --description "Housing expenses" --write
      finance category --add "Housing:Utilities" --write
      finance category --set-budget "Dining Out" --amount 400 --write
      finance category --remove "Old Category" --write
    
    Safety: dry-run by default. Use --write to persist changes.
    """
    from finance.cli.command import category as cmd_category

    code = cmd_category.run(
        add=add,
        remove=remove,
        set_budget=set_budget,
        description=description,
        amount=amount,
        period=period,
        force=force,
        config=config,
        data_dir=data_dir,
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def ytd(
    account: str = typer.Option(..., "--account", "-a", help=HELP_ACCOUNT_DISPLAY),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to filter (defaults to current year)"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", min=1, help="Max number of rows to show (after sorting)"),
    default_currency: Optional[str] = typer.Option(None, "--default-currency", help="Fallback currency if missing in legacy rows (e.g., CAD)"),
):
    """Show year-to-date transactions for a single account as a Rich table."""
    from finance.cli.command import ytd as cmd_ytd

    code = cmd_ytd.run(
        account=account,
        year=year,
        data_dir=data_dir,
        limit=limit,
        default_currency=default_currency,
    )
    raise typer.Exit(code=code)


@app.command()
def categorize(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account ID (omit to categorize across all accounts)"),
    txid: Optional[str] = typer.Option(None, "--txid", "-t", help="Transaction ID prefix (single mode)"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Exact description to match (batch mode)"),
    desc_prefix: Optional[str] = typer.Option(None, "--desc-prefix", "-p", help="Description prefix to match (batch mode, case-insensitive)"),
    pattern: Optional[str] = typer.Option(None, "--pattern", help="Regex pattern to match description (batch mode, case-insensitive)"),
    amount: Optional[float] = typer.Option(None, "--amount", "-m", help="Exact amount to match (batch mode)"),
    category: str = typer.Option(..., "--category", "-c", help="Category name (supports 'Category:Subcategory' syntax)"),
    subcategory: Optional[str] = typer.Option(None, "--subcategory", "-s", help="Subcategory name (alternative to colon syntax)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Assume 'yes' for all confirmations in batch mode"),
    config: Path = typer.Option(Path("config/categories.yml"), "--config", help="Categories config YAML path"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Categorize transactions (single or batch mode).
    
    Modes:
    - Single: use --txid/-t to target one transaction
    - Batch: use --description/-d, --desc-prefix/-p, or --pattern to target multiple transactions
    
    Examples:
      finance categorize --account RBC_CHQ --txid a1b2c3d4 --category "Housing:Utilities" --write
      finance categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
      finance categorize --pattern "Payment.*HYDRO ONE" --category "Housing:Utilities" --yes --write
      finance categorize --account RBC_MC --description "Monthly Fee" --category "Banking:Fees" --write
    
    Safety: dry-run by default. Use --write to persist changes.
    """
    from finance.cli.command import categorize as cmd_categorize

    code = cmd_categorize.run(
        account=account,
        txid=txid,
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
        category=category,
        subcategory=subcategory,
        assume_yes=yes,
        config=config,
        data_dir=data_dir,
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def recategorize(
    from_cat: str = typer.Option(..., "--from", help="Original category name (supports 'Category:Subcategory')"),
    to_cat: str = typer.Option(..., "--to", help="New category name (supports 'Category:Subcategory')"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Rename a category across all ledger files.
    
    Useful when renaming categories in categories.yml to update existing
    transaction categorizations in ledger files.
    
    Examples:
      finance recategorize --from "Business" --to "Mojility" --write
      finance recategorize --from "Business:Meals" --to "Mojility:Meals" --write
    
    Safety: dry-run by default. Use --write to persist changes.
    """
    from finance.cli.command import recategorize as cmd_recategorize

    code = cmd_recategorize.run(
        from_category=from_cat,
        to_category=to_cat,
        data_dir=data_dir,
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def uncategorized(
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account ID to filter (omit for all accounts)"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to filter"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", min=1, help="Max number of transactions to show"),
    min_amount: Optional[float] = typer.Option(None, "--min-amount", help="Minimum absolute amount to include"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
):
    """Display transactions without categories.
    
    Shows uncategorized transactions sorted by description (for grouping similar ones), then date.
    Helps identify which transactions still need categorization.
    
    Examples:
      finance uncategorized
      finance uncategorized --account RBC_CHQ --year 2025
      finance uncategorized --min-amount 100 --limit 50
    """
    from finance.cli.command import uncategorized as cmd_uncategorized

    code = cmd_uncategorized.run(
        account=account,
        year=year,
        limit=limit,
        min_amount=min_amount,
        data_dir=data_dir,
    )
    raise typer.Exit(code=code)


@app.command()
def budget(
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to report (default: current year)"),
    month: Optional[int] = typer.Option(None, "--month", "-m", help="Month to report (1-12, requires --year)"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter to specific category"),
    config: Path = typer.Option(Path("config/categories.yml"), "--config", help="Categories config YAML path"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
):
    """Display budget summary comparing actual spending vs budgeted amounts.
    
    Shows spending by category with budget comparison when budgets are defined.
    Automatically prorates monthly/yearly budgets based on report period.
    
    Examples:
      finance budget                              # Current year
      finance budget --year 2025                  # Specific year
      finance budget --year 2025 --month 10       # Specific month
      finance budget --category "Dining Out"      # Single category detail
    """
    from finance.cli.command import budget as cmd_budget

    code = cmd_budget.run(
        year=year,
        month=month,
        category=category,
        config=config,
        data_dir=data_dir,
    )
    raise typer.Exit(code=code)


@app.command()
def diagnose_categories(
    config: Path = typer.Option(Path("config/categories.yml"), "--config", help="Categories config YAML path"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
):
    """Diagnose category issues by finding categories in transactions not in config.
    
    Scans all ledger files and reports any categories used in transactions that
    aren't defined in categories.yml. Helps identify orphaned, misspelled, or
    forgotten categories.
    
    Examples:
      finance diagnose-categories                     # Check all ledgers
      finance diagnose-categories --config custom.yml # Use custom config
    """
    from finance.cli.command import diagnose_categories as cmd_diagnose_categories

    code = cmd_diagnose_categories.run(
        config=config,
        data_dir=data_dir,
    )
    raise typer.Exit(code=code)


@app.command()
def report(
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to report (default: current year)"),
    month: Optional[int] = typer.Option(None, "--month", "-m", help="Month to report (1-12, requires --year)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path (without extension, default: reports/budget_report_YYYY[-MM])"),
    config: Path = typer.Option(Path("config/categories.yml"), "--config", help="Categories config YAML path"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Generate budget report as markdown and Word document (.docx).
    
    Creates a comprehensive budget report comparing actual spending vs budgeted amounts.
    Outputs both markdown (.md) and Word (.docx) formats using pandoc.
    
    Examples:
      finance report                              # Current year (dry-run)
      finance report --year 2025 --write          # Full year report
      finance report --year 2025 --month 10 --write  # Single month
      finance report --output custom/report --write  # Custom output path
    
    Safety: dry-run by default. Use --write to persist files.
    Note: Requires pandoc for .docx generation (brew install pandoc on macOS).
    """
    from finance.cli.command import report as cmd_report

    code = cmd_report.run(
        year=year,
        month=month,
        output=output,
        config=config,
        data_dir=data_dir,
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def note(
    account: str = typer.Option(..., "--account", "-a", help=HELP_ACCOUNT_WITH_TX),
    txid: Optional[str] = typer.Option(None, "--txid", "-t", help="Transaction ID prefix (TxnID8 as shown in tables)"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Exact description to match (batch mode)"),
    desc_prefix: Optional[str] = typer.Option(None, "--desc-prefix", "-p", help="Description prefix to match (batch mode, case-insensitive)"),
    pattern: Optional[str] = typer.Option(None, "--pattern", help="Regex pattern to match description (batch mode, case-insensitive)"),
    amount: Optional[float] = typer.Option(None, "--amount", "-m", help="Exact amount to match (batch mode)"),
    note: str = typer.Option(..., "--note", "-n", help="Note text to set on the transaction(s)"),
    yes: bool = typer.Option(False, "--yes", "-y", "-r", help="Assume 'yes' for all confirmations in batch mode"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Attach or update notes on transactions in the account ledger.

    Modes:
    - Single: use --txid/-t to target one transaction.
    - Batch: use --description/-d, --desc-prefix/-p, or --pattern (optionally with --amount/-m) to target recurring transactions.

    Safety: dry-run by default. Use --write to persist changes.
    """
    from finance.cli.command import note as cmd_note

    code = cmd_note.run(
        account=account,
        txid=txid,
        note_text=note,
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
        assume_yes=yes,
        data_dir=data_dir,
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def ingest(
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config", help="Accounts config YAML path"),
    ingest_dir: Path = typer.Option(DEFAULT_INGEST_DIR, "--ingest-dir", help="Directory with raw bank CSV files"),
    output_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--output-dir", help="Directory to write per-account ledgers"),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Ingest and normalize raw CSVs into standardized per-account ledgers.

    Safety: dry-run by default. Use --write to write outputs under data/accounts/.
    """
    from finance.cli.command import ingest as cmd_ingest

    code = cmd_ingest.run(
        config=config,
        ingest_dir=ingest_dir,
        output_dir=output_dir,
        write=write,
    )
    raise typer.Exit(code=code)


if __name__ == "__main__":
    app()  # pragma: no cover
