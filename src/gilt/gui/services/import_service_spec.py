from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from gilt.gui.services.import_service import ImportService
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService


def _write_accounts_yml(path: Path) -> None:
    import yaml

    data = {
        "accounts": [
            {
                "account_id": "MYBANK_CHQ",
                "institution": "MyBank",
                "product": "Chequing",
                "import_hints": {"amount_sign": "expenses_negative"},
            },
            {
                "account_id": "MYBANK_CC",
                "institution": "MyBank",
                "product": "Credit Card",
                "import_hints": {"amount_sign": "expenses_positive"},
            },
        ]
    }
    path.write_text(yaml.safe_dump(data))


def _make_pair(
    txn1_id: str = "existing_txn_001",
    txn2_id: str = "new_transaction_1",
    txn1_date: date = date(2025, 6, 1),
    txn2_date: date = date(2025, 6, 2),
    txn1_desc: str = "SAMPLE STORE",
    txn2_desc: str = "SAMPLE STORE ANYTOWN",
    txn1_source: str = "existing.csv",
    txn2_source: str = "import.csv",
) -> TransactionPair:
    return TransactionPair(
        txn1_id=txn1_id,
        txn1_date=txn1_date,
        txn1_description=txn1_desc,
        txn1_amount=-50.0,
        txn1_account="MYBANK_CHQ",
        txn1_source_file=txn1_source,
        txn2_id=txn2_id,
        txn2_date=txn2_date,
        txn2_description=txn2_desc,
        txn2_amount=-50.0,
        txn2_account="MYBANK_CHQ",
        txn2_source_file=txn2_source,
    )


def _make_match(pair: TransactionPair) -> DuplicateMatch:
    return DuplicateMatch(
        pair=pair,
        assessment=DuplicateAssessment(is_duplicate=True, confidence=0.9, reasoning="Same"),
    )


def _make_parse_row(txn_id: str = "txn001", description: str = "SAMPLE STORE") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": txn_id,
                "date": "2025-06-01",
                "description": description,
                "amount": -50.0,
                "currency": "CAD",
                "account_id": "MYBANK_CHQ",
                "counterparty": None,
                "source_file": "import.csv",
            }
        ]
    )


class DescribeImportServiceAccountDetection:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def data_dir(self, temp_dir):
        d = temp_dir / "accounts"
        d.mkdir()
        return d

    @pytest.fixture
    def accounts_config(self, temp_dir):
        config_path = temp_dir / "accounts.yml"
        _write_accounts_yml(config_path)
        return config_path

    @pytest.fixture
    def service(self, data_dir, accounts_config):
        return ImportService(data_dir, accounts_config)

    def it_should_load_accounts_from_config(self, service):
        accounts = service.get_accounts()
        assert len(accounts) == 2
        ids = [a.account_id for a in accounts]
        assert "MYBANK_CHQ" in ids
        assert "MYBANK_CC" in ids

    def it_should_cache_accounts_after_first_load(self, service):
        first = service.get_accounts()
        second = service.get_accounts()
        assert first is second

    def it_should_clear_cache_on_request(self, service):
        service.get_accounts()
        assert service._accounts_cache is not None
        service.clear_accounts_cache()
        assert service._accounts_cache is None

    def it_should_return_expenses_negative_amount_sign_from_import_hints(self, service):
        sign = service._amount_sign_for("MYBANK_CHQ")
        assert sign == "expenses_negative"

    def it_should_return_expenses_positive_amount_sign_from_import_hints(self, service):
        sign = service._amount_sign_for("MYBANK_CC")
        assert sign == "expenses_positive"

    def it_should_default_to_expenses_negative_for_unknown_account(self, service):
        sign = service._amount_sign_for("UNKNOWN_ACCOUNT")
        assert sign == "expenses_negative"


