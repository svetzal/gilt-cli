import logging

import pytest

pytest.importorskip("PySide6")

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from gilt.gui.views.transactions_view import (
    IntelligenceWorker,
    TransactionsView,
    compute_date_range,
)
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService


class DescribeIntelligenceWorker:
    def it_should_scan_for_duplicates_and_categories(self):
        # Arrange
        txn1 = Transaction(
            transaction_id="t1",
            date=date(2023, 1, 1),
            amount=10.0,
            description="Test 1",
            account_id="acc1",
        )
        txn2 = Transaction(
            transaction_id="t2",
            date=date(2023, 1, 1),
            amount=10.0,
            description="Test 2",
            account_id="acc2",
        )
        groups = [
            TransactionGroup(group_id="g1", primary=txn1),
            TransactionGroup(group_id="g2", primary=txn2),
        ]

        mock_dup_service = Mock(spec=DuplicateService)
        mock_cat_service = Mock(spec=SmartCategoryService)

        # Mock duplicate detection
        pair = TransactionPair(
            txn1_id="t1",
            txn1_date=date(2023, 1, 1),
            txn1_description="Test 1",
            txn1_amount=10.0,
            txn1_account="acc1",
            txn2_id="t2",
            txn2_date=date(2023, 1, 1),
            txn2_description="Test 2",
            txn2_amount=10.0,
            txn2_account="acc2",
        )
        assessment = DuplicateAssessment(
            is_duplicate=True, confidence=0.9, reasoning="High confidence"
        )
        match = DuplicateMatch(pair=pair, assessment=assessment)
        mock_dup_service.scan_transactions.return_value = [match]

        # Mock categorization
        mock_cat_service.predict_category.return_value = ("Food", 0.85)

        worker = IntelligenceWorker(groups, mock_dup_service, mock_cat_service)

        # Act
        # We call run() directly to avoid threading issues in test
        # But we need to connect signal first
        result = []
        worker.finished.connect(lambda x: result.append(x))

        worker.run()

        # Assert
        assert len(result) == 1
        metadata = result[0]

        # Check duplicate risk
        assert metadata["t1"]["risk"] is True
        assert metadata["t2"]["risk"] is True

        # Check categorization confidence
        assert metadata["t1"]["confidence"] == 0.85
        assert metadata["t2"]["confidence"] == 0.85


class DescribeComputeDateRange:
    def it_should_return_this_month_range(self):
        today = date(2025, 3, 15)

        start, end = compute_date_range("This Month", today)

        assert start == date(2025, 3, 1)
        assert end == date(2025, 3, 15)

    def it_should_return_last_month_range(self):
        today = date(2025, 3, 15)

        start, end = compute_date_range("Last Month", today)

        assert start == date(2025, 2, 1)
        assert end == date(2025, 2, 28)

    def it_should_handle_last_month_year_rollover(self):
        today = date(2025, 1, 15)

        start, end = compute_date_range("Last Month", today)

        assert start == date(2024, 12, 1)
        assert end == date(2024, 12, 31)

    def it_should_return_this_year_range(self):
        today = date(2025, 3, 15)

        start, end = compute_date_range("This Year", today)

        assert start == date(2025, 1, 1)
        assert end == date(2025, 3, 15)

    def it_should_return_last_year_range(self):
        today = date(2025, 3, 15)

        start, end = compute_date_range("Last Year", today)

        assert start == date(2024, 1, 1)
        assert end == date(2024, 12, 31)

    def it_should_return_none_none_for_all(self):
        start, end = compute_date_range("All", date(2025, 3, 15))

        assert start is None
        assert end is None

    def it_should_return_none_none_for_custom(self):
        start, end = compute_date_range("Custom", date(2025, 3, 15))

        assert start is None
        assert end is None


def _make_group() -> tuple[Transaction, TransactionGroup]:
    txn = Transaction(
        transaction_id="t1",
        date=date(2025, 1, 15),
        amount=-50.0,
        description="SAMPLE STORE",
        account_id="MYBANK_CHQ",
    )
    group = TransactionGroup(group_id="g1", primary=txn)
    return txn, group


class DescribeApplyCategorization:
    def it_should_use_event_store_when_available(self):
        view = MagicMock()
        view.event_store = MagicMock()
        view.es_service = MagicMock()
        view.smart_category_service = None
        _, group = _make_group()

        with patch("gilt.gui.views.transactions_view.LedgerRepository"), patch(
            "gilt.gui.views.transactions_view.CategorizationPersistenceService"
        ) as mock_persist_svc:
            TransactionsView._apply_categorization(view, [group], "Food", None)

        mock_persist_svc.return_value.persist_categorizations.assert_called_once()
        view.reload_transactions.assert_called_once_with(restore_transaction_id=None)

    def it_should_sync_projections_when_no_event_store(self):
        view = MagicMock()
        view.event_store = None
        view.smart_category_service = None
        _, group = _make_group()

        with patch("gilt.gui.views.transactions_view.LedgerRepository"), patch(
            "gilt.services.categorization_persistence_service.write_categorizations_to_csv"
        ) as mock_write:
            TransactionsView._apply_categorization(view, [group], "Food", None)

        mock_write.assert_called_once()
        view._sync_projections.assert_called_once()
        view.reload_transactions.assert_called_once()

    def it_should_record_categorization_when_smart_service_present(self):
        view = MagicMock()
        view.event_store = MagicMock()
        view.es_service = MagicMock()
        view.smart_category_service = MagicMock()
        txn, group = _make_group()

        with patch("gilt.gui.views.transactions_view.LedgerRepository"), patch(
            "gilt.gui.views.transactions_view.CategorizationPersistenceService"
        ):
            TransactionsView._apply_categorization(
                view, [group], "Food", "Groceries", source="user"
            )

        view.smart_category_service.record_categorization.assert_called_once_with(
            transaction_id=txn.transaction_id,
            category="Food",
            subcategory="Groceries",
            source="user",
            previous_category=txn.category,
            previous_subcategory=txn.subcategory,
        )


