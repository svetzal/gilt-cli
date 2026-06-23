from __future__ import annotations

"""
Gilt CLI Wrapper (Typer + Rich)

Local-only, privacy-first CLI for managing personal financial data.

All paths are resolved from a single workspace root:
  --data-dir / GILT_DATA env var / current working directory
"""

from pathlib import Path

import typer

from gilt.workspace import Workspace

APP_HELP = "Gilt CLI (local-only)"
HELP_ACCOUNT_DISPLAY = "Account ID to display (e.g., MYBANK_CHQ)"
HELP_ACCOUNT_WITH_TX = "Account ID containing the transaction (e.g., MYBANK_CHQ)"

app = typer.Typer(no_args_is_help=True, add_completion=False, help=APP_HELP)


@app.callback()
def main(
    ctx: typer.Context,
    data_dir: Path | None = typer.Option(
        None,
        "--data-dir",
        envvar="GILT_DATA",
        help="Workspace root directory (default: current directory)",
    ),
):
    """Gilt CLI — all paths resolved from a single workspace root."""
    ctx.ensure_object(dict)
    ctx.obj["workspace"] = Workspace.resolve(data_dir)


def _ws(ctx: typer.Context) -> Workspace:
    return ctx.obj["workspace"]


# ---------------------------------------------------------------------------
# Per-domain command registration
# ---------------------------------------------------------------------------

from gilt.cli.registration import (  # noqa: E402
    categorization,
    duplicates,
    events,
    ingest,
    reporting,
    setup,
)

setup.register(app, _ws)
categorization.register(app, _ws)
ingest.register(app, _ws)
reporting.register(app, _ws)
duplicates.register(app, _ws)
events.register(app, _ws)


if __name__ == "__main__":
    app()  # pragma: no cover
