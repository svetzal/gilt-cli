from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox, QWizard

from gilt.gui.services.import_service import FileInfo, ImportFileMapping
from gilt.gui.views.import_wizard import PAGE_EXECUTE, ImportWizard
from gilt.gui.views.import_wizard.pages.execute_page import ExecutePage
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
            preview_rows=[],
        )


class DescribeImportWizardLifecycle:
    """ImportWizard.reject() and accept() exercised against the real wizard."""

    def it_should_call_execute_page_cleanup_on_reject(self, qapp, monkeypatch):
        wizard = ImportWizard(_FakeImportService())
        cleanup_called = []
        monkeypatch.setattr(ExecutePage, "cleanupPage", lambda self: cleanup_called.append(True))

        wizard.reject()

        assert cleanup_called == [True]

    def it_should_accept_directly_when_import_successful(self, qapp, monkeypatch):
        wizard = ImportWizard(_FakeImportService())
        execute_page = wizard.page(PAGE_EXECUTE)
        execute_page.import_successful = True

        accepted = []
        monkeypatch.setattr(QWizard, "accept", lambda self: accepted.append(True))

        wizard.accept()

        assert accepted == [True]

    def it_should_prompt_user_when_import_was_unsuccessful(self, qapp, monkeypatch):
        wizard = ImportWizard(_FakeImportService())
        execute_page = wizard.page(PAGE_EXECUTE)
        execute_page.import_successful = False

        monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.Yes)
        accepted = []
        monkeypatch.setattr(QWizard, "accept", lambda self: accepted.append(True))

        wizard.accept()

        assert accepted == [True]

    def it_should_not_close_when_user_declines_after_failed_import(self, qapp, monkeypatch):
        wizard = ImportWizard(_FakeImportService())
        execute_page = wizard.page(PAGE_EXECUTE)
        execute_page.import_successful = False

        monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.No)
        accepted = []
        monkeypatch.setattr(QWizard, "accept", lambda self: accepted.append(True))

        wizard.accept()

        assert accepted == []
