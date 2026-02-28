from __future__ import annotations

from pathlib import Path

import pandas as pd

from gilt.transfer.matching import compute_matches


def _write_ledger(path: Path, rows: list[dict]):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def it_should_match_direct_same_day_and_capture_fee(tmp_path: Path):
    # Build two ledgers with a clear transfer and a nearby fee on the debit side
    a1 = tmp_path / "A1.csv"
    a2 = tmp_path / "A2.csv"

    debit_id = "d1" * 8
    credit_id = "c1" * 8
    fee_id = "f1" * 8

    _write_ledger(
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
    _write_ledger(
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

    _write_ledger(
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
    _write_ledger(
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
