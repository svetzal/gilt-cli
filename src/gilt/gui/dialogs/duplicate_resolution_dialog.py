from __future__ import annotations

"""
Duplicate Resolution Dialog - Dialog for resolving potential duplicates.

Shows two transactions side-by-side and asks user to confirm if they are duplicates.
"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QLabel,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gilt.gui.theme import Theme
from gilt.model.duplicate import DuplicateMatch


class DuplicateResolutionDialog(QDialog):
    """Dialog for resolving a potential duplicate match."""

    def __init__(self, match: DuplicateMatch, parent=None):
        """
        Initialize dialog.

        Args:
            match: The duplicate match to resolve
            parent: Parent widget
        """
        super().__init__(parent)
        self.match = match
        self.result_is_duplicate = False
        self.result_keep_id = None

        self.setWindowTitle("Resolve Duplicate")
        self.setMinimumWidth(800)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        self._create_header_section(layout)
        self._create_comparison_table(layout)
        self._create_resolution_options(layout)
        self._create_dialog_buttons(layout)

    def _create_header_section(self, layout) -> None:
        """Add the title label and confidence info label to layout."""
        header = QLabel("Potential Duplicate Detected")
        header.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        conf_text = f"Confidence: {self.match.confidence_pct:.1f}%"
        if self.match.assessment.reasoning:
            conf_text += f"\nReasoning: {self.match.assessment.reasoning}"

        info_label = QLabel(conf_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            f"background-color: {Theme.color('header_bg').name()}; padding: 10px; border-radius: 4px;"
        )
        layout.addWidget(info_label)

    def _create_comparison_table(self, layout) -> None:
        """Create and configure the side-by-side comparison table and add it to layout."""
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Field", "Transaction A", "Transaction B"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        pair = self.match.pair
        fields = [
            ("Date", str(pair.txn1_date), str(pair.txn2_date)),
            ("Description", pair.txn1_description, pair.txn2_description),
            ("Amount", f"{pair.txn1_amount:.2f}", f"{pair.txn2_amount:.2f}"),
            ("Account", pair.txn1_account, pair.txn2_account),
            ("ID", pair.txn1_id[:8], pair.txn2_id[:8]),
        ]

        self.table.setRowCount(len(fields))
        for row, (field, val1, val2) in enumerate(fields):
            self.table.setItem(row, 0, QTableWidgetItem(field))
            self.table.setItem(row, 1, QTableWidgetItem(val1))
            self.table.setItem(row, 2, QTableWidgetItem(val2))

            if val1 != val2:
                item1 = self.table.item(row, 1)
                item2 = self.table.item(row, 2)
                if item1:
                    item1.setForeground(Theme.color("negative_fg"))
                if item2:
                    item2.setForeground(Theme.color("negative_fg"))

        layout.addWidget(self.table)

    def _create_resolution_options(self, layout) -> None:
        """Create the resolution QGroupBox with radio buttons and add it to layout."""
        group = QGroupBox("Resolution")
        group_layout = QVBoxLayout(group)

        self.radio_duplicate = QRadioButton("Yes, these are duplicates")
        self.radio_duplicate.setChecked(True)
        group_layout.addWidget(self.radio_duplicate)

        self.keep_group = QButtonGroup(self)

        self.radio_keep_1 = QRadioButton("Keep Transaction A (Delete B)")
        self.radio_keep_1.setChecked(True)
        self.keep_group.addButton(self.radio_keep_1)

        self.radio_keep_2 = QRadioButton("Keep Transaction B (Delete A)")
        self.keep_group.addButton(self.radio_keep_2)

        sub_layout = QVBoxLayout()
        sub_layout.setContentsMargins(20, 0, 0, 0)
        sub_layout.addWidget(self.radio_keep_1)
        sub_layout.addWidget(self.radio_keep_2)
        group_layout.addLayout(sub_layout)

        self.radio_different = QRadioButton("No, these are different transactions")
        group_layout.addWidget(self.radio_different)

        self.radio_duplicate.toggled.connect(self._on_duplicate_toggled)

        layout.addWidget(group)

    def _create_dialog_buttons(self, layout) -> None:
        """Create the OK/Cancel button box, connect signals, and add it to layout."""
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _on_duplicate_toggled(self, checked):
        """Enable/disable keep options based on duplicate selection."""
        self.radio_keep_1.setEnabled(checked)
        self.radio_keep_2.setEnabled(checked)

    def _on_accept(self):
        """Handle dialog acceptance."""
        self.result_is_duplicate = self.radio_duplicate.isChecked()

        if self.result_is_duplicate:
            if self.radio_keep_1.isChecked():
                self.result_keep_id = self.match.pair.txn1_id
            else:
                self.result_keep_id = self.match.pair.txn2_id

        self.accept()

    def get_resolution(self) -> tuple[bool, str | None]:
        """
        Get resolution result.

        Returns:
            Tuple of (is_duplicate, keep_id)
        """
        return self.result_is_duplicate, self.result_keep_id