class DescribeImportServiceDuplicateScanning:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def data_dir(self, temp_dir):
        d = temp_dir / "accounts"
        d.mkdir()
        return d

    @pytest.fixture
    def accounts_config(self, temp_dir):
        config_path = temp_dir / "accounts.yml"
        _write_accounts_yml(config_path)
        return config_path

    @pytest.fixture
    def mock_duplicate_service(self):
        svc = Mock(spec=DuplicateService)
        svc.detector = Mock()
        svc.detector.load_all_transactions.return_value = []
        svc.scan_transactions.return_value = []
        return svc

    @pytest.fixture
    def service(self, data_dir, accounts_config, mock_duplicate_service):
        return ImportService(data_dir, accounts_config, duplicate_service=mock_duplicate_service)

    def it_should_return_empty_list_when_no_duplicate_service(self, data_dir, accounts_config):
        svc = ImportService(data_dir, accounts_config, duplicate_service=None)
        result = svc.scan_file_for_duplicates(Path("fake.csv"), "MYBANK_CHQ")
        assert result == []

    def it_should_return_empty_list_when_file_has_no_transactions(
        self, service, mock_duplicate_service
    ):
        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.return_value = pd.DataFrame()
            result = service.scan_file_for_duplicates(Path("fake.csv"), "MYBANK_CHQ")
        assert result == []

    def it_should_filter_out_matches_where_neither_transaction_is_new(
        self, service, mock_duplicate_service
    ):
        new_id = "new_transaction_1"
        existing_1 = "existing_txn_001"
        existing_2 = "existing_txn_002"

        # parse_file returns one new transaction
        new_df = _make_parse_row(new_id)

        # scan_transactions returns a match between two existing transactions (not the new one)
        existing_pair = TransactionPair(
            txn1_id=existing_1,
            txn1_date=date(2025, 6, 1),
            txn1_description="ACME CORP",
            txn1_amount=-50.0,
            txn1_account="MYBANK_CHQ",
            txn2_id=existing_2,
            txn2_date=date(2025, 6, 1),
            txn2_description="ACME CORP",
            txn2_amount=-50.0,
            txn2_account="MYBANK_CHQ",
        )
        mock_duplicate_service.scan_transactions.return_value = [_make_match(existing_pair)]

        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.return_value = new_df
            result = service.scan_file_for_duplicates(Path("fake.csv"), "MYBANK_CHQ")

        assert result == []

    def it_should_keep_match_when_txn1_is_new_transaction(self, service, mock_duplicate_service):
        new_id = "new_transaction_1"
        existing_id = "existing_txn_001"

        new_df = _make_parse_row(new_id)

        pair = TransactionPair(
            txn1_id=new_id,  # txn1 IS the new transaction
            txn1_date=date(2025, 6, 1),
            txn1_description="SAMPLE STORE",
            txn1_amount=-50.0,
            txn1_account="MYBANK_CHQ",
            txn2_id=existing_id,
            txn2_date=date(2025, 6, 1),
            txn2_description="SAMPLE STORE",
            txn2_amount=-50.0,
            txn2_account="MYBANK_CHQ",
        )
        mock_duplicate_service.scan_transactions.return_value = [_make_match(pair)]

        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.return_value = new_df
            result = service.scan_file_for_duplicates(Path("fake.csv"), "MYBANK_CHQ")

        assert len(result) == 1
        assert result[0].pair.txn1_id == new_id

    def it_should_swap_pair_when_txn2_is_new_transaction(self, service, mock_duplicate_service):
        new_id = "new_transaction_1"
        existing_id = "existing_txn_001"

        # parse_file returns the new transaction (txn2 in the match below)
        new_df = pd.DataFrame(
            [
                {
                    "transaction_id": new_id,
                    "date": "2025-06-02",
                    "description": "SAMPLE STORE ANYTOWN",
                    "amount": -50.0,
                    "currency": "CAD",
                    "account_id": "MYBANK_CHQ",
                    "counterparty": None,
                    "source_file": "import.csv",
                }
            ]
        )

        # txn2 is the new transaction; after swap, new should become txn1
        pair = TransactionPair(
            txn1_id=existing_id,
            txn1_date=date(2025, 6, 1),
            txn1_description="SAMPLE STORE",
            txn1_amount=-50.0,
            txn1_account="MYBANK_CHQ",
            txn1_source_file="existing.csv",
            txn2_id=new_id,
            txn2_date=date(2025, 6, 2),
            txn2_description="SAMPLE STORE ANYTOWN",
            txn2_amount=-50.0,
            txn2_account="MYBANK_CHQ",
            txn2_source_file="import.csv",
        )
        mock_duplicate_service.scan_transactions.return_value = [_make_match(pair)]

        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.return_value = new_df
            result = service.scan_file_for_duplicates(Path("fake.csv"), "MYBANK_CHQ")

        assert len(result) == 1
        swapped = result[0].pair
        # New transaction must now be txn1
        assert swapped.txn1_id == new_id
        assert swapped.txn1_date == date(2025, 6, 2)
        assert swapped.txn1_description == "SAMPLE STORE ANYTOWN"
        assert swapped.txn1_source_file == "import.csv"
        # Existing transaction must now be txn2
        assert swapped.txn2_id == existing_id
        assert swapped.txn2_date == date(2025, 6, 1)
        assert swapped.txn2_description == "SAMPLE STORE"
        assert swapped.txn2_source_file == "existing.csv"

    def it_should_return_empty_list_on_parse_error(self, service, mock_duplicate_service):
        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.side_effect = ValueError("CSV parse error")
            result = service.scan_file_for_duplicates(Path("fake.csv"), "MYBANK_CHQ")
        assert result == []


