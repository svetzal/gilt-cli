"""Tests for account module Transaction and TransactionGroup models."""

from __future__ import annotations

from datetime import date

from gilt.model.account import Transaction, TransactionGroup


class DescribeTransactionFromProjectionRow:
    """Test Transaction.from_projection_row() class method."""

    def it_should_convert_basic_projection_row(self):
        """Converts projection row dict to Transaction with field mapping."""
        row = {
            "transaction_id": "abc123def456",
            "transaction_date": "2024-01-15",
            "canonical_description": "EXAMPLE UTILITY",
            "amount": "125.50",
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
            "counterparty": "Example Utility Co",
            "category": "Bills",
            "subcategory": "Utilities",
            "notes": "Monthly bill",
            "source_file": "mybank_jan.csv",
            "metadata": '{"transfer": {"role": "primary"}}',
        }

        txn = Transaction.from_projection_row(row)

        assert txn.transaction_id == "abc123def456"
        assert txn.date == date(2024, 1, 15)
        assert txn.description == "EXAMPLE UTILITY"
        assert txn.amount == 125.50
        assert txn.currency == "CAD"
        assert txn.account_id == "MYBANK_CHQ"
        assert txn.counterparty == "Example Utility Co"
        assert txn.category == "Bills"
        assert txn.subcategory == "Utilities"
        assert txn.notes == "Monthly bill"
        assert txn.source_file == "mybank_jan.csv"
        assert txn.metadata == {"transfer": {"role": "primary"}}

    def it_should_handle_optional_fields_as_none(self):
        """Sets optional fields to None when missing from row."""
        row = {
            "transaction_id": "minimal123",
            "transaction_date": "2024-02-10",
            "canonical_description": "SAMPLE STORE",
            "amount": "-50.00",
            "currency": "CAD",
            "account_id": "MYBANK_CC",
        }

        txn = Transaction.from_projection_row(row)

        assert txn.counterparty is None
        assert txn.category is None
        assert txn.subcategory is None
        assert txn.notes is None
        assert txn.source_file is None
        assert txn.metadata == {}

    def it_should_parse_metadata_json_string(self):
        """Parses metadata from JSON string to dict."""
        row = {
            "transaction_id": "meta123",
            "transaction_date": "2024-03-01",
            "canonical_description": "TEST",
            "amount": "10.00",
            "currency": "CAD",
            "account_id": "TEST_ACCT",
            "metadata": '{"key": "value", "nested": {"foo": "bar"}}',
        }

        txn = Transaction.from_projection_row(row)

        assert txn.metadata == {"key": "value", "nested": {"foo": "bar"}}

    def it_should_handle_empty_metadata(self):
        """Converts None or empty string metadata to empty dict."""
        row_none = {
            "transaction_id": "none123",
            "transaction_date": "2024-04-01",
            "canonical_description": "TEST",
            "amount": "10.00",
            "currency": "CAD",
            "account_id": "TEST_ACCT",
            "metadata": None,
        }

        row_empty = {
            "transaction_id": "empty123",
            "transaction_date": "2024-04-02",
            "canonical_description": "TEST",
            "amount": "10.00",
            "currency": "CAD",
            "account_id": "TEST_ACCT",
            "metadata": "",
        }

        txn_none = Transaction.from_projection_row(row_none)
        txn_empty = Transaction.from_projection_row(row_empty)

        assert txn_none.metadata == {}
        assert txn_empty.metadata == {}

    def it_should_handle_metadata_as_dict(self):
        """Passes through metadata when already a dict (sqlite3.Row case)."""
        row = {
            "transaction_id": "dict123",
            "transaction_date": "2024-05-01",
            "canonical_description": "TEST",
            "amount": "10.00",
            "currency": "CAD",
            "account_id": "TEST_ACCT",
            "metadata": {"already": "parsed"},
        }

        txn = Transaction.from_projection_row(row)

        assert txn.metadata == {"already": "parsed"}


class DescribeTransactionGroupFromProjectionRow:
    """Test TransactionGroup.from_projection_row() class method."""

    def it_should_create_group_with_transaction_id_as_group_id(self):
        """Creates TransactionGroup with group_id matching transaction_id."""
        row = {
            "transaction_id": "group123abc",
            "transaction_date": "2024-06-15",
            "canonical_description": "ACME CORP",
            "amount": "-200.00",
            "currency": "CAD",
            "account_id": "MYBANK_BIZ",
            "category": "Expenses",
            "subcategory": "Supplies",
        }

        group = TransactionGroup.from_projection_row(row)

        assert group.group_id == "group123abc"
        assert group.primary.transaction_id == "group123abc"
        assert group.primary.date == date(2024, 6, 15)
        assert group.primary.description == "ACME CORP"
        assert group.primary.amount == -200.00
        assert group.primary.category == "Expenses"
        assert group.primary.subcategory == "Supplies"
