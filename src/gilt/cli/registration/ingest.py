"""Ingest-domain CLI commands: ingest, reingest, ingest-receipts, receipts."""

from __future__ import annotations

from pathlib import Path

import typer

HELP_WRITE = "Persist changes (default: dry-run)"


def register_ingest(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def ingest(
        ctx: typer.Context,
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
    ):
        """Ingest and normalize raw CSVs into standardized per-account ledgers.

        Safety: dry-run by default. Use --write to write outputs under data/accounts/.
        """
        from gilt.cli.command import ingest as cmd_ingest

        code = cmd_ingest.run(
            workspace=ws_fn(ctx),
            write=write,
        )
        raise typer.Exit(code=code)


def register_reingest(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def reingest(
        ctx: typer.Context,
        account: str = typer.Option(
            ..., "--account", "-a", help="Account ID to reingest (e.g., MYBANK_CC)"
        ),
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
    ):
        """Purge and re-ingest all transactions for a single account.

        Removes the account's ledger CSV, purges related events and projections,
        clears cached intelligence, then re-runs ingestion from the original
        source files. Use this after changing import_hints (e.g., amount_sign)
        or when an account's data needs a clean slate without affecting other accounts.

        Examples:
          gilt reingest --account MYBANK_CC
          gilt reingest -a MYBANK_CC --write

        Safety: dry-run by default. Use --write to execute.
        """
        from gilt.cli.command import reingest as cmd_reingest

        code = cmd_reingest.run(
            account=account,
            workspace=ws_fn(ctx),
            write=write,
        )
        raise typer.Exit(code=code)


def register_ingest_receipts(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="ingest-receipts")
    def ingest_receipts(
        ctx: typer.Context,
        source: Path = typer.Option(
            ...,
            "--source",
            help="Root directory containing receipt JSON files (recursive scan)",
        ),
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
        year: int | None = typer.Option(
            None, "--year", "-y", help="Only process receipts from this year"
        ),
        account: str | None = typer.Option(
            None, "--account", "-a", help="Limit matching to this account"
        ),
        interactive: bool = typer.Option(
            False, "--interactive", "-i", help="Interactively resolve ambiguous matches"
        ),
    ):
        """Ingest receipt JSON sidecar files and enrich matching bank transactions.

        Reads mailctl.receipt.v1 JSON files, matches them to existing bank transactions
        by amount and date, and creates TransactionEnriched events.

        Examples:
          gilt ingest-receipts --source ~/receipts
          gilt ingest-receipts --source ~/receipts --year 2025 --write
          gilt ingest-receipts --source ~/receipts --account MYBANK_CC --write
          gilt ingest-receipts --source ~/receipts --interactive --write

        Safety: dry-run by default. Use --write to persist enrichment events.
        """
        from gilt.cli.command import ingest_receipts as cmd_ingest_receipts

        code = cmd_ingest_receipts.run(
            workspace=ws_fn(ctx),
            source=source,
            write=write,
            year=year,
            account=account,
            interactive=interactive,
        )
        raise typer.Exit(code=code)


def register_receipts(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def receipts(
        ctx: typer.Context,
        by_account: bool = typer.Option(
            False,
            "--by-account",
            help="Group by account_id instead of subcategory",
        ),
        fy: str | None = typer.Option(
            None,
            "--fy",
            help="Fiscal year filter (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025.",
        ),
        missing: bool = typer.Option(
            False,
            "--missing",
            help="List individual transactions without receipts instead of the summary table",
        ),
        category: str = typer.Option(
            "Mojility",
            "--category",
            "-c",
            help="Category to report on (default: Mojility)",
        ),
    ):
        """Display receipt attachment coverage for categorised transactions.

        Shows total transactions, how many have receipts attached, and coverage
        percentage grouped by subcategory (default) or account.

        Examples:
          gilt receipts
          gilt receipts --fy FY25
          gilt receipts --by-account
          gilt receipts --missing
          gilt receipts --category Food
          gilt receipts --fy FY25 --missing
        """
        from gilt.cli.command import receipts as cmd_receipts
        from gilt.cli.command.util import console
        from gilt.util.fy import fiscal_year_range

        fy_range = None
        if fy is not None:
            try:
                fy_range = fiscal_year_range(fy)
            except ValueError as exc:
                console.print(f"[red]Error:[/] {exc}")
                raise typer.Exit(code=1) from exc

        code = cmd_receipts.run(
            category=category,
            by_account=by_account,
            fy_range=fy_range,
            fy_label=fy,
            missing=missing,
            workspace=ws_fn(ctx),
        )
        raise typer.Exit(code=code)


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register ingest commands on *app*."""
    register_ingest(app, ws_fn)
    register_reingest(app, ws_fn)
    register_ingest_receipts(app, ws_fn)
    register_receipts(app, ws_fn)
