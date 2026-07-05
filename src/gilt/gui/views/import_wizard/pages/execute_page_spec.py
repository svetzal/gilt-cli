from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.gui.services.import_service import FileInfo, ImportFileMapping, ImportResult
from gilt.gui.views.import_wizard.pages.execute_page import ExecutePage
from gilt.gui.workers.import_worker import ImportWorker
from gilt.model.account import Account


class _FakeImportService:
    def load_accounts(self):
        return [Account(account_id="MYBANK_CHQ"), Account(account_id="MYBANK_CC")]

    def build_file_mapping(self, file_path: Path, max_preview_rows: int = 5) -> ImportFileMapping:
        detected = Account(account_id="MYBANK_CHQ")
        file_info = FileInfo(
            path=file_path,
            name=file_path.name,
            size=1024,
            modified_date=date(2025, 1, 15),
        )
        return ImportFileMapping(
            file_info=file_info,
            detected_account=detected,
            selected_account_id="MYBANK_CHQ",
            preview_rows=[
                {"date": "2025-01-15", "amount": "-42.00", "description": "EXAMPLE UTILITY"},
            ],
        )


def _make_file_info(name: str = "sample.csv") -> FileInfo:
    return FileInfo(
        path=Path(f"/tmp/{name}"),
        name=name,
        size=512,
        modified_date=date(2025, 1, 15),
    )


def _make_mapping(
    name: str = "sample.csv",
    account_id: str | None = "MYBANK_CHQ",
    preview_rows: list | None = None,
    error: str | None = None,
) -> ImportFileMapping:
    return ImportFileMapping(
        file_info=_make_file_info(name),
        detected_account=Account(account_id=account_id) if account_id else None,
        selected_account_id=account_id,
        preview_rows=preview_rows if preview_rows is not None else [],
        error=error,
    )


class DescribeExecutePageImportFlow:
    """ExecutePage shell logic exercised with a patched ImportWorker.start."""

    def it_should_log_dry_run_mode_and_set_worker(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(_FakeImportService(), [mapping], write=False)

        assert page.worker is not None
        assert "DRY-RUN" in page.log_text.toPlainText()

    def it_should_log_write_mode_when_write_enabled(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(_FakeImportService(), [mapping], write=True)

        assert "WRITE" in page.log_text.toPlainText()

    def it_should_log_duplicate_skip_count_when_exclude_ids_present(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(
            _FakeImportService(), [mapping], write=False, exclude_ids={"tx001", "tx002"}
        )

        assert "2 duplicate" in page.log_text.toPlainText()

    def it_should_log_categorization_count_when_map_present(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(
            _FakeImportService(),
            [mapping],
            write=False,
            categorization_map={"tx001": "Groceries", "tx002": "Transport"},
        )

        assert "2 category" in page.log_text.toPlainText()

    def it_should_set_import_complete_and_successful_on_finished_success(self, qapp):
        page = ExecutePage()
        result = ImportResult(
            success=True,
            imported_count=5,
            duplicate_count=2,
            error_count=0,
            messages=["Processed sample.csv"],
        )

        page._on_finished(result)

        assert page.import_complete is True
        assert page.import_successful is True
        assert page.isComplete() is True

    def it_should_include_transaction_count_in_success_summary(self, qapp):
        page = ExecutePage()
        result = ImportResult(
            success=True,
            imported_count=7,
            duplicate_count=1,
            error_count=0,
            messages=[],
        )

        page._on_finished(result)

        assert "7 transaction(s)" in page.summary_label.text()

    def it_should_set_import_unsuccessful_on_finished_failure(self, qapp):
        page = ExecutePage()
        result = ImportResult(
            success=False,
            imported_count=0,
            duplicate_count=0,
            error_count=1,
            messages=["Parse error"],
        )

        page._on_finished(result)

        assert page.import_complete is True
        assert page.import_successful is False

    def it_should_set_import_unsuccessful_on_error(self, qapp):
        page = ExecutePage()

        page._on_error("Connection refused")

        assert page.import_complete is True
        assert page.import_successful is False
        assert "Connection refused" in page.summary_label.text()

    def it_should_wire_signals_so_finished_emit_reaches_on_finished(self, qapp, monkeypatch):
        """Signals wired in _start_import: emit on worker triggers the handler."""
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(_FakeImportService(), [mapping], write=False)

        result = ImportResult(
            success=True, imported_count=3, duplicate_count=0, error_count=0, messages=[]
        )
        page.worker.finished.emit(result)

        assert page.import_complete is True
        assert page.import_successful is True


class DescribeExecutePageCleanup:
    """ExecutePage.cleanupPage() must follow the documented QThread lifecycle."""

    def it_should_disconnect_signals_before_interrupting_running_worker(self, qapp):
        operations: list[str] = []

        class _FakeSignal:
            def __init__(self, name):
                self._name = name

            def disconnect(self, fn):
                operations.append(f"disconnect({self._name})")

        class _FakeWorker:
            def __init__(self):
                self.progress = _FakeSignal("progress")
                self.finished = _FakeSignal("finished")
                self.error = _FakeSignal("error")

            def isRunning(self):
                return True

            def requestInterruption(self):
                operations.append("requestInterruption")

            def wait(self, ms):
                operations.append(f"wait({ms})")

        page = ExecutePage()
        page.worker = _FakeWorker()
        page.cleanupPage()

        interrupt_idx = operations.index("requestInterruption")
        assert operations.index("disconnect(progress)") < interrupt_idx
        assert operations.index("disconnect(finished)") < interrupt_idx
        assert operations.index("disconnect(error)") < interrupt_idx
        assert "wait(2000)" in operations

    def it_should_be_noop_when_worker_is_none(self, qapp):
        page = ExecutePage()
        page.worker = None
        page.cleanupPage()  # must not raise

    def it_should_be_noop_when_worker_is_not_running(self, qapp):
        class _FakeWorker:
            def isRunning(self):
                return False

        page = ExecutePage()
        page.worker = _FakeWorker()
        page.cleanupPage()  # must not raise
