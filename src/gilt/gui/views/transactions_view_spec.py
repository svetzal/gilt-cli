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


class DescribeOnDateRangeChanged:
    def it_should_show_custom_dates_and_skip_run_filters_for_custom_preset(self):
        view = MagicMock()
        view.date_range_combo.currentText.return_value = "Custom"

        TransactionsView._on_date_range_changed(view, 0)

        view._set_custom_dates_visible.assert_called_once_with(True)
        view.run_filters.assert_not_called()

    def it_should_hide_custom_dates_and_run_filters_without_touching_edits_for_all_preset(self):
        view = MagicMock()
        view.date_range_combo.currentText.return_value = "All"

        TransactionsView._on_date_range_changed(view, 0)

        view._set_custom_dates_visible.assert_called_once_with(False)
        view.run_filters.assert_called_once()
        view.start_date_edit.setDate.assert_not_called()
        view.end_date_edit.setDate.assert_not_called()

    def it_should_set_date_edits_and_run_filters_for_concrete_preset(self):
        view = MagicMock()
        view.date_range_combo.currentText.return_value = "This Month"

        with patch(
            "gilt.gui.views.transactions_view.get_date_range",
            return_value=(date(2025, 6, 1), date(2025, 6, 30)),
        ):
            TransactionsView._on_date_range_changed(view, 0)

        view._set_custom_dates_visible.assert_called_once_with(False)
        view.start_date_edit.setDate.assert_called_once()
        view.end_date_edit.setDate.assert_called_once()
        view.run_filters.assert_called_once()


class DescribeUpdateAccountCombo:
    def it_should_clear_and_repopulate_with_all_accounts_first(self):
        view = MagicMock()
        view.account_combo.currentData.return_value = None
        view.service.load_available_accounts.return_value = ["MYBANK_CHQ", "BANK2_BIZ"]

        TransactionsView._update_account_combo(view)

        view.account_combo.clear.assert_called_once()
        calls = view.account_combo.addItem.call_args_list
        assert calls[0].args == ("All Accounts", None)
        assert calls[1].args == ("MYBANK_CHQ", "MYBANK_CHQ")
        assert calls[2].args == ("BANK2_BIZ", "BANK2_BIZ")

    def it_should_restore_selection_when_still_present(self):
        view = MagicMock()
        view.account_combo.currentData.return_value = "MYBANK_CHQ"
        view.account_combo.findData.return_value = 1
        view.service.load_available_accounts.return_value = ["MYBANK_CHQ"]

        TransactionsView._update_account_combo(view)

        view.account_combo.setCurrentIndex.assert_called_once_with(1)

    def it_should_not_restore_selection_when_absent(self):
        view = MagicMock()
        view.account_combo.currentData.return_value = "GONE_ACCOUNT"
        view.account_combo.findData.return_value = -1
        view.service.load_available_accounts.return_value = ["MYBANK_CHQ"]

        TransactionsView._update_account_combo(view)

        view.account_combo.setCurrentIndex.assert_not_called()


class DescribeUpdateCategoryCombo:
    def it_should_clear_and_repopulate_with_all_categories_first(self):
        view = MagicMock()
        view.category_combo.currentData.return_value = None
        view.service.get_unique_categories.return_value = ["Groceries", "Work"]

        TransactionsView._update_category_combo(view)

        view.category_combo.clear.assert_called_once()
        calls = view.category_combo.addItem.call_args_list
        assert calls[0].args == ("All Categories", None)
        assert calls[1].args == ("Groceries", "Groceries")
        assert calls[2].args == ("Work", "Work")

    def it_should_restore_selection_when_still_present(self):
        view = MagicMock()
        view.category_combo.currentData.return_value = "Groceries"
        view.category_combo.findData.return_value = 1
        view.service.get_unique_categories.return_value = ["Groceries"]

        TransactionsView._update_category_combo(view)

        view.category_combo.setCurrentIndex.assert_called_once_with(1)

    def it_should_not_restore_selection_when_absent(self):
        view = MagicMock()
        view.category_combo.currentData.return_value = "Gone"
        view.category_combo.findData.return_value = -1
        view.service.get_unique_categories.return_value = ["Groceries"]

        TransactionsView._update_category_combo(view)

        view.category_combo.setCurrentIndex.assert_not_called()


