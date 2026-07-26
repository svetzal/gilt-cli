"""Specs for the shared CLI dispatch helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import typer

from gilt.cli.command._errors import CommandAbort
from gilt.cli.registration._dispatch import build_fy_range, command_kwargs, dispatch
from gilt.model.errors import LedgerLoadError


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

    def it_should_print_error_and_exit_1_for_gilt_data_error(self, mocker):
        mock_print_error = mocker.patch("gilt.cli.console.print_error")

        def fake_run(**kwargs):
            raise LedgerLoadError(Path("/data/accounts/MYBANK_CHQ.csv"))

        with pytest.raises(typer.Exit) as exc_info:
            dispatch(fake_run)

        assert exc_info.value.exit_code == 1
        mock_print_error.assert_called_once()
        assert "MYBANK_CHQ.csv" in mock_print_error.call_args[0][0]


class _FakeContext:
    """Minimal stand-in for typer.Context — command_kwargs only reads ``.params``."""

    def __init__(self, params: dict):
        self.params = params


class DescribeCommandKwargs:
    def it_should_pass_through_ctx_params_unchanged(self):
        ctx = _FakeContext({"account": "MYBANK_CHQ", "write": False})

        assert command_kwargs(ctx) == {"account": "MYBANK_CHQ", "write": False}

    def it_should_drop_named_keys(self):
        ctx = _FakeContext({"account": "MYBANK_CHQ", "fy": "FY25", "write": False})

        result = command_kwargs(ctx, drop={"fy"})

        assert result == {"account": "MYBANK_CHQ", "write": False}

    def it_should_rename_named_keys(self):
        ctx = _FakeContext({"yes": True, "write": False})

        result = command_kwargs(ctx, rename={"yes": "assume_yes"})

        assert result == {"assume_yes": True, "write": False}

    def it_should_overlay_extra_kwargs_on_top_of_ctx_params(self):
        ctx = _FakeContext({"account": "MYBANK_CHQ", "write": False})

        result = command_kwargs(ctx, workspace="ws-object")

        assert result == {"account": "MYBANK_CHQ", "write": False, "workspace": "ws-object"}

    def it_should_let_extra_override_a_ctx_param_of_the_same_name(self):
        ctx = _FakeContext({"account": "MYBANK_CHQ"})

        result = command_kwargs(ctx, account="OVERRIDDEN")

        assert result == {"account": "OVERRIDDEN"}

    def it_should_raise_key_error_for_an_unknown_drop_key(self):
        ctx = _FakeContext({"account": "MYBANK_CHQ"})

        with pytest.raises(KeyError):
            command_kwargs(ctx, drop={"nonexistent"})

    def it_should_raise_key_error_for_an_unknown_rename_key(self):
        ctx = _FakeContext({"account": "MYBANK_CHQ"})

        with pytest.raises(KeyError):
            command_kwargs(ctx, rename={"nonexistent": "renamed"})


class DescribeResolveFyRange:
    def it_should_return_none_when_fy_is_none(self):
        assert build_fy_range(None) is None

    def it_should_return_a_range_for_a_valid_fy(self):
        start, end = build_fy_range("FY25")

        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_raise_typer_exit_code_1_for_an_invalid_fy(self, mocker):
        mock_print = mocker.patch("gilt.cli.console.console.print")

        with pytest.raises(typer.Exit) as exc_info:
            build_fy_range("INVALID_FY")

        assert exc_info.value.exit_code == 1
        mock_print.assert_called_once()
        assert "[red]Error:[/]" in mock_print.call_args[0][0]
