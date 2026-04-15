from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from gilt.transfer.conftest import write_ledger_from_dicts
from gilt.transfer.matching import (
    Txn,
    _amount_closeness,
    _date_proximity,
    _filter_candidate_others,
    _find_nearby_fees,
    _select_best_match,
    _try_match_for_debit,
    _valid_sign_pair,
    compute_matches,
    score_pair,
)


def it_should_match_direct_same_day_and_capture_fee(tmp_path: Path):
    # Build two ledgers with a clear transfer and a nearby fee on the debit side
    a1 = tmp_path / "A1.csv"
    a2 = tmp_path / "A2.csv"

    debit_id = "d1" * 8
    credit_id = "c1" * 8
    fee_id = "f1" * 8

    write_ledger_from_dicts(
        a1,
        [
            {
                "transaction_id": debit_id,
                "date": "2025-01-01",
                "description": "INTERAC E-TRANSFER",
                "amount": -100.00,
                "currency": "CAD",
                "account_id": "A1",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "a1.csv",
            },
            {
                "transaction_id": fee_id,
                "date": "2025-01-01",
                "description": "INTERAC FEE",
                "amount": -1.50,
                "currency": "CAD",
                "account_id": "A1",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "a1.csv",
            },
        ],
    )
    write_ledger_from_dicts(
        a2,
        [
            {
                "transaction_id": credit_id,
                "date": "2025-01-01",
                "description": "INTERAC E-TRANSFER",
                "amount": 100.00,
                "currency": "CAD",
                "account_id": "A2",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "a2.csv",
            }
        ],
    )

    matches = compute_matches(tmp_path)
    assert len(matches) == 1
    m = matches[0]
    assert m.debit.transaction_id == debit_id
    assert m.credit.transaction_id == credit_id
    assert m.method == "direct_same_day"
    assert m.score >= 0.95
    assert fee_id in set(m.fee_txn_ids)


def it_should_allow_bank2_biz_loc_same_sign_pair(tmp_path: Path):
    # Special-case: same-sign allowed for BANK2_BIZ <-> BANK2_LOC
    sc_curr = tmp_path / "BANK2_BIZ.csv"
    sc_loc = tmp_path / "BANK2_LOC.csv"

    d_id = "d2" * 8
    c_id = "c2" * 8

    write_ledger_from_dicts(
        sc_curr,
        [
            {
                "transaction_id": d_id,
                "date": "2025-02-02",
                "description": "MOVE FUNDS",
                "amount": -200.00,
                "currency": "CAD",
                "account_id": "BANK2_BIZ",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "curr.csv",
            }
        ],
    )
    write_ledger_from_dicts(
        sc_loc,
        [
            {
                "transaction_id": c_id,
                "date": "2025-02-02",
                "description": "MOVE FUNDS",
                "amount": -200.00,  # same sign
                "currency": "CAD",
                "account_id": "BANK2_LOC",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "loc.csv",
            }
        ],
    )

    matches = compute_matches(tmp_path)
    assert len(matches) == 1
    m = matches[0]
    assert m.debit.account_id == "BANK2_BIZ"
    assert m.credit.account_id == "BANK2_LOC"
    assert m.method in {"direct_same_day", "window_interac"}


def _make_txn(
    idx=0,
    transaction_id="tid",
    date=None,
    amount=-100.0,
    currency="CAD",
    account_id="A1",
    description="INTERAC E-TRANSFER",
    source_file="a.csv",
) -> Txn:
    if date is None:
        date = datetime(2025, 1, 1)
    return Txn(
        idx=idx,
        transaction_id=transaction_id,
        date=date,
        amount=amount,
        currency=currency,
        account_id=account_id,
        description=description,
        source_file=source_file,
    )


class DescribeTxnSignChecks:
    def it_should_report_debit_for_negative_amount(self):
        txn = _make_txn(amount=-50.0)

        assert txn.is_debit() is True
        assert txn.is_credit() is False

    def it_should_report_credit_for_positive_amount(self):
        txn = _make_txn(amount=50.0)

        assert txn.is_debit() is False
        assert txn.is_credit() is True

    def it_should_report_neither_for_zero_amount(self):
        txn = _make_txn(amount=0.0)

        assert txn.is_debit() is False
        assert txn.is_credit() is False


