"""Specs for category_view.py — Rich rendering for the category command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.category_view as view_mod
    import gilt.cli.console as console_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    old_mod = console_mod.console
    view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
        console_mod.console = old_mod
    return buf.getvalue()


class DescribePrintAlreadyExists:
    def it_should_mention_the_category_name(self):
        from gilt.cli.command.category_view import print_already_exists

        output = _capture(lambda: print_already_exists("Housing", None))
        assert "Housing" in output
        assert "already exists" in output

    def it_should_mention_the_subcategory_path(self):
        from gilt.cli.command.category_view import print_already_exists

        output = _capture(lambda: print_already_exists("Housing", "Utilities"))
        assert "Housing:Utilities" in output
        assert "already exists" in output


class DescribePrintCreateParentHint:
    def it_should_mention_the_parent_and_command(self):
        from gilt.cli.command.category_view import print_create_parent_hint

        output = _capture(lambda: print_create_parent_hint("Housing"))
        assert "gilt category --add 'Housing' --write" in output


class DescribeDisplayAddPreview:
    def it_should_preview_a_new_category(self):
        from gilt.cli.command.category_view import display_add_preview

        output = _capture(lambda: display_add_preview("Housing", None, "Housing expenses"))
        assert "Adding category" in output
        assert "Housing" in output
        assert "Housing expenses" in output

    def it_should_preview_a_new_subcategory(self):
        from gilt.cli.command.category_view import display_add_preview

        output = _capture(lambda: display_add_preview("Housing", "Utilities", None))
        assert "Adding subcategory" in output
        assert "Housing:Utilities" in output


class DescribePrintSaved:
    def it_should_mention_the_config_path(self):
        from gilt.cli.command.category_view import print_saved

        output = _capture(lambda: print_saved(Path("config/categories.yml")))
        assert "config/categories.yml" in output


class DescribePrintRemovalWarnings:
    def it_should_print_each_warning(self):
        from gilt.cli.command.category_view import print_removal_warnings

        output = _capture(lambda: print_removal_warnings(["used in 3 transactions"]))
        assert "used in 3 transactions" in output


class DescribePrintForceHint:
    def it_should_mention_force(self):
        from gilt.cli.command.category_view import print_force_hint

        assert "--force" in _capture(print_force_hint)


class DescribePrintCancelled:
    def it_should_print_cancelled(self):
        from gilt.cli.command.category_view import print_cancelled

        assert "Cancelled" in _capture(print_cancelled)


class DescribePrintNotFoundWarning:
    def it_should_print_the_warning(self):
        from gilt.cli.command.category_view import print_not_found_warning

        assert "not found" in _capture(lambda: print_not_found_warning("Category not found"))


class DescribeDisplayRemovePreview:
    def it_should_preview_a_category_removal(self):
        from gilt.cli.command.category_view import display_remove_preview

        output = _capture(lambda: display_remove_preview("Housing", None, 5, None))
        assert "Removing category" in output
        assert "Housing" in output
        assert "5" in output

    def it_should_preview_a_subcategory_removal_with_subcategory_count(self):
        from gilt.cli.command.category_view import display_remove_preview

        output = _capture(lambda: display_remove_preview("Housing", "Utilities", 2, 3))
        assert "Removing subcategory" in output
        assert "Housing:Utilities" in output
        assert "3 subcategory" in output


class DescribeDisplaySetBudgetPreview:
    def it_should_preview_a_new_budget(self):
        from gilt.cli.command.category_view import display_set_budget_preview

        output = _capture(lambda: display_set_budget_preview("Dining Out", 400.0, "monthly", None))
        assert "Setting budget for" in output
        assert "Dining Out" in output
        assert "400" in output
        assert "monthly" in output

    def it_should_show_previous_budget(self):
        from gilt.cli.command.category_view import display_set_budget_preview

        previous = SimpleNamespace(amount=300.0, period=SimpleNamespace(value="monthly"))
        output = _capture(
            lambda: display_set_budget_preview("Dining Out", 500.0, "yearly", previous)
        )
        assert "Previous" in output
        assert "300" in output


class DescribePrintSetBudgetCreateHint:
    def it_should_mention_the_create_command(self):
        from gilt.cli.command.category_view import print_set_budget_create_hint

        output = _capture(lambda: print_set_budget_create_hint("Housing"))
        assert "gilt category --add 'Housing' --write" in output
