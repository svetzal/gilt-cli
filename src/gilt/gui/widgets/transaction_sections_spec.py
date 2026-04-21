from __future__ import annotations

"""Specs for transaction_sections free functions — PySide6 required."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import QApplication, QFormLayout, QGroupBox, QLabel

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.gui.widgets.transaction_sections import (
    build_basics_section,
    build_enrichment_section,
    build_transfer_section,
)
from gilt.model.account import Transaction
from gilt.transfer import (
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_METHOD,
    TRANSFER_ROLE,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _make_label(text: str) -> QLabel:
    label = QLabel(text)
    return label


def _make_txn(**kwargs) -> Transaction:
    defaults = dict(
        transaction_id="abc12345deadbeef",
        date=date(2025, 3, 15),
        description="SAMPLE STORE ANYTOWN",
        amount=-42.50,
        currency="CAD",
        account_id="MYBANK_CHQ",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def _form_rows(group: QGroupBox) -> list[tuple[str, str]]:
    """Extract (label_text, value_text) pairs from a QGroupBox with a QFormLayout."""
    layout = group.layout()
    assert isinstance(layout, QFormLayout)
    rows = []
    for i in range(layout.rowCount()):
        label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
        field_item = layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
        label_text = label_item.widget().text() if label_item and label_item.widget() else ""
        field_widget = field_item.widget() if field_item else None
        field_text = field_widget.text() if isinstance(field_widget, QLabel) else ""
        rows.append((label_text, field_text))
    return rows


class DescribeBuildBasicsSection:
    def it_should_return_a_qgroupbox_with_transaction_title(self, qapp):
        txn = _make_txn()

        group = build_basics_section(_make_label, txn)

        assert isinstance(group, QGroupBox)
        assert group.title() == "Transaction"

    def it_should_include_transaction_id_row(self, qapp):
        txn = _make_txn(transaction_id="abc12345deadbeef")

        group = build_basics_section(_make_label, txn)
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Transaction ID:" in labels

    def it_should_include_amount_row_with_currency(self, qapp):
        txn = _make_txn(amount=-42.50, currency="CAD")

        group = build_basics_section(_make_label, txn)
        rows = _form_rows(group)

        amount_values = [v for lbl, v in rows if lbl == "Amount:"]
        assert amount_values == ["-42.50 CAD"]

    def it_should_include_category_row_when_category_set(self, qapp):
        txn = _make_txn(category="Food")

        group = build_basics_section(_make_label, txn)
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Category:" in labels

    def it_should_include_subcategory_in_category_row(self, qapp):
        txn = _make_txn(category="Food", subcategory="Groceries")

        group = build_basics_section(_make_label, txn)
        rows = _form_rows(group)

        cat_values = [v for lbl, v in rows if lbl == "Category:"]
        assert cat_values == ["Food: Groceries"]

    def it_should_omit_category_row_when_category_is_none(self, qapp):
        txn = _make_txn(category=None)

        group = build_basics_section(_make_label, txn)
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Category:" not in labels

    def it_should_apply_form_setup_fn_when_provided(self, qapp):
        txn = _make_txn()
        applied = []

        def setup(form):
            applied.append(form)

        build_basics_section(_make_label, txn, form_setup_fn=setup)

        assert len(applied) == 1

    def it_should_use_description_label_fn_for_description_row_when_provided(self, qapp):
        txn = _make_txn(description="SAMPLE STORE ANYTOWN")
        used_alt = []

        def alt_label(text: str) -> QLabel:
            used_alt.append(text)
            return QLabel(text)

        build_basics_section(_make_label, txn, description_label_fn=alt_label)

        assert "SAMPLE STORE ANYTOWN" in used_alt

    def it_should_fall_back_to_label_fn_for_description_when_no_description_label_fn(self, qapp):
        txn = _make_txn(description="SAMPLE STORE ANYTOWN")
        used_labels = []

        def tracking_label(text: str) -> QLabel:
            used_labels.append(text)
            return QLabel(text)

        build_basics_section(tracking_label, txn)

        assert "SAMPLE STORE ANYTOWN" in used_labels


class DescribeBuildEnrichmentSection:
    def it_should_return_a_qgroupbox_with_receipt_enrichment_title(self, qapp):
        enrichment = EnrichmentData(vendor="ACME CORP", enrichment_source="test.json")

        group = build_enrichment_section(_make_label, enrichment, "CAD")

        assert isinstance(group, QGroupBox)
        assert group.title() == "Receipt Enrichment"

    def it_should_include_vendor_row(self, qapp):
        enrichment = EnrichmentData(vendor="ACME CORP", enrichment_source="test.json")

        group = build_enrichment_section(_make_label, enrichment, "CAD")
        rows = _form_rows(group)

        vendor_values = [v for lbl, v in rows if lbl == "Vendor:"]
        assert vendor_values == ["ACME CORP"]

    def it_should_include_service_row_when_set(self, qapp):
        enrichment = EnrichmentData(
            vendor="ACME CORP", service="Widget Pro", enrichment_source="test.json"
        )

        group = build_enrichment_section(_make_label, enrichment, "CAD")
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Service:" in labels

    def it_should_omit_service_row_when_none(self, qapp):
        enrichment = EnrichmentData(vendor="ACME CORP", service=None, enrichment_source="test.json")

        group = build_enrichment_section(_make_label, enrichment, "CAD")
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Service:" not in labels

    def it_should_include_tax_row_with_type_when_set(self, qapp):
        enrichment = EnrichmentData(
            vendor="ACME CORP",
            tax_amount=Decimal("5.53"),
            tax_type="HST",
            enrichment_source="test.json",
        )

        group = build_enrichment_section(_make_label, enrichment, "CAD")
        rows = _form_rows(group)

        tax_values = [v for lbl, v in rows if lbl == "Tax:"]
        assert tax_values == ["5.53 (HST)"]

    def it_should_omit_receipt_currency_row_when_same_as_txn_currency(self, qapp):
        enrichment = EnrichmentData(
            vendor="ACME CORP", currency="CAD", enrichment_source="test.json"
        )

        group = build_enrichment_section(_make_label, enrichment, "CAD")
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Receipt currency:" not in labels

    def it_should_include_receipt_currency_row_when_different_from_txn_currency(self, qapp):
        enrichment = EnrichmentData(
            vendor="ACME CORP", currency="USD", enrichment_source="test.json"
        )

        group = build_enrichment_section(_make_label, enrichment, "CAD")
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Receipt currency:" in labels


class DescribeBuildTransferSection:
    def it_should_return_a_qgroupbox_with_transfer_link_title(self, qapp):
        transfer = {TRANSFER_ROLE: "source"}

        group = build_transfer_section(_make_label, transfer)

        assert isinstance(group, QGroupBox)
        assert group.title() == "Transfer Link"

    def it_should_include_role_row_when_present(self, qapp):
        transfer = {TRANSFER_ROLE: "source"}

        group = build_transfer_section(_make_label, transfer)
        rows = _form_rows(group)

        role_values = [v for lbl, v in rows if lbl == "Role:"]
        assert role_values == ["source"]

    def it_should_include_counterparty_account_row_when_present(self, qapp):
        transfer = {TRANSFER_COUNTERPARTY_ACCOUNT_ID: "BANK2_CHQ"}

        group = build_transfer_section(_make_label, transfer)
        rows = _form_rows(group)

        labels = [r[0] for r in rows]
        assert "Counterparty account:" in labels

    def it_should_include_method_row_when_present(self, qapp):
        transfer = {TRANSFER_METHOD: "EFT"}

        group = build_transfer_section(_make_label, transfer)
        rows = _form_rows(group)

        method_values = [v for lbl, v in rows if lbl == "Method:"]
        assert method_values == ["EFT"]

    def it_should_omit_rows_for_missing_transfer_keys(self, qapp):
        transfer = {}

        group = build_transfer_section(_make_label, transfer)
        rows = _form_rows(group)

        assert rows == []
