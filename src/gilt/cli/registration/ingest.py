"""Ingest-domain CLI commands: ingest, reingest, ingest-receipts, receipts."""

from __future__ import annotations

from pathlib import Path

import typer

from gilt.cli.registration._dispatch import build_fy_range, command_kwargs, dispatch
from gilt.cli.registration._options import (
    account_option,
    category_option,
    fy_option,
    interactive_option,
    write_option,
    year_option,
)


def register_ingest(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def ingest(
        ctx: typer.Context,
        write: bool = write_option(),
    ):
        """Ingest and normalize raw CSVs into standardized per-account ledgers.

        Safety: dry-run by default. Use --write to write outputs under data/accounts/.
        """
        from gilt.cli.command import ingest as cmd_ingest

        dispatch(cmd_ingest.run, **command_kwargs(ctx, workspace=ws_fn(ctx)))


def register_reingest(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def reingest(
        ctx: typer.Context,
        account: str = account_option("Account ID to reingest (e.g., MYBANK_CC)", required=True),
        write: bool = write_option(),
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

        dispatch(cmd_reingest.run, **command_kwargs(ctx, workspace=ws_fn(ctx)))


def register_ingest_receipts(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="ingest-receipts")
    def ingest_receipts(
        ctx: typer.Context,
        source: Path = typer.Option(
            ...,
            "--source",
            help="Root directory containing receipt JSON files (recursive scan)",
        ),
        write: bool = write_option(),
        year: int | None = year_option("Only process receipts from this year"),
        account: str | None = account_option("Limit matching to this account"),
        interactive: bool = interactive_option("Interactively resolve ambiguous matches"),
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

        # source is a Path option: ctx.params holds the raw string typer parsed it from,
        # not the Path typer's own argument-binding converts it to, so it's passed
        # explicitly here (the already-converted local variable).
        dispatch(
            cmd_ingest_receipts.run,
            **command_kwargs(ctx, workspace=ws_fn(ctx), source=source),
        )


def register_receipts(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def receipts(
        ctx: typer.Context,
        by_account: bool = typer.Option(
            False,
            "--by-account",
            help="Group by account_id instead of subcategory",
        ),
        fy: str | None = fy_option(
            "Fiscal year filter (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025.",
        ),
        missing: bool = typer.Option(
            False,
            "--missing",
            help="List individual transactions without receipts instead of the summary table",
        ),
        category: str = category_option(
            "Category to report on (default: Mojility)", default="Mojility"
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

        dispatch(
            cmd_receipts.run,
            **command_kwargs(
                ctx,
                drop={"fy"},
                fy_range=build_fy_range(fy),
                fy_label=fy,
                workspace=ws_fn(ctx),
            ),
        )


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register ingest commands on *app*."""
    register_ingest(app, ws_fn)
    register_reingest(app, ws_fn)
    register_ingest_receipts(app, ws_fn)
    register_receipts(app, ws_fn)
