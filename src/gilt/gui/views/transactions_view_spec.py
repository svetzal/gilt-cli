from unittest.mock import Mock
from datetime import date

from gilt.gui.views.transactions_view import IntelligenceWorker
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.duplicate import DuplicateMatch, TransactionPair, DuplicateAssessment
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService


class DescribeIntelligenceWorker:
    def it_should_scan_for_duplicates_and_categories(self):
        # Arrange
        txn1 = Transaction(
            transaction_id="t1",
            date=date(2023, 1, 1),
            amount=10.0,
            description="Test 1",
            account_id="acc1",
        )
        txn2 = Transaction(
            transaction_id="t2",
            date=date(2023, 1, 1),
            amount=10.0,
            description="Test 2",
            account_id="acc2",
        )
        groups = [
            TransactionGroup(group_id="g1", primary=txn1),
            TransactionGroup(group_id="g2", primary=txn2),
        ]

        mock_dup_service = Mock(spec=DuplicateService)
        mock_cat_service = Mock(spec=SmartCategoryService)

        # Mock duplicate detection
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
        mock_dup_service.scan_transactions.return_value = [match]

        # Mock categorization
        mock_cat_service.predict_category.return_value = ("Food", 0.85)

        worker = IntelligenceWorker(groups, mock_dup_service, mock_cat_service)

        # Act
        # We call run() directly to avoid threading issues in test
        # But we need to connect signal first
        result = []
        worker.finished.connect(lambda x: result.append(x))

        worker.run()

        # Assert
        assert len(result) == 1
        metadata = result[0]

        # Check duplicate risk
        assert metadata["t1"]["risk"] is True
        assert metadata["t2"]["risk"] is True

        # Check categorization confidence
        assert metadata["t1"]["confidence"] == 0.85
        assert metadata["t2"]["confidence"] == 0.85
