from __future__ import annotations

"""
Specs for ledger CSV serialisation and deserialisation.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

import csv
import io

from gilt.model.account import SplitLine
from gilt.model.ledger_io import (
    LEDGER_COLUMNS,
    ROW_TYPE_PRIMARY,
    ROW_TYPE_SPLIT,
    _to_str,
    dump_ledger_csv,
    load_ledger_csv,
)
from gilt.testing.fixtures import make_group, make_transaction


def _csv_rows(text: str) -> list[dict]:
    """Parse a CSV string into a list of row dicts."""
    return list(csv.DictReader(io.StringIO(text)))


# ---------------------------------------------------------------------------
# _to_str
# ---------------------------------------------------------------------------


class DescribeToStr:
    """Unit specs for the _to_str formatting helper."""

    def it_should_format_integer_floats_without_decimal(self):
        assert _to_str(100.0) == "100"
        assert _to_str(-25.0) == "-25"
        assert _to_str(0.0) == "0"

    def it_should_format_non_integer_floats_with_stripped_zeros(self):
        assert _to_str(-25.5) == "-25.5"
        assert _to_str(9.99) == "9.99"
        assert _to_str(1.10) == "1.1"

    def it_should_format_none_as_empty_string(self):
        assert _to_str(None) == ""

    def it_should_format_integers_as_plain_string(self):
        assert _to_str(100) == "100"
        assert _to_str(0) == "0"

    def it_should_format_strings_unchanged(self):
        assert _to_str("hello") == "hello"


# ---------------------------------------------------------------------------
# dump_ledger_csv
# ---------------------------------------------------------------------------


class DescribeDumpLedgerCsv:
    """Specs for serialising TransactionGroup objects to CSV text."""

    def it_should_produce_header_row_with_all_ledger_columns(self):
        text = dump_ledger_csv([])
        rows = _csv_rows(text)
        assert rows == []
        # Verify header from first line
        header_line = text.splitlines()[0]
        for col in LEDGER_COLUMNS:
            assert col in header_line

    def it_should_emit_one_primary_row_per_group_with_no_splits(self):
        group = make_group(primary=make_transaction())
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        assert len(rows) == 1
        assert rows[0]["row_type"] == ROW_TYPE_PRIMARY
        assert rows[0]["transaction_id"] == "aabbccdd11223344"

    def it_should_write_amount_as_integer_string_for_whole_numbers(self):
        group = make_group(primary=make_transaction(amount=-50.0))
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        assert rows[0]["amount"] == "-50"

    def it_should_write_amount_as_decimal_string_for_fractional_values(self):
        group = make_group(primary=make_transaction(amount=-9.99))
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        assert rows[0]["amount"] == "-9.99"

    def it_should_emit_split_rows_after_primary(self):
        primary = make_transaction(amount=-100.0)
        splits = [
            SplitLine(amount=-60.0, category="Groceries", memo="food"),
            SplitLine(amount=-40.0, category="Household", memo="cleaning"),
        ]
        group = make_group(primary=primary, splits=splits, tolerance=0.1)
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        assert len(rows) == 3
        assert rows[0]["row_type"] == ROW_TYPE_PRIMARY
        assert rows[1]["row_type"] == ROW_TYPE_SPLIT
        assert rows[2]["row_type"] == ROW_TYPE_SPLIT

    def it_should_write_split_category_to_split_category_column(self):
        primary = make_transaction(amount=-100.0)
        splits = [SplitLine(amount=-100.0, category="Groceries", subcategory="Fresh")]
        group = make_group(primary=primary, splits=splits)
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        split_row = rows[1]
        assert split_row["split_category"] == "Groceries"
        assert split_row["split_subcategory"] == "Fresh"
        # primary category columns are blank on split rows
        assert split_row["category"] == ""
        assert split_row["subcategory"] == ""

    def it_should_serialize_metadata_as_json(self):
        primary = make_transaction(metadata={"transfer": {"role": "source", "amount": 200}})
        group = make_group(primary=primary)
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        import json

        meta = json.loads(rows[0]["metadata_json"])
        assert meta["transfer"]["role"] == "source"

    def it_should_use_group_id_for_group_id_column(self):
        primary = make_transaction(transaction_id="txid0000txid0000")
        group = make_group(primary=primary, group_id="custom-group-id")
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        assert rows[0]["group_id"] == "custom-group-id"

    def it_should_emit_empty_string_for_split_fields_on_primary_row(self):
        group = make_group(primary=make_transaction())
        text = dump_ledger_csv([group])
        rows = _csv_rows(text)
        assert rows[0]["line_id"] == ""
        assert rows[0]["target_account_id"] == ""
        assert rows[0]["split_category"] == ""
        assert rows[0]["split_memo"] == ""
        assert rows[0]["split_percent"] == ""


# ---------------------------------------------------------------------------
# load_ledger_csv
# ---------------------------------------------------------------------------


class DescribeLoadLedgerCsv:
    """Specs for parsing CSV text into TransactionGroup objects."""

    def it_should_return_empty_list_for_empty_input(self):
        result = load_ledger_csv("")
        assert result == []

    def it_should_parse_a_single_primary_row(self):
        primary = make_transaction(
            transaction_id="bbbb2222bbbb2222",
            date="2025-03-10",
            description="ACME CORP",
            amount=-75.0,
            account_id="MYBANK_CC",
        )
        group = make_group(primary=primary)
        text = dump_ledger_csv([group])
        result = load_ledger_csv(text)
        assert len(result) == 1
        assert result[0].primary.transaction_id == "bbbb2222bbbb2222"
        assert result[0].primary.description == "ACME CORP"
        assert result[0].primary.amount == -75.0

    def it_should_apply_default_currency_when_currency_column_is_blank(self):
        # Manually construct a row with blank currency
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "row_type": ROW_TYPE_PRIMARY,
                "group_id": "g1",
                "transaction_id": "cccc3333cccc3333",
                "date": "2025-04-01",
                "description": "EXAMPLE UTILITY",
                "amount": "-150",
                "currency": "",  # blank
                "account_id": "MYBANK_CHQ",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "",
                "metadata_json": "",
                "line_id": "",
                "target_account_id": "",
                "split_category": "",
                "split_subcategory": "",
                "split_memo": "",
                "split_percent": "",
            }
        )
        result = load_ledger_csv(buf.getvalue(), default_currency="USD")
        assert result[0].primary.currency == "USD"

    def it_should_parse_splits_and_associate_with_primary(self):
        primary = make_transaction(amount=-100.0)
        splits = [
            SplitLine(amount=-60.0, category="Groceries"),
            SplitLine(amount=-40.0, category="Household"),
        ]
        group = make_group(primary=primary, splits=splits, tolerance=0.1)
        text = dump_ledger_csv([group])
        result = load_ledger_csv(text)
        assert len(result) == 1
        assert len(result[0].splits) == 2
        assert result[0].splits[0].category == "Groceries"
        assert result[0].splits[1].category == "Household"

    def it_should_handle_legacy_csv_with_no_row_type_column(self):
        """Legacy format: no row_type column — all rows become primary transactions."""
        buf = io.StringIO()
        # Legacy columns subset (no row_type, no group_id)
        legacy_cols = [
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
            "metadata_json",
        ]
        writer = csv.DictWriter(buf, fieldnames=legacy_cols, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "transaction_id": "dddd4444dddd4444",
                "date": "2025-05-20",
                "description": "SAMPLE STORE",
                "amount": "-30",
                "currency": "CAD",
                "account_id": "MYBANK_CHQ",
                "counterparty": "",
                "category": "Groceries",
                "subcategory": "",
                "notes": "",
                "source_file": "",
                "metadata_json": "",
            }
        )
        result = load_ledger_csv(buf.getvalue())
        assert len(result) == 1
        assert result[0].primary.transaction_id == "dddd4444dddd4444"
        assert result[0].primary.category == "Groceries"

    def it_should_skip_groups_where_only_split_rows_exist(self):
        """Splits without a primary row are malformed and should be skipped."""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "row_type": ROW_TYPE_SPLIT,
                "group_id": "orphan-group",
                "transaction_id": "eeee5555eeee5555",
                "date": "2025-06-01",
                "description": "",
                "amount": "-50",
                "currency": "CAD",
                "account_id": "MYBANK_CHQ",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "",
                "metadata_json": "",
                "line_id": "L1",
                "target_account_id": "",
                "split_category": "Food",
                "split_subcategory": "",
                "split_memo": "",
                "split_percent": "",
            }
        )
        result = load_ledger_csv(buf.getvalue())
        assert result == []

    def it_should_sort_groups_by_date_then_account_then_amount_then_group_id(self):
        t1 = make_transaction(
            transaction_id="aaaa0001aaaa0001",
            date="2025-01-01",
            amount=-10.0,
            account_id="MYBANK_CHQ",
        )
        t2 = make_transaction(
            transaction_id="bbbb0002bbbb0002",
            date="2025-01-01",
            amount=-5.0,
            account_id="MYBANK_CHQ",
        )
        t3 = make_transaction(
            transaction_id="cccc0003cccc0003",
            date="2025-01-02",
            amount=-20.0,
            account_id="MYBANK_CHQ",
        )
        # Dump in reverse order to verify sorting
        text = dump_ledger_csv([make_group(primary=t3), make_group(primary=t1), make_group(primary=t2)])
        result = load_ledger_csv(text)
        dates = [str(g.primary.date) for g in result]
        assert dates[0] == "2025-01-01"
        assert dates[1] == "2025-01-01"
        assert dates[2] == "2025-01-02"
        # Within same date/account: smaller abs amount first
        amounts = [abs(g.primary.amount) for g in result[:2]]
        assert amounts == sorted(amounts)

    def it_should_parse_metadata_json_into_dict(self):
        primary = make_transaction(metadata={"key": "value", "num": 42})
        group = make_group(primary=primary)
        text = dump_ledger_csv([group])
        result = load_ledger_csv(text)
        assert result[0].primary.metadata == {"key": "value", "num": 42}

    def it_should_return_empty_dict_for_invalid_metadata_json(self):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "row_type": ROW_TYPE_PRIMARY,
                "group_id": "g1",
                "transaction_id": "ffff6666ffff6666",
                "date": "2025-07-01",
                "description": "ACME CORP",
                "amount": "-10",
                "currency": "CAD",
                "account_id": "MYBANK_CHQ",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "",
                "metadata_json": "{invalid json}",
                "line_id": "",
                "target_account_id": "",
                "split_category": "",
                "split_subcategory": "",
                "split_memo": "",
                "split_percent": "",
            }
        )
        result = load_ledger_csv(buf.getvalue())
        assert result[0].primary.metadata == {}


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class DescribeRoundTrip:
    """Specs verifying dump → load fidelity."""

    def it_should_preserve_primary_fields_through_round_trip(self):
        primary = make_transaction(
            transaction_id="rtrp1111rtrp1111",
            date="2025-08-15",
            description="EXAMPLE UTILITY",
            amount=-200.0,
            currency="CAD",
            account_id="BANK2_BIZ",
            category="Housing",
            subcategory="Utilities",
            notes="monthly bill",
            source_file="mybank_export.csv",
        )
        group = make_group(primary=primary)
        text = dump_ledger_csv([group])
        result = load_ledger_csv(text)
        assert len(result) == 1
        t = result[0].primary
        assert t.transaction_id == "rtrp1111rtrp1111"
        assert str(t.date) == "2025-08-15"
        assert t.description == "EXAMPLE UTILITY"
        assert t.amount == -200.0
        assert t.currency == "CAD"
        assert t.account_id == "BANK2_BIZ"
        assert t.category == "Housing"
        assert t.subcategory == "Utilities"
        assert t.notes == "monthly bill"
        assert t.source_file == "mybank_export.csv"

    def it_should_preserve_splits_through_round_trip(self):
        primary = make_transaction(amount=-100.0)
        splits = [
            SplitLine(
                line_id="L1",
                amount=-70.0,
                category="Groceries",
                subcategory="Fresh",
                memo="produce",
                percent=70.0,
            ),
            SplitLine(
                line_id="L2",
                amount=-30.0,
                category="Household",
                memo="supplies",
                percent=30.0,
            ),
        ]
        group = make_group(primary=primary, splits=splits, tolerance=0.1)
        text = dump_ledger_csv([group])
        result = load_ledger_csv(text)
        assert len(result[0].splits) == 2
        s0 = result[0].splits[0]
        assert s0.line_id == "L1"
        assert s0.amount == -70.0
        assert s0.category == "Groceries"
        assert s0.subcategory == "Fresh"
        assert s0.memo == "produce"
        assert s0.percent == 70.0

    def it_should_preserve_multiple_groups_through_round_trip(self):
        groups = [
            make_group(
                primary=make_transaction(
                    transaction_id=f"tx{i:014d}",
                    date=f"2025-01-{i:02d}",
                    amount=-float(i * 10),
                    account_id="MYBANK_CHQ",
                )
            )
            for i in range(1, 4)
        ]
        text = dump_ledger_csv(groups)
        result = load_ledger_csv(text)
        assert len(result) == 3
        ids = {g.primary.transaction_id for g in result}
        assert ids == {"tx00000000000001", "tx00000000000002", "tx00000000000003"}
