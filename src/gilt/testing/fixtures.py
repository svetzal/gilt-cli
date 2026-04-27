from __future__ import annotations

from datetime import date

from gilt.model.account import Transaction, TransactionGroup
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair


def make_transaction(**kwargs) -> Transaction:
    """Factory for Transaction with sensible synthetic defaults.

    Accepts keyword arguments to override any Transaction field.
    """
    defaults = dict(
        transaction_id="aabbccdd11223344",
        date=date(2025, 3, 10),
        description="SAMPLE STORE ANYTOWN",
        amount=-42.50,
        currency="CAD",
        account_id="MYBANK_CHQ",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def make_group(**kwargs) -> TransactionGroup:
    """Factory for TransactionGroup with sensible synthetic defaults.

    Accepts either:
    - A pre-built primary Transaction via primary=txn (uses it directly)
    - Transaction field kwargs (builds a Transaction internally via make_transaction)

    Group-specific kwargs: splits, group_id, tolerance
    All other kwargs are passed to make_transaction.
    """
    group_kwargs = {}
    txn_kwargs = {}

    for key, value in kwargs.items():
        if key in ("splits", "group_id", "tolerance"):
            group_kwargs[key] = value
        else:
            txn_kwargs[key] = value

    txn = kwargs["primary"] if "primary" in kwargs else make_transaction(**txn_kwargs)

    group_id = group_kwargs.get("group_id", txn.transaction_id)
    splits = group_kwargs.get("splits", [])
    tolerance = group_kwargs.get("tolerance", 0.01)

    return TransactionGroup(
        group_id=group_id,
        primary=txn,
        splits=splits,
        tolerance=tolerance,
    )


def make_pair(**kwargs) -> TransactionPair:
    """Factory for TransactionPair with sensible synthetic defaults.

    Accepts keyword arguments to override any TransactionPair field.
    """
    defaults = dict(
        txn1_id="aaaa111100000001",
        txn1_date=date(2025, 4, 10),
        txn1_description="ACME CORP PAYMENT",
        txn1_amount=-200.00,
        txn1_account="MYBANK_CHQ",
        txn2_id="bbbb222200000002",
        txn2_date=date(2025, 4, 10),
        txn2_description="ACME CORP PMT",
        txn2_amount=-200.00,
        txn2_account="MYBANK_CHQ",
    )
    defaults.update(kwargs)
    return TransactionPair(**defaults)


def make_match(**kwargs) -> DuplicateMatch:
    """Factory for DuplicateMatch with sensible synthetic defaults.

    Accepts keyword arguments to override any TransactionPair or
    DuplicateAssessment field.

    TransactionPair field kwargs:
    - txn1_id, txn1_date, txn1_description, txn1_amount, txn1_account, txn1_source_file
    - txn2_id, txn2_date, txn2_description, txn2_amount, txn2_account, txn2_source_file

    DuplicateAssessment field kwargs:
    - is_duplicate, confidence, reasoning
    """
    pair_kwargs = {}
    assessment_kwargs = {}

    for key, value in kwargs.items():
        if key in ("is_duplicate", "confidence", "reasoning"):
            assessment_kwargs[key] = value
        else:
            pair_kwargs[key] = value

    pair_defaults = dict(
        txn1_id="aaaa111100000001",
        txn1_date=date(2025, 4, 10),
        txn1_description="ACME CORP PAYMENT",
        txn1_amount=-200.00,
        txn1_account="MYBANK_CHQ",
        txn2_id="bbbb222200000002",
        txn2_date=date(2025, 4, 10),
        txn2_description="ACME CORP PMT",
        txn2_amount=-200.00,
        txn2_account="MYBANK_CHQ",
    )
    pair_defaults.update(pair_kwargs)
    pair = TransactionPair(**pair_defaults)

    assessment_defaults = dict(
        is_duplicate=True,
        confidence=0.88,
        reasoning="Same amount on same date with similar descriptions.",
    )
    assessment_defaults.update(assessment_kwargs)
    assessment = DuplicateAssessment(**assessment_defaults)

    return DuplicateMatch(pair=pair, assessment=assessment)


__all__ = [
    "make_transaction",
    "make_group",
    "make_pair",
    "make_match",
]