class DescribeImportServiceCategorizationScanning:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def data_dir(self, temp_dir):
        d = temp_dir / "accounts"
        d.mkdir()
        return d

    @pytest.fixture
    def accounts_config(self, temp_dir):
        config_path = temp_dir / "accounts.yml"
        _write_accounts_yml(config_path)
        return config_path

    @pytest.fixture
    def mock_smart_category_service(self):
        svc = Mock(spec=SmartCategoryService)
        svc.predict_category.return_value = ("Housing", 0.9)
        return svc

    @pytest.fixture
    def service(self, data_dir, accounts_config, mock_smart_category_service):
        return ImportService(
            data_dir,
            accounts_config,
            smart_category_service=mock_smart_category_service,
        )

    def it_should_return_empty_list_when_no_smart_category_service(self, data_dir, accounts_config):
        svc = ImportService(data_dir, accounts_config, smart_category_service=None)
        result = svc.scan_file_for_categorization(Path("fake.csv"), "MYBANK_CHQ")
        assert result == []

    def it_should_exclude_transactions_by_id(self, service):
        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.return_value = _make_parse_row("txn001")
            result = service.scan_file_for_categorization(
                Path("fake.csv"), "MYBANK_CHQ", exclude_ids=["txn001"]
            )
        assert result == []

    def it_should_auto_assign_category_when_confidence_above_threshold(
        self, service, mock_smart_category_service
    ):
        mock_smart_category_service.predict_category.return_value = ("Housing", 0.9)
        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.return_value = _make_parse_row("txn001")
            result = service.scan_file_for_categorization(Path("fake.csv"), "MYBANK_CHQ")
        assert len(result) == 1
        assert result[0].assigned_category == "Housing"
        assert result[0].confidence == pytest.approx(0.9)

    def it_should_not_auto_assign_category_when_confidence_below_threshold(
        self, service, mock_smart_category_service
    ):
        mock_smart_category_service.predict_category.return_value = ("Housing", 0.5)
        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.return_value = _make_parse_row("txn001")
            result = service.scan_file_for_categorization(Path("fake.csv"), "MYBANK_CHQ")
        assert len(result) == 1
        assert result[0].assigned_category is None

    def it_should_return_empty_list_on_parse_error(self, service):
        with patch("gilt.gui.services.import_service.parse_file") as mock_parse:
            mock_parse.side_effect = ValueError("Parse failed")
            result = service.scan_file_for_categorization(Path("fake.csv"), "MYBANK_CHQ")
        assert result == []


class DescribeImportServiceImportExecution:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def data_dir(self, temp_dir):
        d = temp_dir / "accounts"
        d.mkdir()
        return d

    @pytest.fixture
    def accounts_config(self, temp_dir):
        config_path = temp_dir / "accounts.yml"
        _write_accounts_yml(config_path)
        return config_path

    @pytest.fixture
    def service(self, data_dir, accounts_config):
        return ImportService(data_dir, accounts_config)

    def it_should_perform_dry_run_by_default(self, service):
        with (
            patch("gilt.gui.services.import_service.normalize_file") as mock_normalize,
            patch("gilt.gui.services.import_service.link_transfers") as mock_link,
        ):
            mock_link.return_value = 0
            result = service.import_file(Path("fake.csv"), "MYBANK_CHQ", write=False)
        mock_normalize.assert_not_called()
        assert result.success is True
        assert any("DRY-RUN" in msg for msg in result.messages)

    def it_should_call_normalize_and_link_when_write_is_true(self, service, data_dir):
        ledger_path = data_dir / "MYBANK_CHQ.csv"
        with (
            patch("gilt.gui.services.import_service.normalize_file") as mock_normalize,
            patch("gilt.gui.services.import_service.link_transfers") as mock_link,
        ):
            mock_normalize.return_value = ledger_path
            mock_link.return_value = 0
            result = service.import_file(Path("fake.csv"), "MYBANK_CHQ", write=True)
        mock_normalize.assert_called_once()
        mock_link.assert_called_once()
        assert result.success is True

    def it_should_invoke_progress_callback_at_milestones(self, service):
        progress_calls = []
        with (
            patch("gilt.gui.services.import_service.normalize_file"),
            patch("gilt.gui.services.import_service.link_transfers") as mock_link,
        ):
            mock_link.return_value = 0
            service.import_file(
                Path("fake.csv"),
                "MYBANK_CHQ",
                write=False,
                progress_callback=lambda pct: progress_calls.append(pct),
            )
        assert 10 in progress_calls
        assert 100 in progress_calls

    def it_should_return_error_result_on_exception(self, service):
        with patch("gilt.gui.services.import_service.link_transfers") as mock_link:
            mock_link.side_effect = OSError("Link failed")
            result = service.import_file(Path("fake.csv"), "MYBANK_CHQ", write=False)
        assert result.success is False
        assert result.error_count == 1
        assert len(result.messages) > 0
