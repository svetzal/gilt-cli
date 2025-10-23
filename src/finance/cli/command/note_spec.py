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
    rc2 = run(account=acc, txid=tid1[:8], note_text="new-note", data_dir=tmp_path, write=True, assume_yes=True)
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


def it_should_update_notes_in_batch_by_description_and_amount(tmp_path: Path):
    acc = "BATCHACC"
    ledger_path = tmp_path / f"{acc}.csv"

    # Create three rows: two matching description+amount, one different
    rows = [
        {
            "transaction_id": "1111111111111111",
            "date": "2025-06-01",
            "description": "NETFLIX.COM",
            "amount": -16.99,
            "currency": "CAD",
            "account_id": acc,
            "counterparty": "",
            "category": "",
            "subcategory": "",
            "notes": "",
            "source_file": "x.csv",
        },
        {
            "transaction_id": "2222222222222222",
            "date": "2025-07-01",
            "description": "NETFLIX.COM",
            "amount": -16.99,
            "currency": "CAD",
            "account_id": acc,
            "counterparty": "",
            "category": "",
            "subcategory": "",
            "notes": "old",
            "source_file": "x.csv",
        },
        {
            "transaction_id": "3333333333333333",
            "date": "2025-07-02",
            "description": "SPOTIFY",
            "amount": -16.99,
            "currency": "CAD",
            "account_id": acc,
            "counterparty": "",
            "category": "",
            "subcategory": "",
            "notes": "",
            "source_file": "x.csv",
        },
    ]
    _write_simple_ledger(ledger_path, rows)

    # Dry-run should not modify
    rc = run(
        account=acc,
        txid=None,
        note_text="subscription",
        description="NETFLIX.COM",
        amount=-16.99,
        data_dir=tmp_path,
        write=False,
    )
    assert rc == 0
    rows_after = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after[0]["notes"] == ""
    assert rows_after[1]["notes"] == "old"

    # Write should update the two matching rows
    rc2 = run(
        account=acc,
        txid=None,
        note_text="subscription",
        description="NETFLIX.COM",
        amount=-16.99,
        assume_yes=True,
        data_dir=tmp_path,
        write=True,
    )
    assert rc2 == 0
    rows_after2 = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after2[0]["notes"] == "subscription"
    assert rows_after2[1]["notes"] == "subscription"
    assert rows_after2[2]["notes"] == ""


def it_should_return_error_when_no_batch_matches(tmp_path: Path):
    acc = "NOMATCH"
    ledger_path = tmp_path / f"{acc}.csv"
    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": "aaaaaaaaaaaaaaaa",
                "date": "2025-03-03",
                "description": "ABC",
                "amount": -10.0,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            }
        ],
    )
    rc = run(
        account=acc,
        txid=None,
        note_text="x",
        description="DEF",
        amount=-10.0,
        data_dir=tmp_path,
        write=False,
    )
    assert rc == 1


def it_should_match_batch_on_description_with_whitespace_and_amount_by_absolute_when_needed(tmp_path: Path):
    acc = "WSIGN"
    ledger_path = tmp_path / f"{acc}.csv"
    # Row with trailing spaces in description and negative amount in ledger
    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": "bbbbbbbbbbbbbbbb",
                "date": "2025-06-02",
                "description": "Email Trfs - E-TRANSFER SENT   ",
                "amount": -243.0,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            }
        ],
    )

    # Provide description without trailing spaces and positive amount; should match via abs fallback (dry-run)
    rc = run(
        account=acc,
        txid=None,
        note_text="locker",
        description="Email Trfs - E-TRANSFER SENT",
        amount=243.00,
        data_dir=tmp_path,
        write=False,
    )
    assert rc == 0

    # Now write and verify note updated
    rc2 = run(
        account=acc,
        txid=None,
        note_text="locker",
        description="Email Trfs - E-TRANSFER SENT",
        amount=243.00,
        data_dir=tmp_path,
        write=True,
        assume_yes=True,
    )
    assert rc2 == 0
    rows = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["notes"] == "locker"