class DescribeUpdateStatus:
    def it_should_show_total_count_when_displayed_equals_total(self):
        view = MagicMock()
        view.table.get_row_count.return_value = 5
        view._all_transactions = [MagicMock() for _ in range(5)]
        view.table.get_selected_transactions.return_value = []

        TransactionsView._update_status(view)

        view.status_label.setText.assert_called_once_with("Showing 5 transactions")

    def it_should_show_displayed_of_total_when_filtered(self):
        view = MagicMock()
        view.table.get_row_count.return_value = 2
        view._all_transactions = [MagicMock() for _ in range(5)]
        view.table.get_selected_transactions.return_value = []

        TransactionsView._update_status(view)

        view.status_label.setText.assert_called_once_with("Showing 2 of 5 transactions")

    def it_should_append_selected_count_when_selection_present(self):
        view = MagicMock()
        view.table.get_row_count.return_value = 5
        view._all_transactions = [MagicMock() for _ in range(5)]
        view.table.get_selected_transactions.return_value = [MagicMock(), MagicMock()]

        TransactionsView._update_status(view)

        view.status_label.setText.assert_called_once_with("Showing 5 transactions | 2 selected")


class DescribeOnResolveDuplicateRequested:
    def it_should_do_nothing_when_no_selection(self):
        view = MagicMock()
        view.table.get_selected_transactions.return_value = []

        TransactionsView._on_resolve_duplicate_requested(view)

        view._mutation_controller.run_duplicate_resolution.assert_not_called()

    def it_should_do_nothing_when_multiple_selected(self):
        view = MagicMock()
        view.table.get_selected_transactions.return_value = [MagicMock(), MagicMock()]

        TransactionsView._on_resolve_duplicate_requested(view)

        view._mutation_controller.run_duplicate_resolution.assert_not_called()

    def it_should_call_controller_when_exactly_one_selected(self):
        view = MagicMock()
        txn = MagicMock()
        view.table.get_selected_transactions.return_value = [txn]
        view.table.transaction_model.get_metadata.return_value = {"foo": "bar"}

        TransactionsView._on_resolve_duplicate_requested(view)

        view.table.transaction_model.get_metadata.assert_called_once_with(
            txn.primary.transaction_id
        )
        view._mutation_controller.run_duplicate_resolution.assert_called_once_with(
            txn, {"foo": "bar"}
        )


class DescribeOnSelectionChanged:
    def it_should_return_early_when_detail_panel_hidden(self):
        view = MagicMock()
        view.detail_panel.isVisible.return_value = False

        TransactionsView._on_selection_changed(view)

        view.detail_panel.update_transaction.assert_not_called()

    def it_should_skip_receipt_candidates_when_enrichment_found(self):
        view = MagicMock()
        view.detail_panel.isVisible.return_value = True
        txn = MagicMock()
        view.table.get_current_transaction.return_value = txn
        view.enrichment_service.get_enrichment.return_value = {"category": "Groceries"}

        TransactionsView._on_selection_changed(view)

        view._receipt_controller.find_candidates.assert_not_called()
        view.detail_panel.update_transaction.assert_called_once()

    def it_should_look_up_receipt_candidates_when_no_enrichment(self):
        view = MagicMock()
        view.detail_panel.isVisible.return_value = True
        txn = MagicMock()
        view.table.get_current_transaction.return_value = txn
        view.enrichment_service.get_enrichment.return_value = None
        view._receipt_controller.find_candidates.return_value = ["candidate"]

        TransactionsView._on_selection_changed(view)

        view._receipt_controller.find_candidates.assert_called_once_with(txn)
        view.detail_panel.update_transaction.assert_called_once()
