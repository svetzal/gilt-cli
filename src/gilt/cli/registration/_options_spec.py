"""Specs for the shared CLI option factories."""

from __future__ import annotations

import typer

from gilt.cli.registration import _options


class DescribeOptionFactories:
    def it_should_build_an_optional_account_option_by_default(self):
        info = _options.account_option("help text")

        assert isinstance(info, typer.models.OptionInfo)
        assert info.param_decls == ("--account", "-a")
        assert info.default is None
        assert info.help == "help text"

    def it_should_build_a_required_account_option_when_requested(self):
        info = _options.account_option("help text", required=True)

        assert info.default is ...

    def it_should_build_a_required_txid_option_when_requested(self):
        info = _options.txid_option("help text", required=True)

        assert info.default is ...
        assert info.param_decls == ("--txid", "-t")

    def it_should_build_an_optional_txid_option_by_default(self):
        info = _options.txid_option("help text")

        assert info.default is None

    def it_should_build_a_write_option_with_the_shared_default_help(self):
        info = _options.write_option()

        assert info.param_decls == ("--write",)
        assert info.default is False
        assert info.help == _options.HELP_WRITE

    def it_should_build_a_write_option_with_custom_help(self):
        info = _options.write_option("custom help")

        assert info.help == "custom help"

    def it_should_build_a_limit_option_with_optional_range_constraints(self):
        info = _options.limit_option("help text", default=10, min=1)

        assert info.param_decls == ("--limit", "-n")
        assert info.default == 10
        assert info.min == 1

    def it_should_build_a_description_option_without_a_short_flag_when_requested(self):
        info = _options.description_option("help text", short=None)

        assert info.param_decls == ("--description",)

    def it_should_build_a_description_option_with_the_default_short_flag(self):
        info = _options.description_option("help text")

        assert info.param_decls == ("--description", "-d")

    def it_should_build_an_amount_option_without_a_short_flag_when_requested(self):
        info = _options.amount_option("help text", short=None)

        assert info.param_decls == ("--amount",)

    def it_should_build_a_yes_option_with_extra_secondary_flags(self):
        info = _options.yes_option("help text", extra_opts=("-r",))

        assert info.param_decls == ("--yes", "-y", "-r")

    def it_should_build_a_min_confidence_option_with_range_constraints(self):
        info = _options.min_confidence_option("help text", default=0.9, min=0.0, max=1.0)

        assert info.default == 0.9
        assert info.min == 0.0
        assert info.max == 1.0