def it_should_update_notes_in_batch_by_description_only(tmp_path: Path):
    acc = "BATCHDESC"
    ledger_path = tmp_path / f"{acc}.csv"
    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": "4444444444444444",
                "date": "2025-08-01",
                "description": "COFFEE SHOP",
                "amount": -3.50,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            },
            {
                "transaction_id": "5555555555555555",
                "date": "2025-08-02",
                "description": "COFFEE SHOP",
                "amount": -4.00,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "old",
                "source_file": "x.csv",
            },
            {
                "transaction_id": "6666666666666666",
                "date": "2025-08-03",
                "description": "GROCERY STORE",
                "amount": -25.00,
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

    # Dry-run description-only batch
    rc = run(
        account=acc,
        txid=None,
        note_text="morning-coffee",
        description="COFFEE SHOP",
        amount=None,
        data_dir=tmp_path,
        write=False,
    )
    assert rc == 0
    rows_after = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after[0]["notes"] == ""
    assert rows_after[1]["notes"] == "old"
    assert rows_after[2]["notes"] == ""

    # Write description-only batch
    rc2 = run(
        account=acc,
        txid=None,
        note_text="morning-coffee",
        description="COFFEE SHOP",
        amount=None,
        data_dir=tmp_path,
        write=True,
        assume_yes=True,
    )
    assert rc2 == 0
    rows_after2 = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after2[0]["notes"] == "morning-coffee"
    assert rows_after2[1]["notes"] == "morning-coffee"
    assert rows_after2[2]["notes"] == ""


def it_should_update_notes_by_description_prefix_case_insensitive(tmp_path: Path):
    acc = "PREFIXACC"
    ledger_path = tmp_path / f"{acc}.csv"
    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": "7777777777777777",
                "date": "2025-08-10",
                "description": "ANTHROPIC AI INC - SUBSCRIPTION",
                "amount": -99.0,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            },
            {
                "transaction_id": "8888888888888888",
                "date": "2025-08-11",
                "description": "Anthropic LLC PAYMENT",
                "amount": -49.0,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "old",
                "source_file": "x.csv",
            },
            {
                "transaction_id": "9999999999999999",
                "date": "2025-08-12",
                "description": "OTHER VENDOR",
                "amount": -10.0,
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

    # Dry-run with lowercase prefix; should match first two rows only
    rc = run(
        account=acc,
        txid=None,
        note_text="ai-tools",
        description=None,
        desc_prefix="anthropic",
        amount=None,
        data_dir=tmp_path,
        write=False,
    )
    assert rc == 0
    rows_after = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after[0]["notes"] == ""
    assert rows_after[1]["notes"] == "old"
    assert rows_after[2]["notes"] == ""

    # Write with assume_yes; should update the two matching rows, leaving the third untouched
    rc2 = run(
        account=acc,
        txid=None,
        note_text="ai-tools",
        description=None,
        desc_prefix="ANTHROPIC",
        amount=None,
        data_dir=tmp_path,
        write=True,
        assume_yes=True,
    )
    assert rc2 == 0
    rows_after2 = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after2[0]["notes"] == "ai-tools"
    assert rows_after2[1]["notes"] == "ai-tools"
    assert rows_after2[2]["notes"] == ""


def it_should_update_notes_by_regex_pattern(tmp_path: Path):
    acc = "PATTERNACC"
    ledger_path = tmp_path / f"{acc}.csv"
    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": "aaaa111111111111",
                "date": "2025-09-01",
                "description": "Payment - WWW Payment - 12345 HYDRO ONE",
                "amount": -150.0,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            },
            {
                "transaction_id": "bbbb222222222222",
                "date": "2025-09-02",
                "description": "Payment - WWW Payment - 67890 HYDRO ONE",
                "amount": -145.0,
                "currency": "CAD",
                "account_id": acc,
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "x.csv",
            },
            {
                "transaction_id": "cccc333333333333",
                "date": "2025-09-03",
                "description": "Payment - DIFFERENT VENDOR",
                "amount": -50.0,
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

    # Test with regex pattern matching variable payment numbers
    rc = run(
        account=acc,
        txid=None,
        note_text="hydro-bill",
        description=None,
        desc_prefix=None,
        pattern=r"Payment - WWW Payment - \d+ HYDRO ONE",
        amount=None,
        data_dir=tmp_path,
        write=False,
    )
    assert rc == 0
    rows_after = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after[0]["notes"] == ""
    assert rows_after[1]["notes"] == ""
    assert rows_after[2]["notes"] == ""

    # Write with pattern; should match first two rows only
    rc2 = run(
        account=acc,
        txid=None,
        note_text="hydro-bill",
        description=None,
        desc_prefix=None,
        pattern=r"Payment - WWW Payment - \d+ HYDRO ONE",
        amount=None,
        data_dir=tmp_path,
        write=True,
        assume_yes=True,
    )
    assert rc2 == 0
    rows_after2 = list(csv.DictReader(ledger_path.read_text(encoding="utf-8").splitlines()))
    assert rows_after2[0]["notes"] == "hydro-bill"
    assert rows_after2[1]["notes"] == "hydro-bill"
    assert rows_after2[2]["notes"] == ""


def it_should_error_on_invalid_regex_pattern(tmp_path: Path):
    acc = "BADPATTERN"
    ledger_path = tmp_path / f"{acc}.csv"
    _write_simple_ledger(
        ledger_path,
        [
            {
                "transaction_id": "dddd444444444444",
                "date": "2025-09-01",
                "description": "Test",
                "amount": -10.0,
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

    # Invalid regex should return error code
    rc = run(
        account=acc,
        txid=None,
        note_text="test",
        description=None,
        desc_prefix=None,
        pattern=r"[invalid(regex",  # Unclosed bracket
        amount=None,
        data_dir=tmp_path,
        write=False,
    )
    assert rc == 2  # Error code for invalid pattern
