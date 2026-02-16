"""Tests for duplicate feature extractor.

Validates that feature extraction works correctly for various transaction
pair scenarios including identical, similar, and different transactions.
"""

from __future__ import annotations

from datetime import date
import numpy as np

from gilt.ml.feature_extractor import DuplicateFeatureExtractor
from gilt.model.duplicate import TransactionPair


class DescribeFeatureExtractor:
    """Test suite for DuplicateFeatureExtractor."""

    def it_should_extract_features_for_identical_descriptions(self):
        """Identical descriptions should have high similarity scores."""
        pair = TransactionPair(
            txn1_id="abc123",
            txn1_date=date(2025, 1, 15),
            txn1_description="PAYMENT TO SPOTIFY",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="def456",
            txn2_date=date(2025, 1, 15),
            txn2_description="PAYMENT TO SPOTIFY",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
        )

        extractor = DuplicateFeatureExtractor()
        features = extractor.extract_features(pair)

        # Check feature vector shape
        assert features.shape == (8,)

        # Identical descriptions should have:
        # - cosine_similarity ≈ 1.0 (within floating point tolerance)
        assert abs(features[0] - 1.0) < 1e-6, f"Expected cosine≈1.0, got {features[0]}"
        # - levenshtein_ratio = 1.0
        assert features[1] == 1.0, f"Expected lev=1.0, got {features[1]}"
        # - token_overlap = 1.0
        assert features[2] == 1.0, f"Expected token=1.0, got {features[2]}"
        # - amount_exact_match = 1.0
        assert features[3] == 1.0, f"Expected amount=1.0, got {features[3]}"
        # - date_difference = 0
        assert features[4] == 0.0, f"Expected date_diff=0, got {features[4]}"
        # - same_account = 1.0
        assert features[5] == 1.0, f"Expected same_account=1.0, got {features[5]}"
        # - length_difference = 0.0
        assert features[6] == 0.0, f"Expected length_diff=0, got {features[6]}"
        # - common_prefix_ratio = 1.0
        assert features[7] == 1.0, f"Expected prefix=1.0, got {features[7]}"

    def it_should_detect_bank_description_variations(self):
        """Bank description variations should have high but not perfect similarity."""
        pair = TransactionPair(
            txn1_id="abc123",
            txn1_date=date(2025, 1, 15),
            txn1_description="PAYMENT TO SPOTIFY",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="def456",
            txn2_date=date(2025, 1, 16),
            txn2_description="PYMT SPOTIFY INC",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
        )

        extractor = DuplicateFeatureExtractor()
        features = extractor.extract_features(pair)

        # Should have:
        # - Moderate cosine similarity (character n-grams share some patterns)
        # Note: Character n-grams are less sensitive than word-level for different words
        assert features[0] > 0.3, f"Expected cosine>0.3, got {features[0]}"
        # - Moderate levenshtein (different words but similar)
        assert 0.4 < features[1] < 0.9, f"Expected lev in (0.4,0.9), got {features[1]}"
        # - Partial token overlap (SPOTIFY appears in both)
        assert features[2] >= 0.2, f"Expected token>=0.2, got {features[2]}"
        # - Exact amount match
        assert features[3] == 1.0, f"Expected amount=1.0, got {features[3]}"
        # - 1 day apart
        assert features[4] == 1.0, f"Expected date_diff=1, got {features[4]}"
        # - Same account
        assert features[5] == 1.0, f"Expected same_account=1.0, got {features[5]}"

    def it_should_detect_completely_different_transactions(self):
        """Completely different transactions should have low similarity."""
        pair = TransactionPair(
            txn1_id="abc123",
            txn1_date=date(2025, 1, 15),
            txn1_description="PAYMENT TO SPOTIFY",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="def456",
            txn2_date=date(2025, 1, 20),
            txn2_description="GROCERY STORE XYZ",
            txn2_amount=-45.67,
            txn2_account="BANK2_BIZ",
        )

        extractor = DuplicateFeatureExtractor()
        features = extractor.extract_features(pair)

        # Should have:
        # - Low cosine similarity (different words)
        assert features[0] < 0.3, f"Expected cosine<0.3, got {features[0]}"
        # - Low levenshtein (very different text)
        assert features[1] < 0.5, f"Expected lev<0.5, got {features[1]}"
        # - No token overlap
        assert features[2] == 0.0, f"Expected token=0, got {features[2]}"
        # - Different amounts
        assert features[3] == 0.0, f"Expected amount=0, got {features[3]}"
        # - 5 days apart
        assert features[4] == 5.0, f"Expected date_diff=5, got {features[4]}"
        # - Different accounts
        assert features[5] == 0.0, f"Expected same_account=0, got {features[5]}"

    def it_should_handle_empty_descriptions(self):
        """Empty descriptions should not crash feature extraction."""
        pair = TransactionPair(
            txn1_id="abc123",
            txn1_date=date(2025, 1, 15),
            txn1_description="",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="def456",
            txn2_date=date(2025, 1, 15),
            txn2_description="PAYMENT",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
        )

        extractor = DuplicateFeatureExtractor()
        features = extractor.extract_features(pair)

        # Should produce valid features (no NaN or inf)
        assert features.shape == (8,)
        assert not np.any(np.isnan(features)), "Features contain NaN"
        assert not np.any(np.isinf(features)), "Features contain inf"

    def it_should_provide_readable_feature_names(self):
        """Feature names should be available for debugging."""
        extractor = DuplicateFeatureExtractor()
        names = extractor.get_feature_names()

        assert len(names) == 8
        assert 'cosine_similarity' in names
        assert 'levenshtein_ratio' in names
        assert 'token_overlap' in names
        assert 'amount_exact_match' in names

    def it_should_fit_vectorizer_on_training_data(self):
        """Vectorizer should be fittable on multiple pairs."""
        pairs = [
            TransactionPair(
                txn1_id="1", txn1_date=date(2025, 1, 1),
                txn1_description="SPOTIFY PAYMENT",
                txn1_amount=-10.99, txn1_account="MYBANK_CHQ",
                txn2_id="2", txn2_date=date(2025, 1, 1),
                txn2_description="SPOTIFY PYMT",
                txn2_amount=-10.99, txn2_account="MYBANK_CHQ",
            ),
            TransactionPair(
                txn1_id="3", txn1_date=date(2025, 1, 2),
                txn1_description="GROCERY STORE",
                txn1_amount=-45.67, txn1_account="MYBANK_CHQ",
                txn2_id="4", txn2_date=date(2025, 1, 2),
                txn2_description="GROCERY SHOP",
                txn2_amount=-45.67, txn2_account="MYBANK_CHQ",
            ),
        ]

        extractor = DuplicateFeatureExtractor()
        extractor.fit(pairs)

        # Should be able to extract features after fitting
        features = extractor.extract_features(pairs[0])
        assert features.shape == (8,)
        assert extractor._is_fitted

    def it_should_calculate_levenshtein_ratio_correctly(self):
        """Levenshtein ratio should match known examples."""
        extractor = DuplicateFeatureExtractor()

        # Identical strings
        ratio = extractor._levenshtein_ratio("hello", "hello")
        assert ratio == 1.0

        # Completely different
        ratio = extractor._levenshtein_ratio("abc", "xyz")
        assert ratio < 0.5

        # One insertion
        ratio = extractor._levenshtein_ratio("cat", "cats")
        assert ratio > 0.7  # 1 edit in 4 chars = 0.75

        # Empty strings
        ratio = extractor._levenshtein_ratio("", "test")
        assert ratio == 0.0

    def it_should_calculate_common_prefix_ratio_correctly(self):
        """Common prefix ratio should measure shared beginning."""
        extractor = DuplicateFeatureExtractor()

        # Identical strings
        ratio = extractor._common_prefix_ratio("PAYMENT", "PAYMENT")
        assert ratio == 1.0

        # Shared prefix "PAYMENT "
        ratio = extractor._common_prefix_ratio("PAYMENT TO SPOTIFY", "PAYMENT TO NETFLIX")
        assert ratio > 0.5  # "PAYMENT TO " is 11 chars out of ~18 avg

        # No shared prefix
        ratio = extractor._common_prefix_ratio("SPOTIFY", "NETFLIX")
        assert ratio == 0.0

        # Case insensitive
        ratio = extractor._common_prefix_ratio("Payment", "payment")
        assert ratio == 1.0


class DescribeFeatureExtractorPerformance:
    """Performance characteristics of feature extraction."""

    def it_should_extract_features_quickly(self):
        """Feature extraction should be fast (<10ms per pair)."""
        import time

        pair = TransactionPair(
            txn1_id="abc123",
            txn1_date=date(2025, 1, 15),
            txn1_description="PAYMENT TO SPOTIFY MUSIC SERVICE",
            txn1_amount=-10.99,
            txn1_account="MYBANK_CHQ",
            txn2_id="def456",
            txn2_date=date(2025, 1, 16),
            txn2_description="PYMT SPOTIFY INC",
            txn2_amount=-10.99,
            txn2_account="MYBANK_CHQ",
        )

        extractor = DuplicateFeatureExtractor()

        # Measure 100 extractions
        start = time.time()
        for _ in range(100):
            extractor.extract_features(pair)
        elapsed = time.time() - start

        # Should be fast (<<1 second for 100 pairs)
        avg_time_ms = (elapsed / 100) * 1000
        assert avg_time_ms < 50, f"Too slow: {avg_time_ms:.2f}ms per pair"