class DescribeApplyNote:
    def it_should_persist_sync_and_reload(self):
        view = MagicMock()
        view.service.data_dir = Path("/tmp/test_data")
        _, group = _make_group()

        with patch("gilt.gui.views.transactions_view.LedgerRepository"), patch(
            "gilt.gui.views.transactions_view.QMessageBox"
        ), patch("gilt.gui.views.transactions_view.persist_note_update") as mock_persist:
            TransactionsView._apply_note(view, group, "Test note")

        mock_persist.assert_called_once()
        assert mock_persist.call_args.kwargs["note"] == "Test note"
        assert mock_persist.call_args.kwargs["account_id"] == "MYBANK_CHQ"
        assert mock_persist.call_args.kwargs["transaction_id"] == "t1"
        view._sync_projections.assert_called_once()
        view.reload_transactions.assert_called_once()

    def it_should_convert_empty_note_to_none(self):
        view = MagicMock()
        view.service.data_dir = Path("/tmp/test_data")
        _, group = _make_group()

        with patch("gilt.gui.views.transactions_view.LedgerRepository"), patch(
            "gilt.gui.views.transactions_view.QMessageBox"
        ), patch("gilt.gui.views.transactions_view.persist_note_update") as mock_persist:
            TransactionsView._apply_note(view, group, "")

        assert mock_persist.call_args.kwargs["note"] is None


class DescribeIntelligenceScanCallbacks:
    def it_should_update_cache_and_emit_signals_on_finish(self):
        view = MagicMock()
        metadata = {"t1": {"risk": True}}

        TransactionsView._on_intelligence_scan_finished(view, metadata)

        view._intelligence_cache.update.assert_called_once_with(metadata)
        view.table._model.update_metadata.assert_called_once_with(metadata)
        view._update_status.assert_called_once()
        view.status_message.emit.assert_called_once_with("Intelligence scan complete")
        view.scan_finished.emit.assert_called_once()

    def it_should_emit_error_message_and_finished_on_error(self):
        view = MagicMock()
        error_msg = "Connection failed"

        TransactionsView._on_intelligence_scan_error(view, error_msg)

        view.status_message.emit.assert_called_once_with(error_msg)
        view.scan_finished.emit.assert_called_once()


class DescribeGetReceiptMatchService:
    def it_should_return_none_when_no_event_store(self):
        view = MagicMock()
        view.event_store = None

        result = TransactionsView._get_receipt_match_service(view)

        assert result is None

    def it_should_return_service_when_receipts_dir_exists(self, tmp_path):
        view = MagicMock()
        view.event_store = MagicMock()

        with patch(
            "gilt.gui.views.transactions_view.SettingsDialog"
        ) as mock_settings, patch(
            "gilt.gui.views.transactions_view.ReceiptMatchService"
        ) as mock_svc:
            mock_settings.get_receipts_dir.return_value = tmp_path

            result = TransactionsView._get_receipt_match_service(view)

        assert result == mock_svc.return_value
        mock_svc.assert_called_once_with(tmp_path, view.event_store)

    def it_should_return_none_when_receipts_dir_missing(self, tmp_path):
        view = MagicMock()
        view.event_store = MagicMock()
        nonexistent = tmp_path / "nonexistent"

        with patch(
            "gilt.gui.views.transactions_view.SettingsDialog"
        ) as mock_settings, patch("gilt.gui.views.transactions_view.QMessageBox"):
            mock_settings.get_receipts_dir.return_value = nonexistent

            result = TransactionsView._get_receipt_match_service(view)

        assert result is None


class DescribeLoadEnrichment:
    def it_should_set_enrichment_service_to_none_and_log_warning_on_error(self, caplog):
        view = MagicMock()
        view.event_store = MagicMock()
        view.event_store.get_events_by_type.side_effect = ValueError("corrupt event store")

        with caplog.at_level(logging.WARNING, logger="gilt.gui.views.transactions_view"):
            TransactionsView._load_enrichment(view)

        assert view.enrichment_service is None
        assert "Enrichment data unavailable" in caplog.text


class DescribeWorkerLifecycle:
    def it_should_disconnect_all_signals_from_worker(self):
        view = MagicMock()
        worker = MagicMock()

        TransactionsView._disconnect_all_worker_signals(view, worker)

        worker.finished.disconnect.assert_called_once()
        worker.error.disconnect.assert_called_once()
        worker.status.disconnect.assert_called_once()
        worker.progress.disconnect.assert_called_once()

    def it_should_interrupt_and_wait_for_running_worker(self):
        view = MagicMock()
        view._old_workers = []
        worker = MagicMock()
        worker.isRunning.return_value = True
        view.worker = worker

        TransactionsView._stop_workers(view)

        view._disconnect_all_worker_signals.assert_called_once_with(worker)
        worker.requestInterruption.assert_called_once()
        worker.wait.assert_called_once_with(3000)
        assert view.worker is None

    def it_should_handle_no_worker_gracefully(self):
        view = MagicMock()
        view.worker = None
        view._old_workers = []

        TransactionsView._stop_workers(view)

        assert view.worker is None

    def it_should_clear_old_workers(self):
        view = MagicMock()
        view.worker = None
        old_worker = MagicMock()
        old_worker.isRunning.return_value = False
        view._old_workers = [old_worker]

        TransactionsView._stop_workers(view)

        old_worker.wait.assert_called()
        assert view._old_workers == []
