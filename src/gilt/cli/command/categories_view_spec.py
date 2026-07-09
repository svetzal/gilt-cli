"""Specs for categories_view.py — Rich rendering for the categories command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.categories_view as view_mod
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


def _make_category_config(with_subcategories=False):
    from gilt.model.category import Category, CategoryConfig, Subcategory

    subcategories = []
    if with_subcategories:
        subcategories = [Subcategory(name="Internet"), Subcategory(name="Phone")]

    return CategoryConfig(
        categories=[
            Category(
                name="Utilities",
                description="Monthly utility bills",
                subcategories=subcategories,
            )
        ]
    )


class DescribeDisplayCategoriesTable:
    def it_should_render_category_names(self):
        from gilt.cli.command.categories_view import display_categories_table

        config = _make_category_config()
        output = _capture(lambda: display_categories_table(config, {}))
        assert "Utilities" in output

    def it_should_show_total_categories_count(self):
        from gilt.cli.command.categories_view import display_categories_table

        config = _make_category_config()
        output = _capture(lambda: display_categories_table(config, {}))
        assert "Total categories" in output

    def it_should_render_subcategory_names_when_present(self):
        from gilt.cli.command.categories_view import display_categories_table

        config = _make_category_config(with_subcategories=True)
        output = _capture(lambda: display_categories_table(config, {}))
        assert "Internet" in output
        assert "Phone" in output


class DescribePrintNoCategories:
    def it_should_mention_creating_categories_config(self):
        from gilt.cli.command.categories_view import print_no_categories

        output = _capture(print_no_categories)
        assert "No categories defined" in output
