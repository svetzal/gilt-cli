"""
CLI command to audit ML classifier decisions and training data.

Provides visibility into:
- Training data used by ML classifier
- Feature importance
- Predictions on current candidates
- Past user decisions that shaped the model
"""

from __future__ import annotations

from gilt.config import DEFAULT_OLLAMA_MODEL
from gilt.ml.training_data_builder import TrainingDataBuilder
from gilt.transfer.duplicate_detector import DuplicateDetector
from gilt.workspace import Workspace

from ..console import console, print_error
from ..event_sourcing_bootstrap import require_event_sourcing
from .audit_ml_view import (
    print_valid_modes,
    show_features,
    show_predictions,
    show_summary,
    show_training_data,
)


def run(
    workspace: Workspace,
    mode: str = "summary",
    filter_pattern: str | None = None,
    limit: int = 20,
) -> int:
    """Audit ML classifier training data and decisions.

    Args:
        workspace: Workspace for resolving data paths
        mode: Audit mode - "summary", "training", "predictions", or "features"
        filter_pattern: Optional regex pattern to filter descriptions
        limit: Maximum number of examples to show (default 20)

    Returns:
        Exit code (0 = success)
    """
    ready = require_event_sourcing(workspace)
    event_store = ready.event_store
    builder = TrainingDataBuilder(event_store)

    if mode == "summary":
        return show_summary(console, builder)
    elif mode == "training":
        return show_training_data(console, builder, filter_pattern, limit)
    elif mode == "predictions":
        detector, candidates = _load_predictions(workspace, filter_pattern, limit)
        return show_predictions(console, detector, candidates, filter_pattern, limit)
    elif mode == "features":
        return show_features(console, builder)
    else:
        print_error(f"Unknown mode '{mode}'")
        print_valid_modes(console)
        return 1


def _load_predictions(workspace: Workspace, filter_pattern: str | None, limit: int):
    """Load detector and candidate pairs. Returns (detector, candidates) or (None, None) if unavailable."""
    import re

    data_dir = workspace.ledger_data_dir
    detector = DuplicateDetector(
        model=DEFAULT_OLLAMA_MODEL,
        event_store_path=workspace.event_store_path,
        projections_path=workspace.projections_path,
        use_ml=True,
    )

    if not detector._ml_classifier:
        return None, None

    transactions = detector.load_all_transactions(data_dir)
    candidates = detector.find_potential_duplicates(transactions)

    if filter_pattern:
        pattern = re.compile(filter_pattern, re.IGNORECASE)
        candidates = [
            p
            for p in candidates
            if pattern.search(p.txn1_description) or pattern.search(p.txn2_description)
        ]

    return detector, candidates


__all__ = ["run"]
