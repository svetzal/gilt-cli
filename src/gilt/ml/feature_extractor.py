"""Feature extraction for duplicate transaction detection.

Extracts multiple similarity features from transaction pairs to enable
fast ML-based duplicate classification without requiring LLM inference.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from gilt.model.duplicate import TransactionPair


class DuplicateFeatureExtractor:
    """Extracts features from transaction pairs for duplicate detection.

    Features extracted:
    1. TF-IDF cosine similarity (captures semantic description similarity)
    2. Levenshtein ratio (character-level similarity)
    3. Token overlap ratio (word-level similarity)
    4. Amount exact match (boolean)
    5. Date difference in days
    6. Same account (boolean)
    7. Description length difference
    8. Common prefix length ratio
    """

    def __init__(self):
        """Initialize feature extractor with TF-IDF vectorizer.

        Uses character n-grams (2-4) to capture bank description variations
        like "PAYMENT SPOTIFY" vs "PYMT SPOTIFY INC".
        """
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",  # Character n-grams with word boundaries
            ngram_range=(2, 4),  # Bigrams, trigrams, 4-grams
            lowercase=True,
            max_features=500,  # Limit vocabulary for speed
            min_df=1,  # Include even rare patterns
        )
        self._is_fitted = False

    def fit(self, pairs: list[TransactionPair]) -> None:
        """Fit TF-IDF vectorizer on training data.

        Args:
            pairs: List of transaction pairs to learn vocabulary from
        """
        all_descriptions = []
        for pair in pairs:
            all_descriptions.append(pair.txn1_description)
            all_descriptions.append(pair.txn2_description)

        self.vectorizer.fit(all_descriptions)
        self._is_fitted = True

    def extract_features(self, pair: TransactionPair) -> np.ndarray:
        """Extract feature vector from a transaction pair.

        Args:
            pair: Transaction pair to extract features from

        Returns:
            Feature vector as numpy array (8 features)
        """
        # Ensure vectorizer is fitted (use identity transform if not)
        if not self._is_fitted:
            # For single pair, fit on these two descriptions
            self.vectorizer.fit([pair.txn1_description, pair.txn2_description])
            self._is_fitted = True

        # 1. TF-IDF cosine similarity
        desc1_vec = self.vectorizer.transform([pair.txn1_description])
        desc2_vec = self.vectorizer.transform([pair.txn2_description])
        cosine_sim = float(cosine_similarity(desc1_vec, desc2_vec)[0, 0])

        # 2. Levenshtein ratio (character-level similarity)
        # Use simple implementation to avoid external dependency initially
        lev_ratio = self._levenshtein_ratio(pair.txn1_description, pair.txn2_description)

        # 3. Token overlap ratio
        tokens1 = set(pair.txn1_description.lower().split())
        tokens2 = set(pair.txn2_description.lower().split())
        token_overlap = len(tokens1 & tokens2) / max(len(tokens1 | tokens2), 1)

        # 4. Amount exact match (within tolerance)
        amount_match = float(abs(pair.txn1_amount - pair.txn2_amount) < 0.001)

        # 5. Date difference in days
        date_diff = float(abs((pair.txn1_date - pair.txn2_date).days))

        # 6. Same account
        same_account = float(pair.txn1_account == pair.txn2_account)

        # 7. Description length difference (normalized)
        len1 = len(pair.txn1_description)
        len2 = len(pair.txn2_description)
        length_diff = abs(len1 - len2) / max(len1, len2, 1)

        # 8. Common prefix length ratio
        prefix_ratio = self._common_prefix_ratio(pair.txn1_description, pair.txn2_description)

        return np.array(
            [
                cosine_sim,  # [0-1] Higher = more similar
                lev_ratio,  # [0-1] Higher = more similar
                token_overlap,  # [0-1] Higher = more similar
                amount_match,  # {0, 1} 1 = exact match
                date_diff,  # [0-∞] Lower = more similar
                same_account,  # {0, 1} 1 = same account
                length_diff,  # [0-1] Lower = more similar
                prefix_ratio,  # [0-1] Higher = more similar
            ]
        )

    def get_feature_names(self) -> list[str]:
        """Return human-readable feature names."""
        return [
            "cosine_similarity",
            "levenshtein_ratio",
            "token_overlap",
            "amount_exact_match",
            "date_difference_days",
            "same_account",
            "length_difference",
            "common_prefix_ratio",
        ]

    @staticmethod
    def _levenshtein_ratio(s1: str, s2: str) -> float:
        """Calculate Levenshtein ratio (0-1, higher is more similar).

        Simple implementation without external dependencies.
        Uses dynamic programming to compute edit distance.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity ratio from 0.0 (completely different) to 1.0 (identical)
        """
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Compute Levenshtein distance using DP
        rows = len(s1) + 1
        cols = len(s2) + 1

        # Use two rows for space efficiency
        prev_row = list(range(cols))
        curr_row = [0] * cols

        for i in range(1, rows):
            curr_row[0] = i
            for j in range(1, cols):
                if s1[i - 1] == s2[j - 1]:
                    curr_row[j] = prev_row[j - 1]  # No operation needed
                else:
                    curr_row[j] = 1 + min(
                        prev_row[j],  # Deletion
                        curr_row[j - 1],  # Insertion
                        prev_row[j - 1],  # Substitution
                    )
            prev_row, curr_row = curr_row, prev_row

        distance = prev_row[-1]
        max_len = max(len(s1), len(s2))

        # Convert distance to similarity ratio
        return 1.0 - (distance / max_len)

    @staticmethod
    def _common_prefix_ratio(s1: str, s2: str) -> float:
        """Calculate ratio of common prefix length to average length.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Ratio from 0.0 (no common prefix) to 1.0 (identical strings)
        """
        if not s1 or not s2:
            return 0.0

        # Find common prefix length (case-insensitive)
        s1_lower = s1.lower()
        s2_lower = s2.lower()

        prefix_len = 0
        for c1, c2 in zip(s1_lower, s2_lower, strict=False):
            if c1 == c2:
                prefix_len += 1
            else:
                break

        # Normalize by average string length
        avg_len = (len(s1) + len(s2)) / 2
        return prefix_len / avg_len if avg_len > 0 else 0.0


__all__ = ["DuplicateFeatureExtractor"]
