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

        with patch(
            "gilt.gui.controllers.receipt_match_controller.SettingsDialog"
        ) as mock_settings, patch(
            "gilt.gui.controllers.receipt_match_controller.ReceiptMatchService"
        ) as mock_svc:
            mock_settings.get_receipts_dir.return_value = tmp_path

            result = ReceiptMatchController.get_service(controller)

        assert result == mock_svc.return_value
        mock_svc.assert_called_once_with(tmp_path, controller._event_store)

    def it_should_return_none_when_receipts_dir_missing(self, tmp_path):
        controller = MagicMock()
        controller._event_store = MagicMock()
        nonexistent = tmp_path / "nonexistent"

        with patch(
            "gilt.gui.controllers.receipt_match_controller.SettingsDialog"
        ) as mock_settings, patch(
            "gilt.gui.controllers.receipt_match_controller.QMessageBox"
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
