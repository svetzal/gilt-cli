"""Specs for diagnose_categories_view.py — Rich rendering for the diagnose-categories command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.diagnose_categories_view as view_mod
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


def _make_orphan(category="OldCat", subcategory=None, count=3, similar=None):
    orphan = MagicMock()
    orphan.category = category
    orphan.subcategory = subcategory
    orphan.transaction_count = count
    orphan.similar_categories = similar or []
    return orphan


class DescribeDisplayOrphanedCategories:
    def it_should_show_count_of_orphaned_categories(self):
        from gilt.cli.command.diagnose_categories_view import display_orphaned_categories
        from gilt.model.category import Category, CategoryConfig

        result = MagicMock()
        result.orphaned_categories = [_make_orphan("OldCat")]
        config = CategoryConfig(categories=[Category(name="Utilities")])

        output = _capture(lambda: display_orphaned_categories(result, config))
        assert "1" in output

    def it_should_display_orphaned_category_name(self):
        from gilt.cli.command.diagnose_categories_view import display_orphaned_categories
        from gilt.model.category import Category, CategoryConfig

        result = MagicMock()
        result.orphaned_categories = [_make_orphan("OldCat")]
        config = CategoryConfig(categories=[Category(name="Utilities")])

        output = _capture(lambda: display_orphaned_categories(result, config))
        assert "OldCat" in output

    def it_should_display_action_guidance(self):
        from gilt.cli.command.diagnose_categories_view import display_orphaned_categories
        from gilt.model.category import Category, CategoryConfig

        result = MagicMock()
        result.orphaned_categories = [_make_orphan("OldCat")]
        config = CategoryConfig(categories=[Category(name="Utilities")])

        output = _capture(lambda: display_orphaned_categories(result, config))
        assert "Action required" in output
