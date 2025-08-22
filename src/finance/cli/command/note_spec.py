from __future__ import annotations

from pathlib import Path
import csv

from finance.cli.command.note import run


def _write_simple_ledger(path: Path, rows: list[dict]):
    # Minimal processed schema header
    fieldnames = [
        "transaction_id",
        "date",
        "description",
        "amount",
        "currency",
        "account_id",
        "counterparty",
        "category",
        "subcategory",
        "notes",
        "source_file",
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def it_should_update_note_with_write_and_be_dry_run_by_default(tmp_path: Path):
    acc = "TESTACC"
    ledger_path = tmp_path / f"{acc}.csv"

    tid1 = "abcd1234abcd1234"
    tid2 = "efef5678efef5678"

    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": tid1,
                "date": "2025-04-04",
                "description": "Sample 1",
                "amount": -10,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "old",
                "source_file": "x.csv",
            },
            {
                "transaction_id": tid2,
                "date": "2025-04-05",
                "description": "Sample 2",
                "amount": 10,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            },
        ],
    )

    # Dry-run should not modify file
    rc = run(account=acc, txid=tid1[:8], note_text="new-note", data_dir=tmp_path, write=False)
    assert rc == 0
    # Verify unchanged
    rows = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["notes"] == "old"

    # Now write changes
    rc2 = run(account=acc, txid=tid1[:8], note_text="new-note", data_dir=tmp_path, write=True)
    assert rc2 == 0
    rows2 = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows2[0]["notes"] == "new-note"


def it_should_complain_on_short_or_ambiguous_prefix(tmp_path: Path):
    acc = "AMBIG"
    ledger_path = tmp_path / f"{acc}.csv"

    # Two rows whose prefixes will collide if prefix too short
    tid1 = "aabbccddeeff0011"
    tid2 = "aabbccdd11223344"

    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": tid1,
                "date": "2025-05-05",
                "description": "R1",
                "amount": -1,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            },
            {
                "transaction_id": tid2,
                "date": "2025-05-06",
                "description": "R2",
                "amount": 1,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            },
        ],
    )

    # Too short
    rc_short = run(account=acc, txid="aabbccd", note_text="x", data_dir=tmp_path, write=False)
    assert rc_short == 2

    # Ambiguous
    rc_amb = run(account=acc, txid="aabbccdd", note_text="x", data_dir=tmp_path, write=False)
    assert rc_amb == 2
