"""Local-only benchmark: compare raw-description vs normalized-merchant categorization.

Reads data/events.db from the current working directory and produces a
before/after comparison of categorization accuracy using held-out user events.

No data is written; no network I/O is performed.

Usage:
    uv run python scripts/benchmark_categorization.py
    uv run python scripts/benchmark_categorization.py --workspace /path/to/gilt/root
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _load_training_data(event_store_path: Path):
    """Load user-categorized transactions from the event store."""
    from gilt.ml.categorization_training_builder import CategorizationTrainingBuilder
    from gilt.storage.event_store import EventStore

    store = EventStore(str(event_store_path))
    builder = CategorizationTrainingBuilder(store)
    return builder.load_from_events(source_filter="user")


def _filter_to_min_samples(transaction_data, category_labels, min_samples: int = 3):
    """Filter to categories with at least min_samples examples."""
    from collections import Counter

    counts = Counter(category_labels)
    valid = {c for c, n in counts.items() if n >= min_samples}
    mask = [i for i, lbl in enumerate(category_labels) if lbl in valid]
    filtered_txns = [transaction_data[i] for i in mask]
    filtered_labels = [category_labels[i] for i in mask]
    return filtered_txns, filtered_labels


def _build_feature_matrix(
    descriptions, accounts, log_amounts, directions, fitted_vect=None, fitted_enc=None
):
    """Build combined TF-IDF + account + amount feature matrix."""
    import numpy as np
    from scipy.sparse import hstack as sp_hstack
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import OneHotEncoder

    if fitted_vect is None:
        vect = TfidfVectorizer(
            analyzer="word", lowercase=True, ngram_range=(1, 2), max_features=500, min_df=1
        )
        text_f = vect.fit_transform(descriptions)
    else:
        vect = fitted_vect
        text_f = vect.transform(descriptions)

    accts = np.array(accounts).reshape(-1, 1)
    if fitted_enc is None:
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        acct_f = enc.fit_transform(accts)
    else:
        enc = fitted_enc
        acct_f = enc.transform(accts)

    return sp_hstack([text_f, acct_f, log_amounts, directions]).toarray(), vect, enc


def _cv_accuracy(descriptions, accounts, log_amounts, directions, labels, k: int = 5) -> float:
    """Run stratified k-fold CV; return mean accuracy."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=42)
    accs = []
    for train_idx, test_idx in skf.split(descriptions, labels):
        tr_descs = [descriptions[i] for i in train_idx]
        te_descs = [descriptions[i] for i in test_idx]
        tr_accts = [accounts[i] for i in train_idx]
        te_accts = [accounts[i] for i in test_idx]

        X_tr, vect, enc = _build_feature_matrix(
            tr_descs, tr_accts, log_amounts[train_idx], directions[train_idx]
        )
        X_te, _, _ = _build_feature_matrix(
            te_descs,
            te_accts,
            log_amounts[test_idx],
            directions[test_idx],
            fitted_vect=vect,
            fitted_enc=enc,
        )

        clf = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
        clf.fit(X_tr, labels[train_idx])
        accs.append(clf.score(X_te, labels[test_idx]))
    return float(np.mean(accs))


def _print_sample_normalizations(raw_descriptions, norm_descriptions) -> None:
    """Print a sample of normalizations that changed the description."""
    print("\n--- Sample Normalizations ---")
    seen: set[str] = set()
    count = 0
    for raw, norm in zip(raw_descriptions, norm_descriptions, strict=False):
        if raw not in seen and norm != raw.lower().strip():
            seen.add(raw)
            print(f"  {raw[:55]!r:<57} -> {norm!r}")
            count += 1
        if count >= 10:
            break


def _run_benchmark(workspace_root: Path) -> None:
    """Run the before/after benchmark against data/events.db."""
    import numpy as np

    from gilt.ml.merchant_normalizer import normalize_merchant

    event_store_path = workspace_root / "data" / "events.db"
    if not event_store_path.exists():
        print(f"ERROR: Event store not found at {event_store_path}")
        print("Run this script from your gilt workspace root, or pass --workspace.")
        return

    print(f"Loading events from {event_store_path} ...")
    transaction_data, category_labels = _load_training_data(event_store_path)

    if not transaction_data:
        print("No user-categorized transactions found. Cannot benchmark.")
        return

    print(f"Loaded {len(transaction_data)} user-categorized transactions.")

    filtered_txns, filtered_labels = _filter_to_min_samples(transaction_data, category_labels)
    n_f = len(filtered_txns)
    unique_cats_f = sorted(set(filtered_labels))
    print(f"Filtered to {n_f} transactions across {len(unique_cats_f)} categories (≥3 each).")

    if n_f < 6 or len(unique_cats_f) < 2:
        print("Too few samples or categories for cross-validation. Exiting.")
        return

    raw_descriptions = [txn["description"] for txn in filtered_txns]
    norm_descriptions = [normalize_merchant(txn["description"]) for txn in filtered_txns]
    accounts = [txn.get("account", "") for txn in filtered_txns]
    amounts = np.array([txn["amount"] for txn in filtered_txns], dtype=float)
    log_amounts = (np.sign(amounts) * np.log1p(np.abs(amounts))).reshape(-1, 1)
    directions = np.sign(amounts).reshape(-1, 1)

    # Encode labels to integers
    cat_to_idx = {c: i for i, c in enumerate(unique_cats_f)}
    y = np.array([cat_to_idx[c] for c in filtered_labels])

    print("\nRunning 5-fold cross-validation (this may take a moment) ...")
    raw_acc = _cv_accuracy(raw_descriptions, accounts, log_amounts, directions, y)
    norm_acc = _cv_accuracy(norm_descriptions, accounts, log_amounts, directions, y)

    delta = norm_acc - raw_acc
    print("\n--- Benchmark Results ---")
    print(f"  Raw description accuracy:        {raw_acc:.1%}")
    print(f"  Normalized merchant accuracy:    {norm_acc:.1%}")
    print(f"  Delta (norm - raw):              {delta:+.1%}")

    if delta >= 0:
        print("\nNormalization is beneficial (>= baseline accuracy).")
    else:
        print("\nNormalization did not improve accuracy on this dataset.")
        print("This may happen with small datasets or well-separated raw descriptions.")

    _print_sample_normalizations(raw_descriptions, norm_descriptions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark categorization normalization.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("."),
        help="Path to gilt workspace root (default: current directory)",
    )
    args = parser.parse_args()
    _run_benchmark(args.workspace.resolve())


if __name__ == "__main__":
    main()
