from __future__ import annotations

"""
Specifications for duplicate detection models.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair


def _make_pair(**kwargs) -> TransactionPair:
    defaults = dict(
        txn1_id="aabbccdd11223344",
        txn1_date=date(2025, 1, 10),
        txn1_description="EXAMPLE UTILITY PAYMENT",
        txn1_amount=-120.00,
        txn1_account="MYBANK_CHQ",
        txn2_id="eeff00112233aabb",
        txn2_date=date(2025, 1, 10),
        txn2_description="EXAMPLE UTILITY PMT",
        txn2_amount=-120.00,
        txn2_account="MYBANK_CHQ",
    )
    defaults.update(kwargs)
    return TransactionPair(**defaults)


class DescribeTransactionPair:
    """Validation behaviour of the TransactionPair model."""

    def it_should_create_valid_pair_with_all_required_fields(self):
        pair = _make_pair()
        assert pair.txn1_id == "aabbccdd11223344"
        assert pair.txn2_id == "eeff00112233aabb"
        assert pair.txn1_amount == -120.00
        assert pair.txn2_amount == -120.00

    def it_should_allow_optional_source_file_fields(self):
        pair = _make_pair(txn1_source_file="2025-01-mybank.csv", txn2_source_file=None)
        assert pair.txn1_source_file == "2025-01-mybank.csv"
        assert pair.txn2_source_file is None

    def it_should_default_source_file_fields_to_none(self):
        pair = _make_pair()
        assert pair.txn1_source_file is None
        assert pair.txn2_source_file is None

    def it_should_accept_date_objects_for_transaction_dates(self):
        pair = _make_pair(txn1_date=date(2025, 6, 15), txn2_date=date(2025, 6, 16))
        assert pair.txn1_date == date(2025, 6, 15)
        assert pair.txn2_date == date(2025, 6, 16)

    def it_should_reject_missing_required_txn1_id(self):
        with pytest.raises((ValidationError, TypeError)):
            TransactionPair(
                txn1_date=date(2025, 1, 1),
                txn1_description="DESC",
                txn1_amount=-10.0,
                txn1_account="MYBANK_CHQ",
                txn2_id="eeff0011",
                txn2_date=date(2025, 1, 1),
                txn2_description="DESC",
                txn2_amount=-10.0,
                txn2_account="MYBANK_CHQ",
            )

    def it_should_store_float_amounts(self):
        pair = _make_pair(txn1_amount=-42.75, txn2_amount=-42.75)
        assert pair.txn1_amount == -42.75
        assert pair.txn2_amount == -42.75


class DescribeDuplicateAssessment:
    """Behaviour of DuplicateAssessment including confidence normalization."""

    def it_should_accept_confidence_as_decimal_fraction(self):
        assessment = DuplicateAssessment(is_duplicate=True, confidence=0.95, reasoning="Same txn")
        assert assessment.confidence == 0.95

    def it_should_normalize_confidence_percentage_to_fraction(self):
        """Confidence values > 1.0 are treated as percentages and scaled to 0-1."""
        assessment = DuplicateAssessment(is_duplicate=True, confidence=95.0, reasoning="Same txn")
        assert assessment.confidence == pytest.approx(0.95)

    def it_should_normalize_confidence_of_100_to_1_0(self):
        assessment = DuplicateAssessment(is_duplicate=True, confidence=100.0, reasoning="Certain")
        assert assessment.confidence == pytest.approx(1.0)

    def it_should_keep_confidence_of_exactly_1_0_unchanged(self):
        assessment = DuplicateAssessment(is_duplicate=True, confidence=1.0, reasoning="Certain")
        assert assessment.confidence == 1.0

    def it_should_keep_confidence_of_0_0_unchanged(self):
        assessment = DuplicateAssessment(is_duplicate=False, confidence=0.0, reasoning="Uncertain")
        assert assessment.confidence == 0.0

    def it_should_reject_confidence_below_zero(self):
        with pytest.raises(ValidationError):
            DuplicateAssessment(is_duplicate=False, confidence=-0.1, reasoning="Invalid")

    def it_should_reject_confidence_above_1_when_not_a_percentage(self):
        """Values just above 1.0 that aren't percentages (e.g. 1.5) are still normalized."""
        # 1.5 > 1.0 so it gets normalized to 0.015, which is valid
        assessment = DuplicateAssessment(is_duplicate=False, confidence=1.5, reasoning="odd")
        assert assessment.confidence == pytest.approx(0.015)

    def it_should_store_reasoning_text(self):
        assessment = DuplicateAssessment(
            is_duplicate=True, confidence=0.9, reasoning="Amounts match exactly"
        )
        assert assessment.reasoning == "Amounts match exactly"

    def it_should_require_all_fields(self):
        with pytest.raises(ValidationError):
            DuplicateAssessment(is_duplicate=True)


class DescribeDuplicateMatch:
    """Behaviour of DuplicateMatch including the confidence_pct property."""

    @pytest.fixture
    def match(self):
        pair = _make_pair()
        assessment = DuplicateAssessment(
            is_duplicate=True, confidence=0.85, reasoning="High similarity"
        )
        return DuplicateMatch(pair=pair, assessment=assessment)

    def it_should_return_confidence_as_percentage(self, match):
        assert match.confidence_pct == pytest.approx(85.0)

    def it_should_return_100_for_full_confidence(self):
        pair = _make_pair()
        assessment = DuplicateAssessment(is_duplicate=True, confidence=1.0, reasoning="Exact")
        m = DuplicateMatch(pair=pair, assessment=assessment)
        assert m.confidence_pct == pytest.approx(100.0)

    def it_should_return_0_for_zero_confidence(self):
        pair = _make_pair()
        assessment = DuplicateAssessment(
            is_duplicate=False, confidence=0.0, reasoning="Not a match"
        )
        m = DuplicateMatch(pair=pair, assessment=assessment)
        assert m.confidence_pct == pytest.approx(0.0)

    def it_should_compute_confidence_pct_as_int_times_100(self):
        """Verify the property formula: confidence * 100."""
        pair = _make_pair()
        assessment = DuplicateAssessment(is_duplicate=True, confidence=0.73, reasoning="Likely")
        m = DuplicateMatch(pair=pair, assessment=assessment)
        assert m.confidence_pct == pytest.approx(73.0)

    def it_should_expose_pair_and_assessment(self, match):
        assert match.pair.txn1_id == "aabbccdd11223344"
        assert match.assessment.is_duplicate is True
