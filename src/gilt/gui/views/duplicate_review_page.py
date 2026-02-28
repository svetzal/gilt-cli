from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from gilt.gui.services.import_service import ImportFileMapping, ImportService
from gilt.gui.theme import Theme
from gilt.model.duplicate import DuplicateMatch


class DuplicateReviewPage(QWizardPage):
    """Page for reviewing potential duplicates before import."""

    def __init__(self, service: ImportService):
        super().__init__()
        self.service = service
        self.mappings: list[ImportFileMapping] = []
        self.matches: list[DuplicateMatch] = []
        self.resolved_indices: set[int] = set()
        self.exclude_ids: set[str] = set()  # IDs to exclude from import

        self.setTitle("Review Potential Duplicates")
        self.setSubTitle(
            "The system detected transactions that might be duplicates. Please review them below."
        )

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Splitter for list and details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: List of matches
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Potential Duplicates:"))
        self.match_list = QListWidget()
        self.match_list.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.match_list)

        splitter.addWidget(left_widget)

        # Right: Details and Actions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        # Comparison Area
        self.comparison_frame = QFrame()
        self.comparison_frame.setFrameShape(QFrame.Shape.StyledPanel)
        comp_layout = QVBoxLayout(self.comparison_frame)

        # New Transaction (Incoming)
        comp_layout.addWidget(QLabel("<b>New Transaction (Incoming):</b>"))
        self.lbl_new_date = QLabel()
        self.lbl_new_desc = QLabel()
        self.lbl_new_amt = QLabel()
        comp_layout.addWidget(self.lbl_new_date)
        comp_layout.addWidget(self.lbl_new_desc)
        comp_layout.addWidget(self.lbl_new_amt)

        comp_layout.addSpacing(20)

        # Existing Transaction
        comp_layout.addWidget(QLabel("<b>Existing Transaction (In Ledger):</b>"))
        self.lbl_ex_date = QLabel()
        self.lbl_ex_desc = QLabel()
        self.lbl_ex_amt = QLabel()
        comp_layout.addWidget(self.lbl_ex_date)
        comp_layout.addWidget(self.lbl_ex_desc)
        comp_layout.addWidget(self.lbl_ex_amt)

        comp_layout.addStretch()

        # Reasoning
        comp_layout.addWidget(QLabel("<b>AI Reasoning:</b>"))
        self.lbl_reasoning = QLabel()
        self.lbl_reasoning.setWordWrap(True)
        comp_layout.addWidget(self.lbl_reasoning)

        right_layout.addWidget(self.comparison_frame)

        # Actions
        action_layout = QHBoxLayout()

        self.btn_confirm = QPushButton("Skip Import (It's a Duplicate)")
        self.btn_confirm.clicked.connect(self._on_confirm_duplicate)

        # Use theme colors
        neg_color = Theme.color("negative_fg").name()
        self.btn_confirm.setStyleSheet(
            f"background-color: {neg_color}26; "  # 15% opacity (approx 26 in hex)
            "color: palette(text); "
            f"border: 1px solid {neg_color}80; "  # 50% opacity
            "border-radius: 4px; padding: 6px;"
        )

        self.btn_reject = QPushButton("Import Anyway (Not a Duplicate)")
        self.btn_reject.clicked.connect(self._on_reject_duplicate)

        # Use theme colors
        pos_color = Theme.color("positive_fg").name()
        self.btn_reject.setStyleSheet(
            f"background-color: {pos_color}26; "  # 15% opacity
            "color: palette(text); "
            f"border: 1px solid {pos_color}80; "  # 50% opacity
            "border-radius: 4px; padding: 6px;"
        )

        action_layout.addWidget(self.btn_confirm)
        action_layout.addWidget(self.btn_reject)

        right_layout.addLayout(action_layout)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 500])

    def initializePage(self):
        """Called when page is shown."""
        self.matches = []
        self.resolved_indices.clear()
        self.exclude_ids.clear()
        self.match_list.clear()

        # Get mappings from wizard
        wizard = self.wizard()
        if wizard:
            # PAGE_ACCOUNT_MAPPING is 1
            mapping_page = wizard.page(1)
            if hasattr(mapping_page, "get_mappings"):
                self.mappings = mapping_page.get_mappings()  # type: ignore

        # Scan for duplicates
        # TODO: Show progress dialog if this takes time
        for mapping in self.mappings:
            if mapping.selected_account_id:
                file_matches = self.service.scan_file_for_duplicates(
                    mapping.file_info.path, mapping.selected_account_id
                )
                self.matches.extend(file_matches)

        if not self.matches:
            # No duplicates found
            self.match_list.addItem("No potential duplicates found.")
            self.match_list.setEnabled(False)
            self.comparison_frame.hide()
            self.btn_confirm.hide()
            self.btn_reject.hide()
        else:
            self.match_list.setEnabled(True)
            self.comparison_frame.show()
            self.btn_confirm.show()
            self.btn_reject.show()
            self._populate_list()
            self.match_list.setCurrentRow(0)

        self.completeChanged.emit()

    def _populate_list(self):
        self.match_list.clear()
        for i, match in enumerate(self.matches):
            status = ""
            if i in self.resolved_indices:
                status = " [Resolved]"

            item = QListWidgetItem(f"Match {i + 1} ({match.confidence_pct:.0f}%){status}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.match_list.addItem(item)

    def _on_selection_changed(self, row):
        if row < 0 or row >= len(self.matches):
            return

        match = self.matches[row]
        pair = match.pair

        # Update details
        self.lbl_new_date.setText(f"Date: {pair.txn1_date}")
        self.lbl_new_desc.setText(f"Desc: {pair.txn1_description}")
        self.lbl_new_amt.setText(f"Amount: {pair.txn1_amount}")

        self.lbl_ex_date.setText(f"Date: {pair.txn2_date}")
        self.lbl_ex_desc.setText(f"Desc: {pair.txn2_description}")
        self.lbl_ex_amt.setText(f"Amount: {pair.txn2_amount}")

        self.lbl_reasoning.setText(match.assessment.reasoning)

        # Enable/disable buttons if already resolved
        is_resolved = row in self.resolved_indices
        self.btn_confirm.setEnabled(not is_resolved)
        self.btn_reject.setEnabled(not is_resolved)

    def _on_confirm_duplicate(self):
        """User confirms it IS a duplicate -> Skip import."""
        row = self.match_list.currentRow()
        if row < 0:
            return

        match = self.matches[row]

        # Record decision
        if self.service.duplicate_service:
            # We keep the existing one (txn2)
            self.service.duplicate_service.resolve_duplicate(
                match, is_duplicate=True, keep_id=match.pair.txn2_id
            )

        # Add to exclude list (txn1 is the new one)
        self.exclude_ids.add(match.pair.txn1_id)

        self._mark_resolved(row)

    def _on_reject_duplicate(self):
        """User says NOT a duplicate -> Import it."""
        row = self.match_list.currentRow()
        if row < 0:
            return

        match = self.matches[row]

        # Record decision
        if self.service.duplicate_service:
            self.service.duplicate_service.resolve_duplicate(
                match, is_duplicate=False, rationale="User rejected in wizard"
            )

        self._mark_resolved(row)

    def _mark_resolved(self, row):
        self.resolved_indices.add(row)
        self._populate_list()
        self.match_list.setCurrentRow(row + 1 if row + 1 < len(self.matches) else row)
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        # Allow proceeding even if not all resolved?
        # Maybe warn if unresolved?
        # For now, allow proceeding. Unresolved ones will be imported (default behavior).
        return True

    def get_excluded_ids(self) -> set[str]:
        return self.exclude_ids
