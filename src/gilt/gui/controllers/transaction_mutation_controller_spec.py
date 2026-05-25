import pytest

pytest.importorskip("PySide6")

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from gilt.gui.controllers.transaction_mutation_controller import TransactionMutationController
from gilt.testing.fixtures import make_group


class DescribeApplyCategorization:
    def it_should_use_event_store_when_available(self):
        controller = MagicMock()
        controller._event_store = MagicMock()
        controller._es_service = MagicMock()
        controller._smart_category_service = None
        group = make_group(
            transaction_id="t1", date=date(2025, 1, 15), amount=-50.0, description="SAMPLE STORE"
        )

        with patch(
            "gilt.gui.controllers.transaction_mutation_controller.LedgerRepository"
        ), patch(
            "gilt.gui.controllers.transaction_mutation_controller.CategorizationPersistenceService"
        ) as mock_persist_svc:
            TransactionMutationController._apply_categorization(controller, [group], "Food", None)

        mock_persist_svc.return_value.persist_categorizations.assert_called_once()
        controller.data_changed.emit.assert_called_once_with(None)

    def it_should_sync_projections_when_no_event_store(self):
        controller = MagicMock()
        controller._event_store = None
        controller._smart_category_service = None
        group = make_group(
            transaction_id="t1", date=date(2025, 1, 15), amount=-50.0, description="SAMPLE STORE"
        )

        with patch(
            "gilt.gui.controllers.transaction_mutation_controller.LedgerRepository"
        ), patch(
            "gilt.services.categorization_persistence_service.persist_categorizations_to_csv"
        ) as mock_write:
            TransactionMutationController._apply_categorization(controller, [group], "Food", None)

        mock_write.assert_called_once()
        controller._sync_projections.assert_called_once()
        controller.data_changed.emit.assert_called_once_with(None)

    def it_should_record_categorization_when_smart_service_present(self):
        controller = MagicMock()
        controller._event_store = MagicMock()
        controller._es_service = MagicMock()
        controller._smart_category_service = MagicMock()
        group = make_group(
            transaction_id="t1", date=date(2025, 1, 15), amount=-50.0, description="SAMPLE STORE"
        )
        txn = group.primary

        with patch(
            "gilt.gui.controllers.transaction_mutation_controller.LedgerRepository"
        ), patch(
            "gilt.gui.controllers.transaction_mutation_controller.CategorizationPersistenceService"
        ):
            TransactionMutationController._apply_categorization(
                controller, [group], "Food", "Groceries", source="user"
            )

        controller._smart_category_service.record_categorization.assert_called_once_with(
            transaction_id=txn.transaction_id,
            category="Food",
            subcategory="Groceries",
            source="user",
            previous_category=txn.category,
            previous_subcategory=txn.subcategory,
        )


class DescribeApplyNote:
    def it_should_persist_sync_and_reload(self):
        controller = MagicMock()
        controller._service = MagicMock()
        controller._service.data_dir = Path("/tmp/test_data")
        group = make_group(
            transaction_id="t1", date=date(2025, 1, 15), amount=-50.0, description="SAMPLE STORE"
        )

        with patch(
            "gilt.gui.controllers.transaction_mutation_controller.LedgerRepository"
        ), patch(
            "gilt.gui.controllers.transaction_mutation_controller.QMessageBox"
        ), patch(
            "gilt.gui.controllers.transaction_mutation_controller.persist_note_update"
        ) as mock_persist:
            TransactionMutationController._apply_note(controller, group, "Test note")

        mock_persist.assert_called_once()
        assert mock_persist.call_args.kwargs["note"] == "Test note"
        assert mock_persist.call_args.kwargs["account_id"] == "MYBANK_CHQ"
        assert mock_persist.call_args.kwargs["transaction_id"] == "t1"
        controller._sync_projections.assert_called_once()
        controller.data_changed.emit.assert_called_once_with(None)

    def it_should_convert_empty_note_to_none(self):
        controller = MagicMock()
        controller._service = MagicMock()
        controller._service.data_dir = Path("/tmp/test_data")
        group = make_group(
            transaction_id="t1", date=date(2025, 1, 15), amount=-50.0, description="SAMPLE STORE"
        )

        with patch(
            "gilt.gui.controllers.transaction_mutation_controller.LedgerRepository"
        ), patch(
            "gilt.gui.controllers.transaction_mutation_controller.QMessageBox"
        ), patch(
            "gilt.gui.controllers.transaction_mutation_controller.persist_note_update"
        ) as mock_persist:
            TransactionMutationController._apply_note(controller, group, "")

        assert mock_persist.call_args.kwargs["note"] is None


