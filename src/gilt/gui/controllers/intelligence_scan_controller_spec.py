import pytest

pytest.importorskip("PySide6")

from unittest.mock import MagicMock

from gilt.gui.controllers.intelligence_scan_controller import IntelligenceScanController


class DescribeIntelligenceScanCallbacks:
    def it_should_update_cache_and_emit_signals_on_finish(self):
        controller = MagicMock()
        metadata = {"t1": {"risk": True}}

        IntelligenceScanController._on_scan_finished(controller, metadata)

        controller._intelligence_cache.update.assert_called_once_with(metadata)
        controller.metadata_updated.emit.assert_called_once_with(metadata)
        controller.status_message.emit.assert_called_once_with("Intelligence scan complete")
        controller.scan_finished.emit.assert_called_once()

    def it_should_emit_error_message_and_finished_on_error(self):
        controller = MagicMock()
        error_msg = "Connection failed"

        IntelligenceScanController._on_scan_error(controller, error_msg)

        controller.status_message.emit.assert_called_once_with(error_msg)
        controller.scan_finished.emit.assert_called_once()


class DescribeWorkerLifecycle:
    def it_should_disconnect_all_signals_from_worker(self):
        controller = MagicMock()
        worker = MagicMock()

        IntelligenceScanController._disconnect_all_worker_signals(controller, worker)

        worker.finished.disconnect.assert_called_once()
        worker.error.disconnect.assert_called_once()
        worker.status.disconnect.assert_called_once()
        worker.progress.disconnect.assert_called_once()

    def it_should_interrupt_and_wait_for_running_worker(self):
        controller = MagicMock()
        controller._old_workers = []
        worker = MagicMock()
        worker.isRunning.return_value = True
        controller.worker = worker

        IntelligenceScanController.stop(controller)

        controller._disconnect_all_worker_signals.assert_called_once_with(worker)
        worker.requestInterruption.assert_called_once()
        worker.wait.assert_called_once_with(3000)
        assert controller.worker is None

    def it_should_handle_no_worker_gracefully(self):
        controller = MagicMock()
        controller.worker = None
        controller._old_workers = []

        IntelligenceScanController.stop(controller)

        assert controller.worker is None

    def it_should_clear_old_workers(self):
        controller = MagicMock()
        controller.worker = None
        old_worker = MagicMock()
        old_worker.isRunning.return_value = False
        controller._old_workers = [old_worker]

        IntelligenceScanController.stop(controller)

        old_worker.wait.assert_called()
        assert controller._old_workers == []
