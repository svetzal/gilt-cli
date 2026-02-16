"""Tests for ML-based duplicate classifier.

Validates that the classifier can be trained and make predictions
on transaction pairs.
"""

from __future__ import annotations

from datetime import date
import pytest

from gilt.model.duplicate import TransactionPair

try:
    import lightgbm  # noqa: F401

    has_lightgbm = True
except ImportError:
    has_lightgbm = False

from gilt.ml.duplicate_classifier import DuplicateClassifier

pytestmark = pytest.mark.skipif(not has_lightgbm, reason="LightGBM not installed (ml extra)")


class DescribeDuplicateClassifier:
    """Test suite for DuplicateClassifier."""

    def it_should_train_on_labeled_examples(self):
        """Classifier should train successfully with sufficient examples."""
        # Create training data
        pairs, labels = self._create_training_data()

        classifier = DuplicateClassifier()
        metrics = classifier.train(pairs, labels, validation_split=0.2)

        # Should return metrics
        assert "train_accuracy" in metrics
        assert "val_accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics

        # Accuracy should be reasonable (>60%)
        assert metrics["train_accuracy"] > 0.6
        assert metrics["val_accuracy"] > 0.5  # Validation is harder

    def it_should_predict_duplicates_after_training(self):
        """Trained classifier should make predictions."""
        pairs, labels = self._create_training_data()

        classifier = DuplicateClassifier()
        classifier.train(pairs, labels, validation_split=0.2)

        # Test on a new duplicate pair
        test_pair = TransactionPair(
            txn1_id="test1",
            txn1_date=date(2025, 3, 1),
            txn1_description="PAYMENT TO SPOTIFY",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="test2",
            txn2_date=date(2025, 3, 1),
            txn2_description="PYMT SPOTIFY INC",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
        )

        assessment = classifier.predict(test_pair)

        # Should return valid assessment
        assert isinstance(assessment.is_duplicate, bool)
        assert 0.0 <= assessment.confidence <= 1.0
        assert len(assessment.reasoning) > 0

    def it_should_provide_feature_importance(self):
        """Classifier should provide interpretable feature importance."""
        pairs, labels = self._create_training_data()

        classifier = DuplicateClassifier()
        classifier.train(pairs, labels)

        importance = classifier.get_feature_importance()

        # Should have importance for all features
        assert len(importance) == 8
        assert "cosine_similarity" in importance
        assert "amount_exact_match" in importance

        # All importances should be non-negative
        assert all(v >= 0 for v in importance.values())

        # At least one feature should have importance > 0
        assert any(v > 0 for v in importance.values())

    def it_should_require_sufficient_training_data(self):
        """Classifier should reject too little training data."""
        # Create tiny dataset (< 10 examples)
        pairs = [
            TransactionPair(
                txn1_id=f"a{i}",
                txn1_date=date(2025, 1, 1),
                txn1_description="TEST",
                txn1_amount=-10.0,
                txn1_account="ACC",
                txn2_id=f"b{i}",
                txn2_date=date(2025, 1, 1),
                txn2_description="TEST",
                txn2_amount=-10.0,
                txn2_account="ACC",
            )
            for i in range(5)
        ]
        labels = [True] * 5

        classifier = DuplicateClassifier()

        with pytest.raises(ValueError, match="at least 10 training examples"):
            classifier.train(pairs, labels)

    def it_should_fail_prediction_without_training(self):
        """Untrained classifier should raise error on prediction."""
        classifier = DuplicateClassifier()

        pair = TransactionPair(
            txn1_id="a",
            txn1_date=date(2025, 1, 1),
            txn1_description="TEST",
            txn1_amount=-10.0,
            txn1_account="ACC",
            txn2_id="b",
            txn2_date=date(2025, 1, 1),
            txn2_description="TEST",
            txn2_amount=-10.0,
            txn2_account="ACC",
        )

        with pytest.raises(RuntimeError, match="Model not trained"):
            classifier.predict(pair)

    @staticmethod
    def _create_training_data() -> tuple[list[TransactionPair], list[bool]]:
        """Create synthetic training dataset."""
        pairs = []
        labels = []

        # Duplicate examples (similar descriptions, same amount/date/account)
        for i in range(20):
            pairs.append(
                TransactionPair(
                    txn1_id=f"dup{i}_1",
                    txn1_date=date(2025, 1, i + 1),
                    txn1_description=f"PAYMENT TO SPOTIFY {i}",
                    txn1_amount=-10.99,
                    txn1_account="MYBANK_CHQ",
                    txn2_id=f"dup{i}_2",
                    txn2_date=date(2025, 1, i + 1),
                    txn2_description=f"PYMT SPOTIFY INC {i}",
                    txn2_amount=-10.99,
                    txn2_account="MYBANK_CHQ",
                )
            )
            labels.append(True)

        # Non-duplicate examples (different descriptions/amounts)
        for i in range(20):
            pairs.append(
                TransactionPair(
                    txn1_id=f"nondup{i}_1",
                    txn1_date=date(2025, 2, i + 1),
                    txn1_description=f"GROCERY STORE ABC {i}",
                    txn1_amount=-50.00 - i,
                    txn1_account="BANK2_BIZ",
                    txn2_id=f"nondup{i}_2",
                    txn2_date=date(2025, 2, i + 1),
                    txn2_description=f"RESTAURANT XYZ {i}",
                    txn2_amount=-30.00 - i,
                    txn2_account="BANK2_BIZ",
                )
            )
            labels.append(False)

        return pairs, labels
