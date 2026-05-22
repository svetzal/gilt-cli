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
