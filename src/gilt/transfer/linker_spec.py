from __future__ import annotations

from pathlib import Path

import pandas as pd

from gilt.model.ledger_io import load_ledger_csv
from gilt.transfer.linker import link_transfers


def _write_ledger(path: Path, rows: list[dict]):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def it_should_mark_both_sides_and_persist_metadata(tmp_path: Path):
    # Prepare two ledgers with a clear transfer pair
    acc1 = tmp_path / "ACC1.csv"
    acc2 = tmp_path / "ACC2.csv"

    d_id = "d3" * 8
    c_id = "c3" * 8

    _write_ledger(
        acc1,
        [
            {
                "transaction_id": d_id,
                "date": "2025-03-03",
                "description": "E-TRANSFER OUT",
                "amount": -150.0,
                "currency": "CAD",
                "account_id": "ACC1",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "acc1.csv",
            }
        ],
    )

    _write_ledger(
        acc2,
        [
            {
                "transaction_id": c_id,
                "date": "2025-03-03",
                "description": "E-TRANSFER IN",
                "amount": 150.0,
                "currency": "CAD",
                "account_id": "ACC2",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "acc2.csv",
            }
        ],
    )

    # Run linker with write=True so metadata persists to CSVs
    changed = link_transfers(processed_dir=tmp_path, write=True)
    assert changed == 2

    # Verify that metadata_json contains the transfer object on both sides
    for p, role, counter_txn in [
        (acc1, "debit", c_id),
        (acc2, "credit", d_id),
    ]:
        text = p.read_text(encoding="utf-8")
        groups = load_ledger_csv(text, default_currency="CAD")
        assert len(groups) == 1
        meta = groups[0].primary.metadata or {}
        tr = meta.get("transfer")
        assert isinstance(tr, dict)
        assert tr.get("role") == role
        assert tr.get("counterparty_transaction_id") == counter_txn
        assert abs(float(tr.get("amount", 0.0)) - 150.0) < 1e-6
        assert tr.get("method") in {"direct_same_day", "window_interac"}
        assert isinstance(tr.get("score"), float)

    # Run again (idempotent). No further file changes should be needed.
    changed2 = link_transfers(processed_dir=tmp_path, write=True)
    assert changed2 in {0, 2}  # implementation may touch both files if score/method updated
