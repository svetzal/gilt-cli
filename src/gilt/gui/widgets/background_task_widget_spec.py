from __future__ import annotations

import pytest


def _has_display():
    try:
        from PySide6.QtWidgets import QApplication

        # Check if we can create or access a QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _has_display(), reason="No display available")


def _make_widget():
    from gilt.gui.widgets.background_task_widget import BackgroundTaskWidget

    return BackgroundTaskWidget()


class DescribeBackgroundTaskWidget:
    def it_should_be_hidden_initially(self):
        widget = _make_widget()
        assert not widget.isVisible()

    def it_should_show_on_start_task(self):
        widget = _make_widget()
        widget.start_task("Scanning...", 10)
        assert widget.isVisible()
        assert widget._label.text() == "Scanning..."
        assert widget._progress_bar.maximum() == 10
        assert widget._progress_bar.value() == 0

    def it_should_update_progress(self):
        widget = _make_widget()
        widget.start_task("Working...", 5)
        widget.update_progress(3, 5)
        assert widget._progress_bar.value() == 3
        assert widget._progress_bar.maximum() == 5

    def it_should_update_status_text(self):
        widget = _make_widget()
        widget.start_task("Phase 1...", 10)
        widget.update_status("Phase 2...")
        assert widget._label.text() == "Phase 2..."

    def it_should_hide_on_finish(self):
        widget = _make_widget()
        widget.start_task("Working...", 5)
        widget.finish_task()
        assert not widget.isVisible()

    def it_should_reset_progress_on_new_task(self):
        widget = _make_widget()
        widget.start_task("First task", 10)
        widget.update_progress(7, 10)
        widget.start_task("Second task", 20)
        assert widget._progress_bar.value() == 0
        assert widget._progress_bar.maximum() == 20
        assert widget._label.text() == "Second task"
