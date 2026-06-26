"""Specs for the shared CLI dispatch helpers."""

from __future__ import annotations

from datetime import date

import pytest
import typer

from gilt.cli.command._errors import CommandAbort
from gilt.cli.registration._dispatch import dispatch, resolve_fy_range


class DescribeDispatch:
    def it_should_call_run_with_kwargs_and_raise_typer_exit_with_the_returned_code(self):
        def fake_run(**kwargs):
            return 0

        with pytest.raises(typer.Exit) as exc_info:
            dispatch(fake_run, a=1, b=2)

        assert exc_info.value.exit_code == 0

    def it_should_propagate_a_nonzero_exit_code(self):
        def fake_run(**kwargs):
            return 3

        with pytest.raises(typer.Exit) as exc_info:
            dispatch(fake_run)

        assert exc_info.value.exit_code == 3

    def it_should_translate_command_abort_to_typer_exit_with_abort_code(self):
        def fake_run(**kwargs):
            raise CommandAbort(2)

        with pytest.raises(typer.Exit) as exc_info:
            dispatch(fake_run)

        assert exc_info.value.exit_code == 2


class DescribeResolveFyRange:
    def it_should_return_none_when_fy_is_none(self):
        assert resolve_fy_range(None) is None

    def it_should_return_a_range_for_a_valid_fy(self):
        start, end = resolve_fy_range("FY25")

        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_raise_typer_exit_code_1_for_an_invalid_fy(self, mocker):
        mock_print = mocker.patch("gilt.cli.console.console.print")

        with pytest.raises(typer.Exit) as exc_info:
            resolve_fy_range("INVALID_FY")

        assert exc_info.value.exit_code == 1
        mock_print.assert_called_once()
        assert "[red]Error:[/]" in mock_print.call_args[0][0]