class DescribeTxnDescHash8:
    def it_should_return_8_char_hex_string(self):
        txn = _make_txn(description="INTERAC E-TRANSFER")

        result = txn.desc_hash8

        assert len(result) == 8
        assert all(c in "0123456789abcdef" for c in result)

    def it_should_produce_different_hashes_for_different_inputs(self):
        txn_a = _make_txn(description="INTERAC E-TRANSFER")
        txn_b = _make_txn(description="MOVE FUNDS")

        assert txn_a.desc_hash8 != txn_b.desc_hash8

    def it_should_be_deterministic(self):
        txn = _make_txn(description="INTERAC E-TRANSFER")

        assert txn.desc_hash8 == txn.desc_hash8


class DescribeTxnHasDescToken:
    def it_should_return_true_when_token_exactly_present(self):
        txn = _make_txn(description="INTERAC E-TRANSFER")

        assert txn.has_desc_token(["INTERAC"]) is True

    def it_should_be_case_insensitive(self):
        txn = _make_txn(description="Interac e-transfer")

        assert txn.has_desc_token(["INTERAC"]) is True

    def it_should_return_false_when_token_absent(self):
        txn = _make_txn(description="MOVE FUNDS")

        assert txn.has_desc_token(["INTERAC"]) is False

    def it_should_return_false_for_empty_description(self):
        txn = _make_txn(description="")

        assert txn.has_desc_token(["INTERAC"]) is False

    def it_should_match_fee_as_substring(self):
        txn = _make_txn(description="INTERAC FEE")

        assert txn.has_desc_token(["FEE"]) is True


class DescribeAmountCloseness:
    def it_should_return_1_for_exact_match(self):
        assert _amount_closeness(-100.0, 100.0, 0.01) == 1.0

    def it_should_return_1_when_diff_within_epsilon(self):
        assert _amount_closeness(-100.0, 101.50, 1.75) == 1.0

    def it_should_return_decaying_score_beyond_epsilon(self):
        result = _amount_closeness(-100.0, 103.0, 1.75)

        assert 0.0 < result < 1.0

    def it_should_return_1_for_zero_epsilon_exact_match(self):
        assert _amount_closeness(-100.0, 100.0, 0.0) == 1.0

    def it_should_return_0_for_zero_epsilon_any_difference(self):
        assert _amount_closeness(-100.0, 101.0, 0.0) == 0.0

    def it_should_return_0_for_far_apart_amounts(self):
        assert _amount_closeness(-100.0, 200.0, 1.75) == 0.0


class DescribeDateProximity:
    def it_should_return_1_for_same_day(self):
        d = datetime(2025, 1, 1)

        assert _date_proximity(d, d, window_days=3) == 1.0

    def it_should_return_approx_two_thirds_for_one_day_window_three(self):
        a = datetime(2025, 1, 1)
        b = datetime(2025, 1, 2)

        result = _date_proximity(a, b, window_days=3)

        assert result == pytest.approx(1.0 - 1 / 3)

    def it_should_return_0_beyond_window(self):
        a = datetime(2025, 1, 1)
        b = datetime(2025, 1, 5)

        assert _date_proximity(a, b, window_days=3) == 0.0

    def it_should_return_0_exactly_at_window_edge(self):
        a = datetime(2025, 1, 1)
        b = datetime(2025, 1, 4)

        assert _date_proximity(a, b, window_days=3) == 0.0


