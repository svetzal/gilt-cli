"""Events-domain CLI commands: rebuild-projections, backfill-events, migrate-to-events."""

from __future__ import annotations

from pathlib import Path

import typer

from gilt.cli.registration._dispatch import command_kwargs, dispatch
from gilt.cli.registration._options import (
    budget_projections_db_option,
    event_store_option,
    force_option,
    projections_db_option,
    write_option,
)


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register event-sourcing commands on *app*."""

    @app.command(name="rebuild-projections")
    def build_projections(
        ctx: typer.Context,
        from_scratch: bool = typer.Option(
            False,
            "--from-scratch",
            help="Delete existing projections and rebuild from all events",
        ),
        incremental: bool = typer.Option(
            False,
            "--incremental",
            help="Only apply new events since last rebuild (default behavior)",
        ),
        events_db: Path | None = typer.Option(
            None, "--events-db", help="Path to events database (advanced override)"
        ),
        projections_db: Path | None = projections_db_option(
            "Path to projections database (advanced override)"
        ),
    ):
        """Rebuild transaction projections from event store.

        By default, applies only new events since last rebuild (incremental mode).
        Use --from-scratch to rebuild everything from all events.

        Examples:
          gilt rebuild-projections
          gilt rebuild-projections --from-scratch
          gilt rebuild-projections --events-db custom/events.db
        """
        from gilt.cli.command import rebuild_projections as cmd_rebuild_projections

        # events_db/projections_db are Path options: ctx.params holds the raw string typer
        # parsed them from, not the Path typer's own argument-binding converts them to, so
        # they're passed explicitly here (already-converted local variables) rather than
        # left to flow through from ctx.params.
        dispatch(
            cmd_rebuild_projections.run,
            **command_kwargs(
                ctx,
                workspace=ws_fn(ctx),
                events_db=events_db,
                projections_db=projections_db,
            ),
        )

    @app.command(name="backfill-events")
    def backfill_events(
        ctx: typer.Context,
        events_db: Path | None = event_store_option(),
        projections_db: Path | None = projections_db_option(
            "Path to transaction projections database (advanced override)",
        ),
        budget_projections_db: Path | None = budget_projections_db_option(),
        write: bool = write_option("Actually write events (default: dry-run)"),
    ):
        """Backfill events from existing data (advanced/debugging).

        Most users should use 'gilt migrate-to-events --write' instead.

        Examples:
          gilt backfill-events
          gilt backfill-events --write

        Safety: dry-run by default. Use --write to persist events.
        """
        from gilt.cli.command import backfill_events as cmd_backfill_events

        # Path options (events_db/projections_db/budget_projections_db) are passed as
        # extras (already-converted local variables) — see comment in rebuild-projections.
        dispatch(
            cmd_backfill_events.run,
            **command_kwargs(
                ctx,
                drop={"events_db", "projections_db", "budget_projections_db", "write"},
                event_store_path=events_db,
                projections_db_path=projections_db,
                budget_projections_db_path=budget_projections_db,
                dry_run=not write,
                workspace=ws_fn(ctx),
            ),
        )

    @app.command(name="migrate-to-events")
    def migrate_to_events(
        ctx: typer.Context,
        events_db: Path | None = event_store_option(),
        projections_db: Path | None = projections_db_option(
            "Path to transaction projections database (advanced override)",
        ),
        budget_projections_db: Path | None = budget_projections_db_option(),
        write: bool = write_option("Actually perform migration (default: dry-run)"),
        force: bool = force_option("Overwrite existing event store"),
    ):
        """One-command migration to event sourcing (recommended for upgrades).

        This command automates the complete migration process:
        1. Validates you have CSV data to migrate
        2. Creates event store from your existing data
        3. Builds transaction and budget projections
        4. Validates everything matches original data

        Examples:
          gilt migrate-to-events
          gilt migrate-to-events --write
          gilt migrate-to-events --write --force

        Safety: dry-run by default. Use --write to perform migration.
        """
        from gilt.cli.command import migrate_to_events as cmd_migrate_to_events

        # Path options (events_db/projections_db/budget_projections_db) are passed as
        # extras (already-converted local variables) — see comment in rebuild-projections.
        dispatch(
            cmd_migrate_to_events.run,
            **command_kwargs(
                ctx,
                drop={"events_db", "projections_db", "budget_projections_db"},
                event_store_path=events_db,
                projections_db_path=projections_db,
                budget_projections_db_path=budget_projections_db,
                workspace=ws_fn(ctx),
            ),
        )
