from __future__ import annotations

"""
Spec for LedgerRepository — the gateway for all per-account CSV ledger I/O.

Verifies path resolution, load/save round-trips, bulk loading,
account enumeration, and missing-file handling.
"""

from pathlib import Path

import pytest

from gilt.model.account import Transaction, TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv
from gilt.model.ledger_repository import LedgerRepository


def _make_group(txn_id: str, account_id: str, date: str = "2025-01-15") -> TransactionGroup:
    """Create a minimal TransactionGroup for testing."""
    return TransactionGroup(
        group_id=txn_id,
        primary=Transaction(
            transaction_id=txn_id,
            date=date,
            description="EXAMPLE UTILITY",
            amount=-42.00,
            currency="CAD",
            account_id=account_id,
        ),
    )


class DescribeLedgerRepository:
    @pytest.fixture
    def data_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "accounts"
        d.mkdir()
        return d

    @pytest.fixture
    def repo(self, data_dir: Path) -> LedgerRepository:
        return LedgerRepository(data_dir)

    def it_should_load_groups_for_an_existing_account(self, repo, data_dir):
        group = _make_group("txn001", "MYBANK_CHQ")
        (data_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group]), encoding="utf-8")

        groups = repo.load("MYBANK_CHQ")

        assert len(groups) == 1
        assert groups[0].primary.transaction_id == "txn001"

    def it_should_return_empty_list_for_nonexistent_account(self, repo):
        groups = repo.load("MISSING_ACCT")

        assert groups == []

    def it_should_save_groups_to_csv(self, repo, data_dir):
        group = _make_group("txn002", "MYBANK_CC")

        repo.save("MYBANK_CC", [group])

        assert (data_dir / "MYBANK_CC.csv").exists()
        text = (data_dir / "MYBANK_CC.csv").read_text(encoding="utf-8")
        assert "txn002" in text

    def it_should_round_trip_load_and_save(self, repo):
        group = _make_group("txn003", "BANK2_BIZ")
        repo.save("BANK2_BIZ", [group])

        loaded = repo.load("BANK2_BIZ")

        assert len(loaded) == 1
        assert loaded[0].primary.transaction_id == "txn003"
        assert loaded[0].primary.account_id == "BANK2_BIZ"
        assert loaded[0].primary.description == "EXAMPLE UTILITY"
        assert loaded[0].primary.amount == -42.00

    def it_should_report_exists_true_for_existing_ledger(self, repo, data_dir):
        group = _make_group("txn004", "MYBANK_CHQ")
        (data_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group]), encoding="utf-8")

        assert repo.exists("MYBANK_CHQ") is True

    def it_should_report_exists_false_for_missing_ledger(self, repo):
        assert repo.exists("NO_SUCH_ACCT") is False

    def it_should_resolve_ledger_path_from_account_id(self, repo, data_dir):
        path = repo.ledger_path("MYBANK_CHQ")

        assert path == data_dir / "MYBANK_CHQ.csv"

    def it_should_load_all_account_groups(self, repo, data_dir):
        group_a = _make_group("txn005", "MYBANK_CHQ")
        group_b = _make_group("txn006", "MYBANK_CC")
        (data_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group_a]), encoding="utf-8")
        (data_dir / "MYBANK_CC.csv").write_text(dump_ledger_csv([group_b]), encoding="utf-8")

        all_groups = repo.load_all()

        ids = {g.primary.transaction_id for g in all_groups}
        assert ids == {"txn005", "txn006"}

    def it_should_skip_unparseable_files_when_loading_all(self, repo, data_dir):
        group = _make_group("txn007", "MYBANK_CHQ")
        (data_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group]), encoding="utf-8")
        (data_dir / "CORRUPT.csv").write_text("not,valid,csv\nbad data here\n", encoding="utf-8")

        all_groups = repo.load_all()

        # MYBANK_CHQ should load; CORRUPT should be skipped silently
        ids = {g.primary.transaction_id for g in all_groups}
        assert "txn007" in ids

    def it_should_return_empty_list_when_directory_missing(self, tmp_path):
        repo = LedgerRepository(tmp_path / "nonexistent")

        groups = repo.load_all()

        assert groups == []

    def it_should_list_available_account_ids(self, repo, data_dir):
        group_a = _make_group("txn008", "MYBANK_CHQ")
        group_b = _make_group("txn009", "BANK2_BIZ")
        (data_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group_a]), encoding="utf-8")
        (data_dir / "BANK2_BIZ.csv").write_text(dump_ledger_csv([group_b]), encoding="utf-8")

        account_ids = repo.available_account_ids()

        assert account_ids == ["BANK2_BIZ", "MYBANK_CHQ"]

    def it_should_return_empty_list_for_account_ids_when_dir_missing(self, tmp_path):
        repo = LedgerRepository(tmp_path / "nonexistent")

        account_ids = repo.available_account_ids()

        assert account_ids == []