class DescribeFindNearbyFees:
    def it_should_find_fee_in_same_account_within_window(self):
        debit = _make_txn(
            transaction_id="d1",
            date=datetime(2025, 1, 1),
            amount=-100.0,
            account_id="MYBANK_CHQ",
        )
        fee = _make_txn(
            transaction_id="f1",
            date=datetime(2025, 1, 1),
            amount=-1.50,
            account_id="MYBANK_CHQ",
            description="INTERAC FEE",
        )

        result = _find_nearby_fees(debit, [debit, fee], fee_max=3.00, day_window=1)

        assert fee in result

    def it_should_exclude_fee_in_different_account(self):
        debit = _make_txn(
            transaction_id="d1", date=datetime(2025, 1, 1), account_id="MYBANK_CHQ", amount=-100.0
        )
        fee = _make_txn(
            transaction_id="f1",
            date=datetime(2025, 1, 1),
            amount=-1.50,
            account_id="MYBANK_CC",
            description="INTERAC FEE",
        )

        result = _find_nearby_fees(debit, [debit, fee], fee_max=3.00, day_window=1)

        assert fee not in result

    def it_should_exclude_fee_outside_date_window(self):
        debit = _make_txn(
            transaction_id="d1", date=datetime(2025, 1, 1), account_id="MYBANK_CHQ", amount=-100.0
        )
        fee = _make_txn(
            transaction_id="f1",
            date=datetime(2025, 1, 5),
            amount=-1.50,
            account_id="MYBANK_CHQ",
            description="INTERAC FEE",
        )

        result = _find_nearby_fees(debit, [debit, fee], fee_max=3.00, day_window=1)

        assert fee not in result

    def it_should_exclude_fee_above_fee_max(self):
        debit = _make_txn(
            transaction_id="d1", date=datetime(2025, 1, 1), account_id="MYBANK_CHQ", amount=-100.0
        )
        fee = _make_txn(
            transaction_id="f1",
            date=datetime(2025, 1, 1),
            amount=-5.00,
            account_id="MYBANK_CHQ",
            description="INTERAC FEE",
        )

        result = _find_nearby_fees(debit, [debit, fee], fee_max=3.00, day_window=1)

        assert fee not in result

    def it_should_exclude_debit_itself(self):
        debit = _make_txn(
            transaction_id="d_fee",
            date=datetime(2025, 1, 1),
            amount=-1.50,
            account_id="MYBANK_CHQ",
            description="INTERAC FEE",
        )

        result = _find_nearby_fees(debit, [debit], fee_max=3.00, day_window=1)

        assert result == []


class DescribeScorePair:
    def it_should_return_1_for_perfect_match(self):
        debit = _make_txn(
            transaction_id="d1",
            date=datetime(2025, 1, 1),
            amount=-100.0,
            description="INTERAC E-TRANSFER",
        )
        credit = _make_txn(
            transaction_id="c1",
            date=datetime(2025, 1, 1),
            amount=100.0,
            description="INTERAC E-TRANSFER",
        )

        result = score_pair(debit, credit, epsilon=0.01, window_days=3)

        assert result == pytest.approx(1.0)

    def it_should_reduce_score_when_no_desc_token(self):
        debit = _make_txn(amount=-100.0, date=datetime(2025, 1, 1), description="PAYMENT")
        credit = _make_txn(amount=100.0, date=datetime(2025, 1, 1), description="PAYMENT")

        result = score_pair(debit, credit, epsilon=0.01, window_days=3)

        assert result < 1.0

    def it_should_apply_weights_correctly(self):
        debit = _make_txn(amount=-100.0, date=datetime(2025, 1, 1), description="PAYMENT")
        credit = _make_txn(amount=100.0, date=datetime(2025, 1, 1), description="PAYMENT")

        result = score_pair(debit, credit, epsilon=0.01, window_days=3)

        assert result == pytest.approx(0.9)


class DescribeValidSignPair:
    def it_should_be_valid_for_opposite_signs(self):
        debit = _make_txn(amount=-100.0, account_id="A1")
        credit = _make_txn(amount=100.0, account_id="A2")

        assert _valid_sign_pair(debit, credit) is True

    def it_should_be_invalid_for_same_signs_normal_accounts(self):
        debit = _make_txn(amount=-100.0, account_id="A1")
        other = _make_txn(amount=-100.0, account_id="A2")

        assert _valid_sign_pair(debit, other) is False

    def it_should_be_valid_for_bank2_biz_loc_same_sign(self):
        debit = _make_txn(amount=-200.0, account_id="BANK2_BIZ")
        other = _make_txn(amount=-200.0, account_id="BANK2_LOC")

        assert _valid_sign_pair(debit, other) is True

    def it_should_be_valid_for_bank2_loc_biz_order_independent(self):
        debit = _make_txn(amount=-200.0, account_id="BANK2_LOC")
        other = _make_txn(amount=-200.0, account_id="BANK2_BIZ")

        assert _valid_sign_pair(debit, other) is True


