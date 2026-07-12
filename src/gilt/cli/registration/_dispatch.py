"""Shared dispatch helpers for CLI command registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NoReturn

import typer

from gilt.cli.command._errors import CommandAbort
from gilt.model.errors import GiltDataError

HELP_WRITE = "Persist changes (default: dry-run)"


def dispatch(run: Callable[..., int], /, **kwargs: Any) -> NoReturn:
    """Single choke-point: invoke a command's run() and translate its exit code into typer.Exit.

    Cross-cutting concerns (logging, error middleware, exit-code translation) belong here,
    not in each wrapper.

    Raises:
        typer.Exit: Always — with the returned exit code, or code=1 on CommandAbort
            or GiltDataError.
    """
    try:
        code = run(**kwargs)
    except CommandAbort as exc:
        raise typer.Exit(code=exc.code) from exc
    except GiltDataError as exc:
        from gilt.cli.console import print_error

        print_error(str(exc))
        raise typer.Exit(code=1) from exc
    raise typer.Exit(code=code)


def build_fy_range(fy: str | None):
    """Parse a fiscal-year string into a (start, end) date range.

    Returns None when fy is None. Raises typer.Exit(code=1) on parse failure,
    printing a [red]Error:[/] message to the console.
    """
    if fy is None:
        return None
    from gilt.cli.console import console
    from gilt.util.fy import fiscal_year_range

    try:
        return fiscal_year_range(fy)
    except ValueError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc
