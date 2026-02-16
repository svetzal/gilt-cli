"""Machine learning classifier for duplicate transaction detection.

Provides fast, lightweight duplicate detection using LightGBM classifier
trained on engineered features. Requires training data from user feedback.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import pickle

try:
    import lightgbm as lgb
except ImportError:
    lgb = None  # Allow module import even if lightgbm not installed

import numpy as np
import pandas as pd

from finance.model.duplicate import TransactionPair, DuplicateAssessment
from finance.ml.feature_extractor import DuplicateFeatureExtractor


class DuplicateClassifier:
    """LightGBM-based classifier for duplicate detection.

    This classifier uses engineered features from transaction pairs to predict
    whether they are duplicates. It provides:
    - Fast inference (~1ms per pair)
    - Confidence scores (probabilities)
    - Feature importance for interpretability

    Requires training on labeled examples (50-500 pairs recommended).
    """

    def __init__(self, model_path: Optional[Path] = None):
        """Initialize classifier, optionally loading a pre-trained model.

        Args:
            model_path: Path to saved model file (.pkl). If None, creates
                       untrained classifier.
        """
        if lgb is None:
            raise ImportError(
                "LightGBM not installed. Install with: pip install -e '.[ml]'"
            )

        self.feature_extractor = DuplicateFeatureExtractor()
        self.model: Optional[lgb.LGBMClassifier] = None
        self._is_trained = False

        if model_path and model_path.exists():
            self.load(model_path)

    def train(
        self,
        pairs: List[TransactionPair],
        labels: List[bool],
        validation_split: float = 0.2,
    ) -> dict:
        """Train classifier on labeled transaction pairs.

        Args:
            pairs: List of transaction pairs
            labels: List of boolean labels (True = duplicate)
            validation_split: Fraction of data to use for validation

        Returns:
            Dictionary with training metrics (accuracy, precision, recall)
        """
        if len(pairs) != len(labels):
            raise ValueError(
                f"Pairs ({len(pairs)}) and labels ({len(labels)}) must have same length"
            )

        if len(pairs) < 10:
            raise ValueError(
                f"Need at least 10 training examples, got {len(pairs)}"
            )

        # Fit vectorizer on all descriptions
        self.feature_extractor.fit(pairs)

        # Extract features
        X = np.vstack([self.feature_extractor.extract_features(p) for p in pairs])
        y = np.array(labels, dtype=int)

        # Convert to DataFrame with feature names to avoid sklearn warnings
        feature_names = self.feature_extractor.get_feature_names()
        X_df = pd.DataFrame(X, columns=feature_names)

        # Split train/validation
        n_val = max(1, int(len(pairs) * validation_split))
        indices = np.random.permutation(len(pairs))
        val_indices = indices[:n_val]
        train_indices = indices[n_val:]

        X_train, y_train = X_df.iloc[train_indices], y[train_indices]
        X_val, y_val = X_df.iloc[val_indices], y[val_indices]

        # Train LightGBM
        self.model = lgb.LGBMClassifier(
            objective='binary',
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=5,
            random_state=42,
            verbose=-1,  # Suppress training output
        )

        self.model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=10, verbose=False)],
        )

        self._is_trained = True

        # Calculate metrics
        train_pred = self.model.predict(X_train)
        val_pred = self.model.predict(X_val)

        train_acc = np.mean(train_pred == y_train)
        val_acc = np.mean(val_pred == y_val)

        # Precision/recall for duplicates (positive class)
        true_positives = np.sum((val_pred == 1) & (y_val == 1))
        false_positives = np.sum((val_pred == 1) & (y_val == 0))
        false_negatives = np.sum((val_pred == 0) & (y_val == 1))

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )

        return {
            'train_accuracy': float(train_acc),
            'val_accuracy': float(val_acc),
            'precision': float(precision),
            'recall': float(recall),
            'n_train': len(train_indices),
            'n_val': len(val_indices),
        }

    def predict(self, pair: TransactionPair) -> DuplicateAssessment:
        """Predict whether a transaction pair is a duplicate.

        Args:
            pair: Transaction pair to assess

        Returns:
            DuplicateAssessment with prediction, confidence, and reasoning
        """
        if not self._is_trained or self.model is None:
            raise RuntimeError("Model not trained. Call train() first or load a model.")

        # Extract features
        features = self.feature_extractor.extract_features(pair)

        # Convert to DataFrame with feature names to avoid sklearn warnings
        feature_names = self.feature_extractor.get_feature_names()
        features_df = pd.DataFrame([features], columns=feature_names)

        # Get probability for duplicate class (class 1)
        proba = self.model.predict_proba(features_df)[0, 1]
        is_duplicate = proba > 0.5

        # Generate reasoning based on feature importance
        reasoning = self._explain_prediction(features, proba)

        return DuplicateAssessment(
            is_duplicate=is_duplicate,
            confidence=float(proba if is_duplicate else (1 - proba)),
            reasoning=reasoning,
        )

    def _explain_prediction(self, features: np.ndarray, proba: float) -> str:
        """Generate human-readable reasoning for prediction.

        Args:
            features: Feature vector used for prediction
            proba: Predicted probability of duplicate

        Returns:
            Explanation string
        """
        feature_names = self.feature_extractor.get_feature_names()

        # Get top contributing features
        if self.model and hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            # Sort by importance
            sorted_indices = np.argsort(importances)[::-1][:3]  # Top 3

            reasons = []
            for idx in sorted_indices:
                name = feature_names[idx]
                value = features[idx]
                importance = importances[idx]

                if importance > 0.1:  # Only mention significant features
                    if name == 'cosine_similarity':
                        reasons.append(
                            f"description similarity: {value:.2f}"
                        )
                    elif name == 'amount_exact_match':
                        reasons.append("exact amount match" if value == 1 else "different amounts")
                    elif name == 'date_difference_days':
                        reasons.append(f"{int(value)} day(s) apart")
                    elif name == 'same_account':
                        reasons.append("same account" if value == 1 else "different accounts")

            if reasons:
                reason_str = ", ".join(reasons)
                return f"ML model ({proba:.1%} confidence): {reason_str}"

        # Fallback reasoning
        return f"ML model predicts {'duplicate' if proba > 0.5 else 'not duplicate'} ({proba:.1%})"

    def get_feature_importance(self) -> dict:
        """Get feature importance scores from trained model.

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not self._is_trained or self.model is None:
            raise RuntimeError("Model not trained")

        feature_names = self.feature_extractor.get_feature_names()
        importances = self.model.feature_importances_

        # Sort by importance (descending)
        sorted_indices = np.argsort(importances)[::-1]

        return {
            feature_names[idx]: float(importances[idx])
            for idx in sorted_indices
        }

    def save(self, path: Path) -> None:
        """Save trained model to disk.

        Args:
            path: Path to save model (.pkl file)
        """
        if not self._is_trained:
            raise RuntimeError("Cannot save untrained model")

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'feature_extractor': self.feature_extractor,
            }, f)

    def load(self, path: Path) -> None:
        """Load trained model from disk.

        Args:
            path: Path to saved model (.pkl file)
        """
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        with open(path, 'rb') as f:
            data = pickle.load(f)

        self.model = data['model']
        self.feature_extractor = data['feature_extractor']
        self._is_trained = True


__all__ = ["DuplicateClassifier"]
