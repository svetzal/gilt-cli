import pytest

pytest.importorskip("PySide6")

from pathlib import Path
from unittest.mock import MagicMock, patch

from gilt.gui.main_window import MainWindow


class DescribeOnNavChanged:
    def it_should_set_content_stack_index_0_for_nav_0(self):
        window = MagicMock()

        MainWindow._on_nav_changed(window, 0)

        window.content_stack.setCurrentIndex.assert_called_once_with(0)

    def it_should_set_content_stack_index_1_for_nav_1(self):
        window = MagicMock()

        MainWindow._on_nav_changed(window, 1)

        window.content_stack.setCurrentIndex.assert_called_once_with(1)

    def it_should_set_content_stack_index_2_for_nav_2(self):
        window = MagicMock()

        MainWindow._on_nav_changed(window, 2)

        window.content_stack.setCurrentIndex.assert_called_once_with(2)

    def it_should_set_content_stack_index_3_for_nav_3(self):
        window = MagicMock()

        MainWindow._on_nav_changed(window, 3)

        window.content_stack.setCurrentIndex.assert_called_once_with(3)

    def it_should_not_set_content_stack_for_invalid_index(self):
        window = MagicMock()

        MainWindow._on_nav_changed(window, -1)

        window.content_stack.setCurrentIndex.assert_not_called()


class DescribeOnNavigateToView:
    def it_should_set_both_stack_and_nav_list(self):
        window = MagicMock()

        MainWindow._on_navigate_to_view(window, 2)

        window.content_stack.setCurrentIndex.assert_called_once_with(2)
        window.nav_list.setCurrentRow.assert_called_once_with(2)


class DescribeRefreshCurrentView:
    def it_should_reload_dashboard_for_index_0(self):
        window = MagicMock()
        window.content_stack.currentIndex.return_value = 0

        MainWindow._refresh_current_view(window)

        window.dashboard_view.reload_dashboard.assert_called_once()

    def it_should_reload_transactions_for_index_1(self):
        window = MagicMock()
        window.content_stack.currentIndex.return_value = 1

        MainWindow._refresh_current_view(window)

        window.transactions_view.reload_transactions.assert_called_once()

    def it_should_load_categories_for_index_2(self):
        window = MagicMock()
        window.content_stack.currentIndex.return_value = 2

        MainWindow._refresh_current_view(window)

        window.categories_view._load_categories.assert_called_once()

    def it_should_reload_budget_for_index_3(self):
        window = MagicMock()
        window.content_stack.currentIndex.return_value = 3

        MainWindow._refresh_current_view(window)

        window.budget_view.reload_budget.assert_called_once()


class DescribeShowImportWizard:
    def it_should_reload_transactions_after_wizard_accepted(self):
        window = MagicMock()
        window.workspace = MagicMock()
        window.data_dir = Path("/tmp/data")

        with patch("gilt.gui.main_window.SettingsDialog"), patch(
            "gilt.gui.main_window.EventSourcingService"
        ), patch("gilt.gui.main_window.DuplicateDetector"), patch(
            "gilt.gui.main_window.DuplicateService"
        ), patch(
            "gilt.gui.main_window.CategorizationClassifier"
        ), patch(
            "gilt.gui.main_window.SmartCategoryService"
        ), patch(
            "gilt.gui.main_window.ImportService"
        ), patch(
            "gilt.gui.main_window.ImportWizard"
        ) as mock_wizard_cls:
            mock_wizard_cls.return_value.exec.return_value = True

            MainWindow._show_import_wizard(window)

        window.transactions_view.reload_transactions.assert_called_once()

    def it_should_not_reload_after_wizard_rejected(self):
        window = MagicMock()
        window.workspace = MagicMock()
        window.data_dir = Path("/tmp/data")

        with patch("gilt.gui.main_window.SettingsDialog"), patch(
            "gilt.gui.main_window.EventSourcingService"
        ), patch("gilt.gui.main_window.DuplicateDetector"), patch(
            "gilt.gui.main_window.DuplicateService"
        ), patch(
            "gilt.gui.main_window.CategorizationClassifier"
        ), patch(
            "gilt.gui.main_window.SmartCategoryService"
        ), patch(
            "gilt.gui.main_window.ImportService"
        ), patch(
            "gilt.gui.main_window.ImportWizard"
        ) as mock_wizard_cls:
            mock_wizard_cls.return_value.exec.return_value = False

            MainWindow._show_import_wizard(window)

        window.transactions_view.reload_transactions.assert_not_called()