class DescribeApplyPrediction:
    def it_should_parse_category_and_subcategory_from_prediction(self):
        controller = MagicMock()
        group = make_group(
            transaction_id="t1", date=date(2025, 1, 15), amount=-50.0, description="SAMPLE STORE"
        )

        TransactionMutationController._apply_prediction(controller, group, "Food: Groceries")

        controller._apply_categorization.assert_called_once_with(
            [group],
            "Food",
            "Groceries",
            source="llm",
            restore_transaction_id="t1",
        )

    def it_should_parse_prediction_with_no_subcategory(self):
        controller = MagicMock()
        group = make_group(
            transaction_id="t2", date=date(2025, 1, 15), amount=-20.0, description="BUS PASS"
        )

        TransactionMutationController._apply_prediction(controller, group, "Transport")

        controller._apply_categorization.assert_called_once_with(
            [group],
            "Transport",
            None,
            source="llm",
            restore_transaction_id="t2",
        )


class DescribeCategorizeSelected:
    def it_should_skip_when_no_transactions_selected(self):
        controller = MagicMock()

        TransactionMutationController.categorize_selected(controller, [])

        controller._apply_categorization.assert_not_called()


class DescribeNoteSelected:
    def it_should_not_open_note_dialog_for_multiple_selections(self):
        controller = MagicMock()
        group1 = make_group(transaction_id="t1", date=date(2025, 1, 15), amount=-50.0)
        group2 = make_group(transaction_id="t2", date=date(2025, 1, 16), amount=-30.0)

        TransactionMutationController.note_selected(controller, [group1, group2])

        controller._apply_note.assert_not_called()


class DescribeRunDuplicateResolution:
    def it_should_call_sync_projections_on_successful_resolution(self):
        controller = MagicMock()
        controller._duplicate_service = MagicMock()
        controller._service = MagicMock()
        resolution = MagicMock()
        resolution.confirmed = True
        resolution.delete_transaction_id = "del_id"
        resolution.delete_account_id = "ACC1"
        controller._duplicate_service.run_duplicate_deletion.return_value = resolution
        controller._service.delete_transaction.return_value = True

        group = make_group(transaction_id="t1", date=date(2025, 1, 15), amount=-100.0)
        meta = {"duplicate_match": MagicMock()}

        with patch(
            "gilt.gui.controllers.transaction_mutation_controller.DuplicateResolutionDialog"
        ) as mock_dialog_cls, patch(
            "gilt.gui.controllers.transaction_mutation_controller.QMessageBox"
        ):
            mock_dialog = mock_dialog_cls.return_value
            mock_dialog.exec.return_value = True
            mock_dialog.get_resolution.return_value = (True, "t1")

            TransactionMutationController.run_duplicate_resolution(controller, group, meta)

        controller._sync_projections.assert_called_once()
        controller.data_changed.emit.assert_called_once_with(None)


class DescribeManualMerge:
    def it_should_return_immediately_for_single_transaction(self):
        controller = MagicMock()
        group = make_group(transaction_id="t1", date=date(2025, 1, 15), amount=-100.0)

        TransactionMutationController.manual_merge(controller, [group])

        controller._apply_categorization.assert_not_called()
        controller._sync_projections.assert_not_called()


class DescribeOnTransactionUpdated:
    def it_should_record_inline_edit_with_smart_service_when_categorized(self):
        controller = MagicMock()
        controller._service = MagicMock()
        controller._service.update_transaction.return_value = True
        controller._smart_category_service = MagicMock()

        group = make_group(
            transaction_id="t1",
            date=date(2025, 1, 15),
            amount=-50.0,
            description="SAMPLE STORE",
            category="Food",
            subcategory="Groceries",
        )

        TransactionMutationController.on_transaction_updated(controller, group)

        controller._smart_category_service.record_categorization.assert_called_once_with(
            transaction_id="t1",
            category="Food",
            subcategory="Groceries",
            source="user",
        )
        controller._sync_projections.assert_called_once()

    def it_should_not_record_categorization_when_no_category(self):
        controller = MagicMock()
        controller._service = MagicMock()
        controller._service.update_transaction.return_value = True
        controller._smart_category_service = MagicMock()

        group = make_group(
            transaction_id="t1",
            date=date(2025, 1, 15),
            amount=-50.0,
            description="SAMPLE STORE",
        )

        TransactionMutationController.on_transaction_updated(controller, group)

        controller._smart_category_service.record_categorization.assert_not_called()