class DescribeFilterCandidateOthers:
    def it_should_include_valid_credit_from_different_account(self):
        d = _make_txn(transaction_id="d1", account_id="A1", amount=-100.0, currency="CAD")
        credit = _make_txn(
            transaction_id="c1",
            account_id="A2",
            amount=100.0,
            currency="CAD",
            description="INTERAC E-TRANSFER",
        )
        txns_by_ccy = {"CAD": [d, credit]}

        result = _filter_candidate_others(d, txns_by_ccy, set())

        assert credit in result

    def it_should_exclude_transaction_from_same_account(self):
        d = _make_txn(transaction_id="d1", account_id="A1", amount=-100.0, currency="CAD")
        same_account = _make_txn(
            transaction_id="s1", account_id="A1", amount=100.0, currency="CAD"
        )
        txns_by_ccy = {"CAD": [d, same_account]}

        result = _filter_candidate_others(d, txns_by_ccy, set())

        assert same_account not in result

    def it_should_exclude_already_matched_transaction(self):
        d = _make_txn(transaction_id="d1", account_id="A1", amount=-100.0, currency="CAD")
        matched = _make_txn(transaction_id="m1", account_id="A2", amount=100.0, currency="CAD")
        txns_by_ccy = {"CAD": [d, matched]}

        result = _filter_candidate_others(d, txns_by_ccy, {"m1"})

        assert matched not in result

    def it_should_exclude_transaction_with_excluded_token(self):
        d = _make_txn(transaction_id="d1", account_id="A1", amount=-100.0, currency="CAD")
        overdraft = _make_txn(
            transaction_id="o1",
            account_id="A2",
            amount=100.0,
            currency="CAD",
            description="OVERDRAFT",
        )
        txns_by_ccy = {"CAD": [d, overdraft]}

        result = _filter_candidate_others(d, txns_by_ccy, set())

        assert overdraft not in result

    def it_should_exclude_invalid_sign_pair(self):
        d = _make_txn(transaction_id="d1", account_id="A1", amount=-100.0, currency="CAD")
        same_sign = _make_txn(
            transaction_id="s1",
            account_id="A2",
            amount=-100.0,
            currency="CAD",
            description="INTERAC E-TRANSFER",
        )
        txns_by_ccy = {"CAD": [d, same_sign]}

        result = _filter_candidate_others(d, txns_by_ccy, set())

        assert same_sign not in result


class DescribeSelectBestMatch:
    def it_should_return_same_day_candidate_above_threshold(self):
        d = _make_txn(
            transaction_id="d1",
            date=datetime(2025, 1, 1),
            amount=-100.0,
            description="INTERAC E-TRANSFER",
        )
        credit = _make_txn(
            transaction_id="c1",
            date=datetime(2025, 1, 1),
            amount=100.0,
            description="INTERAC E-TRANSFER",
            account_id="A2",
        )

        result = _select_best_match(
            d, [credit], epsilon_direct=0.01, epsilon_interac=1.75, window_days=3
        )

        assert result is not None
        txn, score, method = result
        assert txn.transaction_id == "c1"
        assert method == "direct_same_day"

    def it_should_prefer_same_day_over_window_candidate(self):
        d = _make_txn(
            transaction_id="d1",
            date=datetime(2025, 1, 1),
            amount=-100.0,
            description="INTERAC E-TRANSFER",
        )
        credit_same_day = _make_txn(
            transaction_id="c_same",
            date=datetime(2025, 1, 1),
            amount=100.0,
            description="INTERAC E-TRANSFER",
            account_id="A2",
        )
        credit_next_day = _make_txn(
            transaction_id="c_next",
            date=datetime(2025, 1, 2),
            amount=100.0,
            description="INTERAC E-TRANSFER",
            account_id="A2",
        )

        result = _select_best_match(
            d,
            [credit_same_day, credit_next_day],
            epsilon_direct=0.01,
            epsilon_interac=1.75,
            window_days=3,
        )

        assert result is not None
        _, _, method = result
        assert method == "direct_same_day"

    def it_should_return_window_candidate_when_no_same_day_match(self):
        d = _make_txn(
            transaction_id="d1",
            date=datetime(2025, 1, 1),
            amount=-100.0,
            description="INTERAC E-TRANSFER",
        )
        credit = _make_txn(
            transaction_id="c1",
            date=datetime(2025, 1, 2),
            amount=100.0,
            description="INTERAC E-TRANSFER",
            account_id="A2",
        )

        result = _select_best_match(
            d, [credit], epsilon_direct=0.01, epsilon_interac=1.75, window_days=3
        )

        assert result is not None
        _, _, method = result
        assert method == "window_interac"

    def it_should_return_none_when_no_candidate_passes_threshold(self):
        d = _make_txn(
            transaction_id="d1",
            date=datetime(2025, 1, 1),
            amount=-100.0,
            description="INTERAC E-TRANSFER",
        )
        far_credit = _make_txn(
            transaction_id="c1",
            date=datetime(2025, 1, 6),
            amount=50.0,
            description="OTHER",
            account_id="A2",
        )

        result = _select_best_match(
            d, [far_credit], epsilon_direct=0.01, epsilon_interac=1.75, window_days=3
        )

        assert result is None


