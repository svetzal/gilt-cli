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
def note(
    account: str = typer.Option(..., "--account", "-a", help=HELP_ACCOUNT_WITH_TX),
    txid: str = typer.Option(..., "--txid", "-t", help="Transaction ID prefix (TxnID8 as shown in tables)"),
    note: str = typer.Option(..., "--note", "-n", help="Note text to set on the transaction"),
    data_dir: Path = typer.Option(DEFAULT_DATA_DIR, "--data-dir", help=HELP_LEDGER_DIR),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Attach or update a note on a specific transaction in the account ledger.

    Safety: dry-run by default. Use --write to persist changes.
    """
    from finance.cli.command import note as cmd_note

    code = cmd_note.run(
        account=account,
        txid=txid,
        note_text=note,
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
