"""Machine learning utilities for Finance application.

This package provides lightweight, fast ML-based duplicate detection
as an alternative to LLM-based approaches.
"""

from gilt.ml.feature_extractor import DuplicateFeatureExtractor
from gilt.ml.training_data_builder import TrainingDataBuilder

__all__ = ["DuplicateFeatureExtractor", "TrainingDataBuilder"]

# Optionally export classifier if lightgbm is installed
try:
    from gilt.ml.duplicate_classifier import DuplicateClassifier  # noqa: F401

    __all__.append("DuplicateClassifier")
except ImportError:
    pass  # LightGBM not installed, classifier not available
