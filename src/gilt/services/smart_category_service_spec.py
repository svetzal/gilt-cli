from unittest.mock import Mock
from gilt.services.smart_category_service import SmartCategoryService
from gilt.ml.categorization_classifier import CategorizationClassifier
from gilt.storage.event_store import EventStore
from gilt.model.events import TransactionCategorized

class DescribeSmartCategoryService:
    def it_should_predict_category(self):
        # Arrange
        mock_classifier = Mock(spec=CategorizationClassifier)
        mock_event_store = Mock(spec=EventStore)
        service = SmartCategoryService(mock_classifier, mock_event_store)

        mock_classifier.predict_single.return_value = ("Food", 0.95)

        # Act
        category, confidence = service.predict_category("Burger King", 10.0, "acc1")

        # Assert
        assert category == "Food"
        assert confidence == 0.95
        mock_classifier.predict_single.assert_called_once_with(
            description="Burger King",
            amount=10.0,
            account="acc1",
            confidence_threshold=0.0  # Should return even low confidence for UI to decide
        )

    def it_should_record_categorization(self):
        # Arrange
        mock_classifier = Mock(spec=CategorizationClassifier)
        mock_event_store = Mock(spec=EventStore)
        service = SmartCategoryService(mock_classifier, mock_event_store)

        # Act
        service.record_categorization(
            transaction_id="t1",
            category="Food",
            source="user",
            confidence=1.0
        )

        # Assert
        mock_event_store.append_event.assert_called_once()
        event = mock_event_store.append_event.call_args[0][0]
        assert isinstance(event, TransactionCategorized)
        assert event.transaction_id == "t1"
        assert event.category == "Food"
        assert event.source == "user"
