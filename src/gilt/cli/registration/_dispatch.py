"""Shared dispatch helpers for CLI command registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NoReturn

import typer

HELP_WRITE = "Persist changes (default: dry-run)"


def dispatch(run: Callable[..., int], /, **kwargs: Any) -> NoReturn:
    """Single choke-point: invoke a command's run() and translate its exit code into typer.Exit.

    Cross-cutting concerns (logging, error middleware, exit-code translation) belong here,
    not in each wrapper.
    """
    code = run(**kwargs)
    raise typer.Exit(code=code)


def resolve_fy_range(fy: str | None):
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
