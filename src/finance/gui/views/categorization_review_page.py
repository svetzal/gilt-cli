from __future__ import annotations

from typing import List, Set

from PySide6.QtWidgets import (
    QWizardPage,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QProgressBar,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor, QBrush

from finance.gui.services.import_service import ImportService, ImportFileMapping, CategorizationReviewItem
from finance.gui.services.category_service import CategoryService
from finance.gui.dialogs.settings_dialog import SettingsDialog
from finance.gui.widgets.smart_category_combo import SmartCategoryComboBox
from finance.gui.theme import Theme


class CategorizationScanWorker(QThread):
    """Worker thread for scanning transactions for categorization."""

    progress = Signal(int)
    finished = Signal(list)  # List[CategorizationReviewItem]
    error = Signal(str)

    def __init__(
        self,
        service: ImportService,
        mappings: List[ImportFileMapping],
        exclude_ids: Set[str]
    ):
        super().__init__()
        self.service = service
        self.mappings = mappings
        self.exclude_ids = exclude_ids

    def run(self):
        try:
            all_items = []
            total_files = len(self.mappings)

            for i, mapping in enumerate(self.mappings):
                if not mapping.selected_account_id:
                    continue

                self.progress.emit(int((i / total_files) * 100))

                items = self.service.scan_file_for_categorization(
                    mapping.file_info.path,
                    mapping.selected_account_id,
                    exclude_ids=list(self.exclude_ids)
                )
                all_items.extend(items)

            self.progress.emit(100)
            self.finished.emit(all_items)

        except Exception as e:
            self.error.emit(str(e))


class CategorizationReviewPage(QWizardPage):
    """Page for reviewing auto-categorization suggestions."""

    def __init__(self, service: ImportService):
        super().__init__()
        self.service = service
        self.items: List[CategorizationReviewItem] = []
        self.mappings: List[ImportFileMapping] = []
        self.exclude_ids: Set[str] = set()

        # Load categories for dropdowns
        accounts_config = SettingsDialog.get_accounts_config()
        # Assuming categories.yml is in the same config dir
        categories_config = accounts_config.parent / "categories.yml"
        self.category_service = CategoryService(categories_config)
        self.all_categories = self.category_service.get_all_categories()

        self.setTitle("Review Categorization")
        self.setSubTitle(
            "Review and confirm category suggestions. "
            "Low confidence suggestions are highlighted."
        )

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Account", "Description", "Amount", "Suggested Category", "Confidence", "Confirm"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Legend
        legend_layout = QHBoxLayout()

        legend_layout.addWidget(QLabel("Legend:"))

        lbl_high = QLabel("High Confidence (>80%)")
        high_bg = Theme.color("success_bg").name()
        high_fg = Theme.color("success_fg").name()
        lbl_high.setStyleSheet(f"background-color: {high_bg}; color: {high_fg}; padding: 2px;")
        legend_layout.addWidget(lbl_high)

        lbl_low = QLabel("Low Confidence (<80%)")
        low_bg = Theme.color("warning_bg").name()
        low_fg = Theme.color("warning_fg").name()
        lbl_low.setStyleSheet(f"background-color: {low_bg}; color: {low_fg}; padding: 2px;")
        legend_layout.addWidget(lbl_low)

        legend_layout.addStretch()
        layout.addLayout(legend_layout)

    def initializePage(self):
        """Called when page is shown."""
        # Get mappings from previous pages
        wizard = self.wizard()
        if hasattr(wizard, "page"):
            mapping_page = wizard.page(1)  # PAGE_ACCOUNT_MAPPING
            if mapping_page:
                self.mappings = mapping_page.get_mappings()

            dup_page = wizard.page(3) # PAGE_DUPLICATE_REVIEW
            if dup_page:
                self.exclude_ids = dup_page.get_excluded_ids()

        self._start_scan()

    def _start_scan(self):
        """Start scanning for categorization."""
        self.table.setRowCount(0)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = CategorizationScanWorker(
            self.service, self.mappings, self.exclude_ids
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.error.connect(self._on_scan_error)
        self.worker.start()

    def _on_scan_finished(self, items: List[CategorizationReviewItem]):
        """Handle scan completion."""
        self.progress_bar.setVisible(False)
        self.items = items
        self._populate_table()

    def _on_scan_error(self, error: str):
        """Handle scan error."""
        self.progress_bar.setVisible(False)
        # Show error in table or label
        self.table.setRowCount(0)
        # Could show a message box or label

    def _populate_table(self):
        """Populate the table with items."""
        self.table.setRowCount(len(self.items))
        self.table.setSortingEnabled(False)

        for row, item in enumerate(self.items):
            # Date
            self.table.setItem(row, 0, QTableWidgetItem(str(item.transaction.date)))

            # Account
            self.table.setItem(row, 1, QTableWidgetItem(item.transaction.account_id))

            # Description
            self.table.setItem(row, 2, QTableWidgetItem(item.transaction.description))

            # Amount
            amt_item = QTableWidgetItem(f"{item.transaction.amount:.2f}")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, amt_item)

            # Category Dropdown
            combo = SmartCategoryComboBox()

            # Prepare suggestions
            suggestions = []
            if item.predicted_category:
                suggestions.append((item.predicted_category, item.confidence))

            # Prepare all categories
            all_cats = []
            for c in self.all_categories:
                all_cats.append(c.name)
                for sub in c.subcategories:
                    all_cats.append(f"{c.name}: {sub.name}")

            combo.set_categories(all_cats, suggestions, placeholder="-- Select --")

            # Set current selection
            current_val = item.assigned_category
            if item.assigned_category and item.assigned_subcategory:
                current_val = f"{item.assigned_category}: {item.assigned_subcategory}"
            
            if current_val:
                idx = combo.findData(current_val, Qt.ItemDataRole.UserRole)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            combo.currentIndexChanged.connect(lambda idx, r=row: self._on_category_changed(r, idx))
            self.table.setCellWidget(row, 4, combo)

            # Confidence
            conf_text = f"{item.confidence:.0%}"
            conf_item = QTableWidgetItem(conf_text)

            if item.confidence < 0.8:
                conf_item.setBackground(Theme.color("warning_bg"))
                conf_item.setForeground(Theme.color("warning_fg"))
            else:
                conf_item.setBackground(Theme.color("success_bg"))
                conf_item.setForeground(Theme.color("success_fg"))

            self.table.setItem(row, 5, conf_item)

            # Confirm Checkbox
            chk = QCheckBox()
            chk.setChecked(item.assigned_category is not None)
            chk.stateChanged.connect(lambda state, r=row: self._on_confirm_changed(r, state))
            self.table.setCellWidget(row, 6, chk)

            # Styling
            if item.confidence < 0.8:
                # Low confidence
                bg_color = Theme.color("warning_bg")
                fg_color = Theme.color("warning_fg")
            else:
                # High confidence
                bg_color = Theme.color("success_bg")
                fg_color = Theme.color("success_fg")

            for col in range(7):
                if col not in [4, 6]: # Skip widget columns
                    it = self.table.item(row, col)
                    if it:
                        it.setBackground(QBrush(bg_color))
                        it.setForeground(QBrush(fg_color))

        self.table.setSortingEnabled(True)

    def _on_category_changed(self, row: int, index: int):
        """Handle category selection change."""
        combo = self.table.cellWidget(row, 4)
        if not isinstance(combo, QComboBox):
            return

        category_str = combo.currentData()
        
        if category_str and ":" in category_str:
            parts = category_str.split(":", 1)
            self.items[row].assigned_category = parts[0].strip()
            self.items[row].assigned_subcategory = parts[1].strip()
        else:
            self.items[row].assigned_category = category_str
            self.items[row].assigned_subcategory = None

        # Auto-check confirm if category selected
        chk = self.table.cellWidget(row, 6)
        if isinstance(chk, QCheckBox):
            chk.setChecked(category_str is not None)

    def _on_confirm_changed(self, row: int, state: int):
        """Handle confirm checkbox change."""
        # If unchecked, maybe clear assignment? Or just keep it but don't apply?
        # For now, just track it.
        pass

    def get_categorization_decisions(self) -> List[CategorizationReviewItem]:
        """Get the final list of items with user decisions."""
        return self.items
