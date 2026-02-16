from unittest.mock import Mock
import pytest
from gilt.services.duplicate_service import DuplicateService
from gilt.model.duplicate import TransactionPair, DuplicateAssessment, DuplicateMatch
from gilt.model.events import DuplicateConfirmed, DuplicateRejected
from gilt.transfer.duplicate_detector import DuplicateDetector
from gilt.storage.event_store import EventStore
from datetime import date

class DescribeDuplicateService:
    def it_should_scan_for_duplicates(self):
        # Arrange
        mock_detector = Mock(spec=DuplicateDetector)
        mock_event_store = Mock(spec=EventStore)
        service = DuplicateService(mock_detector, mock_event_store)

        expected_matches = [Mock(spec=DuplicateMatch)]
        mock_detector.scan_for_duplicates.return_value = expected_matches

        # Act
        result = service.scan_for_duplicates(data_dir="some/path")

        # Assert
        assert result == expected_matches
        mock_detector.scan_for_duplicates.assert_called_once_with(
            "some/path", 1, 0.001
        )

    def it_should_resolve_duplicate_as_confirmed(self):
        # Arrange
        mock_detector = Mock(spec=DuplicateDetector)
        mock_event_store = Mock(spec=EventStore)
        service = DuplicateService(mock_detector, mock_event_store)

        pair = TransactionPair(
            txn1_id="t1", txn1_date=date(2025, 1, 1), txn1_description="desc1", txn1_amount=10.0, txn1_account="acc1",
            txn2_id="t2", txn2_date=date(2025, 1, 1), txn2_description="desc2", txn2_amount=10.0, txn2_account="acc1"
        )
        assessment = DuplicateAssessment(is_duplicate=True, confidence=0.9, reasoning="Same")
        match = DuplicateMatch(pair=pair, assessment=assessment)

        # Act
        service.resolve_duplicate(match, is_duplicate=True, keep_id="t1")

        # Assert
        mock_event_store.append_event.assert_called_once()
        event = mock_event_store.append_event.call_args[0][0]
        assert isinstance(event, DuplicateConfirmed)
        assert event.primary_transaction_id == "t1"
        assert event.duplicate_transaction_id == "t2"
        assert event.llm_was_correct is True

    def it_should_resolve_duplicate_as_rejected(self):
        # Arrange
        mock_detector = Mock(spec=DuplicateDetector)
        mock_event_store = Mock(spec=EventStore)
        service = DuplicateService(mock_detector, mock_event_store)

        pair = TransactionPair(
            txn1_id="t1", txn1_date=date(2025, 1, 1), txn1_description="desc1", txn1_amount=10.0, txn1_account="acc1",
            txn2_id="t2", txn2_date=date(2025, 1, 1), txn2_description="desc2", txn2_amount=10.0, txn2_account="acc1"
        )
        assessment = DuplicateAssessment(is_duplicate=True, confidence=0.9, reasoning="Same")
        match = DuplicateMatch(pair=pair, assessment=assessment)

        # Act
        service.resolve_duplicate(match, is_duplicate=False, rationale="Different dates")

        # Assert
        mock_event_store.append_event.assert_called_once()
        event = mock_event_store.append_event.call_args[0][0]
        assert isinstance(event, DuplicateRejected)
        assert event.transaction_id_1 == "t1"
        assert event.transaction_id_2 == "t2"
        assert event.user_rationale == "Different dates"
        assert event.llm_was_correct is False
