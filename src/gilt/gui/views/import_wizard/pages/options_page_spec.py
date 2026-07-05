from __future__ import annotations

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.gui.views.import_wizard.pages.options_page import OptionsPage


class DescribeOptionsPage:
    """OptionsPage.get_write_enabled() exercised against the real widget."""

    def it_should_default_to_dry_run_mode(self, qapp):
        page = OptionsPage()
        assert page.get_write_enabled() is False

    def it_should_report_write_enabled_after_checkbox_is_checked(self, qapp):
        page = OptionsPage()
        page.write_check.setChecked(True)
        assert page.get_write_enabled() is True
