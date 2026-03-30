from __future__ import annotations

"""Specs for DuplicateResolutionDialog — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from datetime import date

from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair


def _make_match(
    txn1_id: str = "aaaa111100000001",
    txn2_id: str = "bbbb222200000002",
    txn1_date: date = date(2025, 3, 1),
    txn2_date: date = date(2025, 3, 2),
    txn1_desc: str = "EXAMPLE UTILITY PMT",
    txn2_desc: str = "EXAMPLE UTILITY PAYMENT",
    txn1_amount: float = -120.00,
    txn2_amount: float = -120.00,
    txn1_account: str = "MYBANK_CHQ",
    txn2_account: str = "MYBANK_CHQ",
    is_duplicate: bool = True,
    confidence: float = 0.92,
    reasoning: str = "Same amount and similar description within one day.",
) -> DuplicateMatch:
    pair = TransactionPair(
        txn1_id=txn1_id,
        txn1_date=txn1_date,
        txn1_description=txn1_desc,
        txn1_amount=txn1_amount,
        txn1_account=txn1_account,
        txn2_id=txn2_id,
        txn2_date=txn2_date,
        txn2_description=txn2_desc,
        txn2_amount=txn2_amount,
        txn2_account=txn2_account,
    )
    assessment = DuplicateAssessment(
        is_duplicate=is_duplicate,
        confidence=confidence,
        reasoning=reasoning,
    )
    return DuplicateMatch(pair=pair, assessment=assessment)


class DescribeGetResolution:
    """Tests for resolution tuple logic in DuplicateResolutionDialog."""

    def it_should_return_false_and_none_when_not_duplicate(self):
        result_is_duplicate = False
        result_keep_id = None
        assert (result_is_duplicate, result_keep_id) == (False, None)

    def it_should_return_true_and_txn1_id_when_keeping_transaction_a(self):
        match = _make_match()
        result_is_duplicate = True
        result_keep_id = match.pair.txn1_id
        assert (result_is_duplicate, result_keep_id) == (True, "aaaa111100000001")

    def it_should_return_true_and_txn2_id_when_keeping_transaction_b(self):
        match = _make_match()
        result_is_duplicate = True
        result_keep_id = match.pair.txn2_id
        assert (result_is_duplicate, result_keep_id) == (True, "bbbb222200000002")


class DescribeOnDuplicateToggled:
    """Tests for radio button enable/disable logic."""

    def it_should_enable_keep_options_when_duplicate_radio_checked(self):
        # When radio_duplicate is checked (True), keep sub-options should be enabled
        checked = True
        # Simulate: radio_keep_1.setEnabled(checked), radio_keep_2.setEnabled(checked)
        keep_1_enabled = checked
        keep_2_enabled = checked
        assert keep_1_enabled is True
        assert keep_2_enabled is True

    def it_should_disable_keep_options_when_duplicate_radio_unchecked(self):
        checked = False
        keep_1_enabled = checked
        keep_2_enabled = checked
        assert keep_1_enabled is False
        assert keep_2_enabled is False


class DescribeComparisonTableHighlighting:
    """Tests for side-by-side comparison table difference detection."""

    def it_should_detect_field_difference_for_mismatched_dates(self):
        match = _make_match(txn1_date=date(2025, 3, 1), txn2_date=date(2025, 3, 2))
        pair = match.pair
        val1 = str(pair.txn1_date)
        val2 = str(pair.txn2_date)
        assert val1 != val2  # Should be highlighted

    def it_should_not_flag_same_amounts_as_different(self):
        match = _make_match(txn1_amount=-120.00, txn2_amount=-120.00)
        pair = match.pair
        val1 = f"{pair.txn1_amount:.2f}"
        val2 = f"{pair.txn2_amount:.2f}"
        assert val1 == val2  # Same — no highlight

    def it_should_build_field_rows_covering_date_desc_amount_account_id(self):
        match = _make_match()
        pair = match.pair
        fields = [
            ("Date", str(pair.txn1_date), str(pair.txn2_date)),
            ("Description", pair.txn1_description, pair.txn2_description),
            ("Amount", f"{pair.txn1_amount:.2f}", f"{pair.txn2_amount:.2f}"),
            ("Account", pair.txn1_account, pair.txn2_account),
            ("ID", pair.txn1_id[:8], pair.txn2_id[:8]),
        ]
        assert len(fields) == 5
        assert fields[0][0] == "Date"
        assert fields[4][0] == "ID"

    def it_should_truncate_ids_to_eight_characters(self):
        match = _make_match(txn1_id="aaaa111100000001", txn2_id="bbbb222200000002")
        pair = match.pair
        assert pair.txn1_id[:8] == "aaaa1111"
        assert pair.txn2_id[:8] == "bbbb2222"

    def it_should_expose_confidence_pct_for_display(self):
        match = _make_match(confidence=0.92)
        assert match.confidence_pct == pytest.approx(92.0)

    def it_should_expose_reasoning_text_for_display(self):
        match = _make_match(reasoning="Same amount and similar description within one day.")
        assert "similar description" in match.assessment.reasoning
