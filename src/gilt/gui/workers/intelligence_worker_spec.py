import pytest

pytest.importorskip("PySide6")

from datetime import date
from unittest.mock import Mock

from gilt.gui.workers.intelligence_worker import IntelligenceWorker
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService
from gilt.testing import make_group, make_transaction


class DescribeIntelligenceWorker:
    def it_should_find_duplicates_and_categories(self):
        txn1 = make_transaction(
            transaction_id="t1",
            date=date(2023, 1, 1),
            amount=10.0,
            description="Test 1",
            account_id="acc1",
        )
        txn2 = make_transaction(
            transaction_id="t2",
            date=date(2023, 1, 1),
            amount=10.0,
            description="Test 2",
            account_id="acc2",
        )
        groups = [
            make_group(group_id="g1", primary=txn1),
            make_group(group_id="g2", primary=txn2),
        ]

        mock_dup_service = Mock(spec=DuplicateService)
        mock_cat_service = Mock(spec=SmartCategoryService)

        pair = TransactionPair(
            txn1_id="t1",
            txn1_date=date(2023, 1, 1),
            txn1_description="Test 1",
            txn1_amount=10.0,
            txn1_account="acc1",
            txn2_id="t2",
            txn2_date=date(2023, 1, 1),
            txn2_description="Test 2",
            txn2_amount=10.0,
            txn2_account="acc2",
        )
        assessment = DuplicateAssessment(
            is_duplicate=True, confidence=0.9, reasoning="High confidence"
        )
        match = DuplicateMatch(pair=pair, assessment=assessment)
        mock_dup_service.find_duplicates.return_value = [match]

        mock_cat_service.predict_category.return_value = ("Food", 0.85)

        worker = IntelligenceWorker(groups, mock_dup_service, mock_cat_service)

        result = []
        worker.finished.connect(lambda x: result.append(x))

        worker.run()

        assert len(result) == 1
        metadata = result[0]

        assert metadata["t1"]["risk"] is True
        assert metadata["t2"]["risk"] is True

        assert metadata["t1"]["confidence"] == 0.85
        assert metadata["t2"]["confidence"] == 0.85
