import logging
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PySide6")

from gilt.gui.views.transactions_view import TransactionsView


class DescribeLoadEnrichment:
    def it_should_set_enrichment_service_to_none_and_log_warning_on_error(self, caplog):
        view = MagicMock()
        view.event_store = MagicMock()
        view.event_store.get_events_by_type.side_effect = ValueError("corrupt event store")

        with caplog.at_level(logging.WARNING, logger="gilt.gui.views.transactions_view"):
            TransactionsView._load_enrichment(view)

        assert view.enrichment_service is None
        assert "Enrichment data unavailable" in caplog.text


class DescribeTransactionsViewEnrichmentWithRealView:
    """_load_enrichment verified on a real TransactionsView instantiated with stubs."""

    def it_should_set_enrichment_service_to_none_when_event_store_raises(
        self, qapp, tmp_path, caplog
    ):
        data_dir = tmp_path / "accounts"
        data_dir.mkdir()
        categories_yml = tmp_path / "categories.yml"
        categories_yml.write_text("categories: []\n", encoding="utf-8")

        event_store = MagicMock()
        event_store.get_events_by_type.side_effect = ValueError("corrupt event store")

        with (
            patch(
                "gilt.gui.dialogs.settings_dialog.SettingsDialog.get_categories_config",
                return_value=categories_yml,
            ),
            caplog.at_level(logging.WARNING, logger="gilt.gui.views.transactions_view"),
        ):
            view = TransactionsView(data_dir=data_dir, event_store=event_store)

        assert view.enrichment_service is None
        assert "Enrichment data unavailable" in caplog.text


class DescribeRunFilters:
    def _make_view(
        self,
        *,
        account_data=None,
        date_range_text="All",
        category_data=None,
        search_text="",
        uncategorized=False,
        start_date=None,
        end_date=None,
    ):
        """Build a minimal mock matching TransactionsView's filter attributes."""
        view = MagicMock()
        view.account_combo.currentData.return_value = account_data
        view.date_range_combo.currentText.return_value = date_range_text
        view.category_combo.currentData.return_value = category_data
        view.search_edit.text.return_value = search_text
        view.uncategorized_check.isChecked.return_value = uncategorized
        if start_date:
            sd = MagicMock()
            sd.year.return_value = start_date.year
            sd.month.return_value = start_date.month
            sd.day.return_value = start_date.day
            view.start_date_edit.date.return_value = sd
        if end_date:
            ed = MagicMock()
            ed.year.return_value = end_date.year
            ed.month.return_value = end_date.month
            ed.day.return_value = end_date.day
            view.end_date_edit.date.return_value = ed
        return view

    def it_should_pass_none_dates_when_period_is_all(self):
        view = self._make_view(date_range_text="All")

        TransactionsView.run_filters(view)

        view.table.set_filters.assert_called_once()
        kwargs = view.table.set_filters.call_args.kwargs
        assert kwargs["start_date"] is None
        assert kwargs["end_date"] is None

    def it_should_pass_date_range_from_edits_when_not_all(self):
        view = self._make_view(
            date_range_text="Custom",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )

        TransactionsView.run_filters(view)

        kwargs = view.table.set_filters.call_args.kwargs
        assert kwargs["start_date"] == date(2025, 1, 1)
        assert kwargs["end_date"] == date(2025, 3, 31)

    def it_should_pass_account_filter_when_account_selected(self):
        view = self._make_view(account_data="MYBANK_CHQ")

        TransactionsView.run_filters(view)

        kwargs = view.table.set_filters.call_args.kwargs
        assert kwargs["account_filter"] == ["MYBANK_CHQ"]

    def it_should_pass_none_account_when_all_accounts(self):
        view = self._make_view(account_data=None)

        TransactionsView.run_filters(view)

        kwargs = view.table.set_filters.call_args.kwargs
        assert kwargs["account_filter"] is None

    def it_should_pass_uncategorized_flag(self):
        view = self._make_view(uncategorized=True)

        TransactionsView.run_filters(view)

        kwargs = view.table.set_filters.call_args.kwargs
        assert kwargs["uncategorized_only"] is True

    def it_should_strip_empty_search_text_to_none(self):
        view = self._make_view(search_text="   ")

        TransactionsView.run_filters(view)

        kwargs = view.table.set_filters.call_args.kwargs
        assert kwargs["search_text"] is None

    def it_should_pass_non_empty_search_text(self):
        view = self._make_view(search_text="SAMPLE")

        TransactionsView.run_filters(view)

        kwargs = view.table.set_filters.call_args.kwargs
        assert kwargs["search_text"] == "SAMPLE"


class DescribeClearFilters:
    def it_should_reset_combos_on_clear_filters(self):
        view = MagicMock()

        TransactionsView.clear_filters(view)

        view.account_combo.setCurrentIndex.assert_called_once_with(0)
        view.date_range_combo.setCurrentIndex.assert_called_once_with(0)
        view.category_combo.setCurrentIndex.assert_called_once_with(0)
        view.search_edit.clear.assert_called_once()
        view.uncategorized_check.setChecked.assert_called_once_with(False)
