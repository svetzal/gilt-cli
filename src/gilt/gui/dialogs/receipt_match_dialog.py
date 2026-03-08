"""
Receipt Match Dialog — lets users match receipts to transactions.

Supports two modes:
1. Single-transaction: find candidate receipts for one transaction and let user pick.
2. Batch: wizard-style flow through matched/ambiguous/unmatched results.
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gilt.services.receipt_ingestion_service import MatchResult, ReceiptData


class ReceiptMatchDialog(QDialog):
    """Dialog for matching a single transaction to candidate receipts."""

    def __init__(
        self,
        transaction_id: str,
        transaction_desc: str,
        transaction_amount: Decimal,
        transaction_date: str,
        candidates: list[ReceiptData],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Match Receipt")
        self.setMinimumWidth(550)
        self.setMinimumHeight(400)
        self.setModal(True)

        self._candidates = candidates
        self._selected_receipt: ReceiptData | None = None

        self._init_ui(transaction_id, transaction_desc, transaction_amount, transaction_date)

    def _init_ui(
        self,
        txn_id: str,
        txn_desc: str,
        txn_amount: Decimal,
        txn_date: str,
    ):
        layout = QVBoxLayout(self)

        # Transaction details
        txn_group = QGroupBox("Transaction")
        txn_layout = QVBoxLayout(txn_group)
        txn_layout.addWidget(QLabel(f"ID: {txn_id[:8]}"))
        txn_layout.addWidget(QLabel(f"Date: {txn_date}"))
        txn_layout.addWidget(QLabel(f"Description: {txn_desc}"))
        txn_layout.addWidget(QLabel(f"Amount: {txn_amount:.2f}"))
        layout.addWidget(txn_group)

        # Candidate receipts
        layout.addWidget(QLabel("Candidate receipts:"))

        if not self._candidates:
            no_match = QLabel("No matching receipts found.")
            no_match.setStyleSheet("color: gray; padding: 20px;")
            no_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_match)
        else:
            self._list = QListWidget()
            for receipt in self._candidates:
                text = self._format_receipt(receipt)
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, receipt)
                self._list.addItem(item)
            self._list.itemDoubleClicked.connect(self._on_double_click)
            layout.addWidget(self._list)

        # Buttons
        button_layout = QHBoxLayout()
        if self._candidates:
            select_btn = QPushButton("Select")
            select_btn.clicked.connect(self._on_select)
            button_layout.addWidget(select_btn)

        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(skip_btn)

        layout.addLayout(button_layout)

    def _format_receipt(self, receipt: ReceiptData) -> str:
        parts = [receipt.vendor]
        if receipt.service:
            parts.append(f"({receipt.service})")

        subtotal = receipt.amount
        tax = receipt.tax_amount or Decimal(0)
        total = subtotal + tax
        amount_str = f"${subtotal:.2f}"
        if tax:
            amount_str += f" + ${tax:.2f} {receipt.tax_type or 'tax'} = ${total:.2f}"
        parts.append(amount_str)

        parts.append(str(receipt.receipt_date))

        if receipt.invoice_number:
            parts.append(f"[{receipt.invoice_number}]")

        return "  |  ".join(parts)

    def _on_select(self):
        if not hasattr(self, "_list"):
            return
        current = self._list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a receipt.")
            return
        self._selected_receipt = current.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _on_double_click(self, item: QListWidgetItem):
        self._selected_receipt = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def get_selected_receipt(self) -> ReceiptData | None:
        """Return the receipt selected by the user, or None if skipped."""
        return self._selected_receipt


class BatchReceiptMatchDialog(QDialog):
    """Wizard-style dialog for batch receipt matching.

    Shows results in three phases: auto-matched, ambiguous (user picks), unmatched (info).
    Collects user decisions and returns all resolved matches.
    """

    def __init__(
        self,
        matched: list[MatchResult],
        ambiguous: list[MatchResult],
        unmatched: list[MatchResult],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Batch Receipt Matching")
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        self.setModal(True)

        self._matched = matched
        self._ambiguous = list(ambiguous)  # copy — we pop from it
        self._unmatched = unmatched

        # Results: all MatchResult objects that the user approved (auto + user-selected)
        self._resolved: list[MatchResult] = list(matched)

        self._current_ambiguous_index = 0

        self._init_ui()
        self._show_summary()

    def _init_ui(self):
        self._layout = QVBoxLayout(self)

        # Summary area (replaced during wizard steps)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._layout.addWidget(self._content)

        # Navigation buttons
        btn_layout = QHBoxLayout()
        self._proceed_btn = QPushButton("Proceed to Ambiguous")
        self._proceed_btn.clicked.connect(self._start_ambiguous)
        btn_layout.addWidget(self._proceed_btn)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self._next_ambiguous)
        self._skip_btn.setVisible(False)
        btn_layout.addWidget(self._skip_btn)

        self._done_btn = QPushButton("Done")
        self._done_btn.clicked.connect(self.accept)
        self._done_btn.setVisible(False)
        btn_layout.addWidget(self._done_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._layout.addLayout(btn_layout)

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_summary(self):
        self._clear_content()

        summary = QLabel(
            f"Auto-matched: {len(self._matched)}\n"
            f"Ambiguous (need review): {len(self._ambiguous)}\n"
            f"Unmatched: {len(self._unmatched)}"
        )
        summary.setStyleSheet("font-size: 14px; padding: 20px;")
        self._content_layout.addWidget(summary)

        if not self._ambiguous:
            self._proceed_btn.setVisible(False)
            self._done_btn.setVisible(True)

    def _start_ambiguous(self):
        self._proceed_btn.setVisible(False)
        self._skip_btn.setVisible(True)
        self._current_ambiguous_index = 0
        self._show_current_ambiguous()

    def _show_current_ambiguous(self):
        if self._current_ambiguous_index >= len(self._ambiguous):
            self._finish()
            return

        self._clear_content()
        result = self._ambiguous[self._current_ambiguous_index]
        receipt = result.receipt

        # Receipt info
        receipt_group = QGroupBox(
            f"Receipt {self._current_ambiguous_index + 1} of {len(self._ambiguous)}"
        )
        receipt_layout = QVBoxLayout(receipt_group)
        receipt_layout.addWidget(QLabel(f"Vendor: {receipt.vendor}"))
        if receipt.service:
            receipt_layout.addWidget(QLabel(f"Service: {receipt.service}"))

        subtotal = receipt.amount
        tax = receipt.tax_amount or Decimal(0)
        total = subtotal + tax
        amount_str = f"${subtotal:.2f}"
        if tax:
            amount_str += f" + ${tax:.2f} {receipt.tax_type or 'tax'} = ${total:.2f}"
        receipt_layout.addWidget(QLabel(f"Amount: {amount_str}"))
        receipt_layout.addWidget(QLabel(f"Date: {receipt.receipt_date}"))
        if receipt.invoice_number:
            receipt_layout.addWidget(QLabel(f"Invoice: {receipt.invoice_number}"))
        self._content_layout.addWidget(receipt_group)

        # Candidate transactions
        self._content_layout.addWidget(QLabel("Candidate transactions:"))
        self._ambiguous_list = QListWidget()
        for candidate in result.candidates:
            txid = candidate["transaction_id"][:8]
            txn_date = candidate.get("transaction_date", "")
            txn_amount = candidate.get("amount", "")
            desc = candidate.get("canonical_description", "")
            acct = candidate.get("account_id", "")
            text = f"{txid}  {txn_date}  ${txn_amount}  {desc}  [{acct}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, candidate)
            self._ambiguous_list.addItem(item)

        self._ambiguous_list.itemDoubleClicked.connect(self._on_ambiguous_select)
        self._content_layout.addWidget(self._ambiguous_list)

        # Select button
        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self._on_ambiguous_select_clicked)
        self._content_layout.addWidget(select_btn)

    def _on_ambiguous_select_clicked(self):
        current = self._ambiguous_list.currentItem()
        if not current:
            QMessageBox.warning(self, "No Selection", "Please select a transaction.")
            return
        self._resolve_current(current.data(Qt.ItemDataRole.UserRole))

    def _on_ambiguous_select(self, item: QListWidgetItem):
        self._resolve_current(item.data(Qt.ItemDataRole.UserRole))

    def _resolve_current(self, candidate: dict):
        result = self._ambiguous[self._current_ambiguous_index]
        resolved = MatchResult(
            receipt=result.receipt,
            status="matched",
            transaction_id=candidate["transaction_id"],
            candidate_count=result.candidate_count,
            current_description=candidate.get("canonical_description", ""),
            candidates=result.candidates,
            match_confidence="user-selected",
        )
        self._resolved.append(resolved)
        self._next_ambiguous()

    def _next_ambiguous(self):
        self._current_ambiguous_index += 1
        self._show_current_ambiguous()

    def _finish(self):
        self._clear_content()
        self._skip_btn.setVisible(False)
        self._done_btn.setVisible(True)

        summary = QLabel(
            f"Resolved: {len(self._resolved)} receipt(s) matched.\n"
            f"Click Done to apply."
        )
        summary.setStyleSheet("font-size: 14px; padding: 20px;")
        self._content_layout.addWidget(summary)

    def get_resolved_matches(self) -> list[MatchResult]:
        """Return all resolved match results (auto + user-selected)."""
        return self._resolved