class DescribeTryMatchForDebit:
    def it_should_return_none_for_excluded_token_description(self):
        d = _make_txn(
            transaction_id="d1",
            amount=-100.0,
            description="OVERDRAFT",
            account_id="MYBANK_CHQ",
        )
        txns_by_ccy: dict[str, list[Txn]] = {"CAD": [d]}

        result = _try_match_for_debit(
            d,
            txns_by_ccy=txns_by_ccy,
            matched_other_ids=set(),
            all_txns=[d],
            epsilon_direct=0.01,
            epsilon_interac=1.75,
            window_days=3,
            fee_max_amount=3.00,
            fee_day_window=1,
        )

        assert result is None

    def it_should_return_none_when_no_matching_candidates(self):
        d = _make_txn(
            transaction_id="d1",
            amount=-100.0,
            description="INTERAC E-TRANSFER",
            account_id="MYBANK_CHQ",
        )
        same_account = _make_txn(
            transaction_id="s1",
            amount=100.0,
            description="INTERAC E-TRANSFER",
            account_id="MYBANK_CHQ",
        )
        txns_by_ccy = {"CAD": [d, same_account]}

        result = _try_match_for_debit(
            d,
            txns_by_ccy=txns_by_ccy,
            matched_other_ids=set(),
            all_txns=[d, same_account],
            epsilon_direct=0.01,
            epsilon_interac=1.75,
            window_days=3,
            fee_max_amount=3.00,
            fee_day_window=1,
        )

        assert result is None

    def it_should_return_match_with_fee_when_valid(self):
        d = _make_txn(
            transaction_id="d1",
            date=datetime(2025, 1, 1),
            amount=-100.0,
            description="INTERAC E-TRANSFER",
            account_id="MYBANK_CHQ",
        )
        credit = _make_txn(
            transaction_id="c1",
            date=datetime(2025, 1, 1),
            amount=100.0,
            description="INTERAC E-TRANSFER",
            account_id="MYBANK_CC",
        )
        fee = _make_txn(
            transaction_id="f1",
            date=datetime(2025, 1, 1),
            amount=-1.50,
            description="INTERAC FEE",
            account_id="MYBANK_CHQ",
        )
        all_txns = [d, credit, fee]
        txns_by_ccy = {"CAD": all_txns}

        result = _try_match_for_debit(
            d,
            txns_by_ccy=txns_by_ccy,
            matched_other_ids=set(),
            all_txns=all_txns,
            epsilon_direct=0.01,
            epsilon_interac=1.75,
            window_days=3,
            fee_max_amount=3.00,
            fee_day_window=1,
        )

        assert result is not None
        assert result.debit.transaction_id == "d1"
        assert result.credit.transaction_id == "c1"
        assert "f1" in result.fee_txn_ids
