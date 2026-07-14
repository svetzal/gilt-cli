import pytest

pytest.importorskip("PySide6")

from unittest.mock import MagicMock, patch

from gilt.gui.controllers.receipt_match_controller import ReceiptMatchController


class DescribeGetReceiptMatchService:
    def it_should_return_none_when_no_event_store(self):
        controller = MagicMock()
        controller._event_store = None

        result = ReceiptMatchController.get_service(controller)

        assert result is None

    def it_should_return_service_when_receipts_dir_exists(self, tmp_path):
        controller = MagicMock()
        controller._event_store = MagicMock()

        with (
            patch("gilt.gui.controllers.receipt_match_controller.SettingsDialog") as mock_settings,
            patch("gilt.gui.controllers.receipt_match_controller.ReceiptMatchService") as mock_svc,
        ):
            mock_settings.get_receipts_dir.return_value = tmp_path

            result = ReceiptMatchController.get_service(controller)

        assert result == mock_svc.return_value
        mock_svc.assert_called_once_with(tmp_path, controller._event_store)

    def it_should_return_none_when_receipts_dir_missing(self, tmp_path):
        controller = MagicMock()
        controller._event_store = MagicMock()
        nonexistent = tmp_path / "nonexistent"

        with (
            patch("gilt.gui.controllers.receipt_match_controller.SettingsDialog") as mock_settings,
            patch("gilt.gui.controllers.receipt_match_controller.QMessageBox"),
        ):
            mock_settings.get_receipts_dir.return_value = nonexistent

            result = ReceiptMatchController.get_service(controller)

        assert result is None

    def it_should_return_empty_list_when_no_service(self):
        controller = MagicMock()
        controller.get_service.return_value = None

        txn_group = MagicMock()
        result = ReceiptMatchController.find_candidates(controller, txn_group)

        assert result == []


class DescribeSyncProjections:
    def it_should_call_ensure_projections_up_to_date(self):
        controller = MagicMock(spec=ReceiptMatchController)
        controller._es_service = MagicMock()
        controller._event_store = MagicMock()

        ReceiptMatchController._sync_projections(controller)

        controller._es_service.ensure_projections_up_to_date.assert_called_once_with(
            controller._event_store
        )

    def it_should_not_fail_when_no_es_service(self):
        controller = MagicMock(spec=ReceiptMatchController)
        controller._es_service = None
        controller._event_store = MagicMock()

        ReceiptMatchController._sync_projections(controller)

        controller.status_message.emit.assert_not_called()

    def it_should_not_fail_when_no_event_store(self):
        controller = MagicMock(spec=ReceiptMatchController)
        controller._es_service = MagicMock()
        controller._event_store = None

        ReceiptMatchController._sync_projections(controller)

        controller._es_service.ensure_projections_up_to_date.assert_not_called()

    def it_should_emit_warning_on_os_error(self):
        controller = MagicMock(spec=ReceiptMatchController)
        controller._es_service = MagicMock()
        controller._event_store = MagicMock()
        controller._es_service.ensure_projections_up_to_date.side_effect = OSError("fail")

        ReceiptMatchController._sync_projections(controller)

        controller.status_message.emit.assert_called_once()


class DescribeRunSingleMatch:
    def it_should_sync_projections_before_emitting_data_changed(self):
        controller = MagicMock(spec=ReceiptMatchController)
        controller._parent = None
        mock_svc = MagicMock()
        controller.get_service.return_value = mock_svc
        txn = MagicMock()
        txn.transaction_id = "abc123"
        txn.amount = -50.0
        txn.date = "2025-01-01"
        txn.description = "SAMPLE STORE"
        txn.account_id = "ACC1"
        txn.currency = "CAD"
        txn_group = MagicMock()
        txn_group.primary = txn
        mock_svc.find_candidates_for_transaction.return_value = []

        call_order = []
        controller._sync_projections.side_effect = lambda: call_order.append("sync")
        controller.data_changed.emit.side_effect = lambda _: call_order.append("emit")

        with (
            patch(
                "gilt.gui.controllers.receipt_match_controller.ReceiptMatchDialog"
            ) as mock_dialog_cls,
            patch("gilt.gui.controllers.receipt_match_controller.QMessageBox"),
        ):
            mock_dialog = mock_dialog_cls.return_value
            mock_dialog.exec.return_value = True
            receipt = MagicMock()
            mock_dialog.get_selected_receipt.return_value = receipt

            ReceiptMatchController.run_single_match(controller, [txn_group])

        assert call_order == ["sync", "emit"]


class DescribeRunBatchMatch:
    def it_should_sync_projections_once_before_emitting_data_changed(self):
        controller = MagicMock(spec=ReceiptMatchController)
        controller._parent = None
        mock_svc = MagicMock()
        controller.get_service.return_value = mock_svc

        result = MagicMock()
        result.matched = [MagicMock()]
        result.ambiguous = []
        result.unmatched = []
        mock_svc.run_batch_matching.return_value = result

        call_order = []
        controller._sync_projections.side_effect = lambda: call_order.append("sync")
        controller.data_changed.emit.side_effect = lambda _: call_order.append("emit")

        with (
            patch(
                "gilt.gui.controllers.receipt_match_controller.BatchReceiptMatchDialog"
            ) as mock_dialog_cls,
            patch("gilt.gui.controllers.receipt_match_controller.QMessageBox"),
        ):
            mock_dialog = mock_dialog_cls.return_value
            mock_dialog.exec.return_value = True
            resolved = MagicMock()
            resolved.match_confidence = "exact"
            resolved.receipt = MagicMock()
            resolved.transaction_id = "txn1"
            mock_dialog.get_resolved_matches.return_value = [resolved]

            ReceiptMatchController.run_batch_match(controller, [MagicMock()], None)

        assert call_order == ["sync", "emit"]
        controller._sync_projections.assert_called_once()


class DescribeRunMatchFromPanel:
    def it_should_sync_projections_before_emitting_data_changed(self):
        controller = MagicMock(spec=ReceiptMatchController)
        mock_svc = MagicMock()
        controller.get_service.return_value = mock_svc

        call_order = []
        controller._sync_projections.side_effect = lambda: call_order.append("sync")
        controller.data_changed.emit.side_effect = lambda _: call_order.append("emit")

        receipt = MagicMock()
        ReceiptMatchController.run_match_from_panel(controller, receipt, "txn42")

        assert call_order == ["sync", "emit"]
