## Duplicate detection — current implementation (concise)

This document describes the actual, deployed duplicate-detection behaviour
in the codebase. It is intentionally short and focused: it explains what the
system does today and how to inspect or reproduce it.

Summary
- Default detection: fast ML classifier (LightGBM) trained on user feedback.
- Fallback: LLM analysis when ML is unavailable or when `--llm` is passed.
- Training data: derived from event store `DuplicateConfirmed` / `DuplicateRejected` events.

Key behaviours
- `gilt duplicates` (default): uses the ML classifier when available.
- `gilt duplicates --llm`: forces LLM-based analysis (slower).
- `gilt duplicates --interactive` / `-i`: interactive reviewer that emits
  `DuplicateConfirmed` and `DuplicateRejected` events (dry-run by default).

Where training data comes from
- The ML training process reads user feedback events from the event store.
  Specifically it expects each `DuplicateSuggested` event to include a
  full transaction pair in `assessment['pair']`. Training examples are
  constructed from `DuplicateConfirmed` (positive) and `DuplicateRejected`
  (negative) events by referencing their source suggestion event.

Training lifecycle
- Training happens when `DuplicateDetector` is initialized with `use_ml=True`.
- The detector will only train a model if there are at least 10 labeled
  examples available (this threshold is configurable in code).
- If training fails or is insufficient, the system silently falls back to LLM.

Files and commands you can use right now
- Migration script (backfill historical events with pair data):
  `src/gilt/scripts/migrate_event_schema.py`
  - Dry-run: `python src/gilt/scripts/migrate_event_schema.py`
  - Apply:   `python src/gilt/scripts/migrate_event_schema.py --write`

- Audit current training data and predictions:
  `gilt audit-ml` (summary)
  `gilt audit-ml --mode training --limit 50` (show examples)
  `gilt audit-ml --mode predictions --limit 20` (show ML decisions)
  `gilt audit-ml --mode features` (feature importance and metrics)

- Run duplicate detection (ML default):
  `gilt duplicates`
  Force LLM: `gilt duplicates --llm`
  Interactive review: `gilt duplicates --interactive`

Important implementation notes
- Feature engineering and model code are in `src/gilt/ml/`:
  - `feature_extractor.py` — engineered feature set + TF-IDF
  - `duplicate_classifier.py` — LightGBM wrapper with predict/train
  - `training_data_builder.py` — builds pairs & labels from events
- The CLI integration is in `src/gilt/cli/command/duplicates.py` and
  the `audit-ml` helper is in `src/gilt/cli/command/audit_ml.py`.
- The system intentionally uses ML as the default because it is orders of
  magnitude faster than the LLM while matching user-labelled behaviour.

When to use the LLM
- Use `--llm` when you want a textual rationale or when the ML model is
  unavailable/insufficiently trained. The LLM is _much_ slower and is kept
  as a fallback for difficult cases.

If you want to change behaviour
- To re-train from scratch: run the migration (if needed), then restart the
  CLI; `DuplicateDetector` will train at init if enough examples exist.
- To inspect or correct training labels, use `gilt audit-ml --mode training`
  to find and correct mis-labelled historical feedback (you can then re-run
  training by reinitializing the detector or running a command that triggers it).

Contact / next steps
- If you want, I can:
  - Add a small command to re-train on demand (e.g. `gilt ml retrain`).
  - Add an option to fall back to LLM automatically when ML confidence < X.

This file intentionally contains only the concise, accurate description
of the current implementation and how to inspect it.

# Traditional ML Approach for Duplicate Detection

## Problem Statement

The current duplicate detection system uses a 30B parameter LLM (`qwen3:30b`) which is:
- **Extremely slow**: Each pair comparison requires a full LLM inference
- **Resource intensive**: Requires significant GPU/CPU resources
- **Overkill**: Binary classification doesn't need natural language generation

## Proposed Solution: TF-IDF + Cosine Similarity + Gradient Boosting

Replace LLM-based assessment with a lightweight, fast ML pipeline:

### Architecture Comparison

**Current (LLM-Based)**:
```
Transaction Pair
    ↓
[Load 30B LLM Model] ← 16GB+ RAM, 30s cold start
    ↓
[Build Prompt with Context] ← 200-500 tokens
    ↓
[LLM Inference] ← 2-5 seconds per pair
    ↓
[Parse Structured Output]
    ↓
{is_duplicate: bool, confidence: float, reasoning: string}
```

**Proposed (ML-Based)**:
```
Transaction Pair
    ↓
[Feature Engineering] ← <1ms, 8 numeric features
    ↓
[TF-IDF Vectorization] ← <1ms, character n-grams
    ↓
[LightGBM Inference] ← <1ms, tree ensemble
    ↓
{is_duplicate: bool, confidence: float, reasoning: string}
```

**Key Differences**:
- **LLM**: Slow, heavy, zero-shot learning, natural language reasoning
- **ML**: Fast, lightweight, requires training data, feature-based reasoning

### Why This Works

1. **TF-IDF for Description Similarity**
   - Captures word importance in transaction descriptions
   - Handles bank's text variations naturally
   - Very fast to compute (milliseconds vs seconds)

2. **Engineered Features**
   - Description cosine similarity (TF-IDF vectors)
   - Exact amount match (boolean)
   - Date difference in days
   - Character-level similarity (Levenshtein distance)
   - Token overlap ratio
   - Same account (boolean)

3. **LightGBM Classifier**
   - Fast inference (~1ms per prediction)
   - Handles non-linear relationships
   - Provides confidence scores naturally
   - Requires minimal training data (100-500 examples)

### Performance Comparison

| Metric | Current (LLM) | Proposed (ML) | Improvement |
|--------|---------------|---------------|-------------|
| Speed per pair | 2-5 seconds | <10ms | **200-500x faster** |
| Memory | 16GB+ | <1GB | **16x less** |
| Cold start | ~30s | <1s | **30x faster** |
| Accuracy | ~95%* | ~90-95%** | Comparable |
| Training data | None (zero-shot) | 100-500 pairs | Small dataset |

\* Estimated from LLM capabilities
\** With proper feature engineering

### Implementation Plan

#### Phase 1: Feature Engineering (1-2 hours)

Create `src/gilt/ml/feature_extractor.py`:

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import Levenshtein

class DuplicateFeatureExtractor:
    def __init__(self):
        # Use character n-grams for bank description variations
        self.vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(2, 4),
            lowercase=True,
            max_features=500
        )

    def extract_features(self, pair: TransactionPair) -> np.ndarray:
        """Extract features for duplicate detection."""
        # Text similarity features
        desc1_vec = self.vectorizer.transform([pair.txn1_description])
        desc2_vec = self.vectorizer.transform([pair.txn2_description])
        cosine_sim = cosine_similarity(desc1_vec, desc2_vec)[0, 0]

        # Character-level similarity
        levenshtein_ratio = Levenshtein.ratio(
            pair.txn1_description,
            pair.txn2_description
        )

        # Token overlap
        tokens1 = set(pair.txn1_description.lower().split())
        tokens2 = set(pair.txn2_description.lower().split())
        token_overlap = len(tokens1 & tokens2) / max(len(tokens1 | tokens2), 1)

        # Numerical features
        amount_match = float(abs(pair.txn1_amount - pair.txn2_amount) < 0.001)
        date_diff = abs((pair.txn1_date - pair.txn2_date).days)
        same_account = float(pair.txn1_account == pair.txn2_account)

        return np.array([
            cosine_sim,
            levenshtein_ratio,
            token_overlap,
            amount_match,
            date_diff,
            same_account,
            len(pair.txn1_description),
            len(pair.txn2_description),
        ])
```

#### Phase 2: Model Training (2-3 hours)

Create `src/gilt/ml/duplicate_classifier.py`:

```python
import lightgbm as lgb
from sklearn.model_selection import train_test_split

class DuplicateClassifier:
    def __init__(self):
        self.model = lgb.LGBMClassifier(
            objective='binary',
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            random_state=42
        )
        self.feature_extractor = DuplicateFeatureExtractor()

    def train(self, pairs: List[TransactionPair], labels: List[bool]):
        """Train on labeled examples."""
        X = np.vstack([self.feature_extractor.extract_features(p) for p in pairs])
        y = np.array(labels)

        self.model.fit(X, y)

    def predict(self, pair: TransactionPair) -> DuplicateAssessment:
        """Predict if pair is duplicate with confidence."""
        features = self.feature_extractor.extract_features(pair)

        # Get probability (0-1 for is_duplicate=True)
        proba = self.model.predict_proba(features.reshape(1, -1))[0, 1]
        is_duplicate = proba > 0.5

        # Generate reasoning based on feature importance
        reasoning = self._explain_prediction(features, proba)

        return DuplicateAssessment(
            is_duplicate=is_duplicate,
            confidence=proba if is_duplicate else (1 - proba),
            reasoning=reasoning
        )
```

#### Phase 3: Integration (1-2 hours)

Update `src/gilt/transfer/duplicate_detector.py`:

```python
class DuplicateDetector:
    def __init__(self, use_ml: bool = True, ...):
        self.use_ml = use_ml
        if use_ml:
            self.ml_classifier = self._load_or_train_ml_model()
        else:
            # Keep existing LLM path for backward compatibility
            self._llm = LLMBroker(model=model)

    def assess_duplicate(self, pair: TransactionPair) -> DuplicateAssessment:
        if self.use_ml:
            return self.ml_classifier.predict(pair)
        else:
            # Fall back to LLM
            return self._assess_duplicate_llm(pair)
```

#### Phase 4: Bootstrap Training Data (2-3 hours)

Strategy to get initial training data:

1. **Use existing LLM assessments** if available
   - User has already reviewed some duplicates
   - Load from `DuplicateConfirmed`/`DuplicateRejected` events

2. **Active learning loop**
   - Start with high-confidence rules (exact description match = not duplicate)
   - Use ML model with uncertainty sampling
   - Ask user to label only uncertain cases

3. **Synthetic negatives**
   - Generate obvious non-duplicates from existing data
   - Different amounts, different days, different accounts

Create `src/gilt/ml/training_data_builder.py`:

```python
class TrainingDataBuilder:
    def load_from_events(self, event_store: EventStore) -> Tuple[List[TransactionPair], List[bool]]:
        """Load training examples from user feedback events."""
        pairs = []
        labels = []

        # Get DuplicateConfirmed events (positive examples)
        for event in event_store.get_events_by_type("DuplicateConfirmed"):
            pair = self._reconstruct_pair(event)
            pairs.append(pair)
            labels.append(True)

        # Get DuplicateRejected events (negative examples)
        for event in event_store.get_events_by_type("DuplicateRejected"):
            pair = self._reconstruct_pair(event)
            pairs.append(pair)
            labels.append(False)

        return pairs, labels

    def generate_synthetic_negatives(self, transactions: List[Transaction], n: int = 100):
        """Generate obvious non-duplicates for training."""
        # Sample random pairs with different amounts/accounts
        # These are guaranteed negatives
        pass
```

### Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
  # ... existing ...
  "scikit-learn>=1.3,<2",
  "lightgbm>=4.0,<5",
  "python-Levenshtein>=0.20,<1",
  "numpy>=1.24,<2",
]
```

### Migration Path

1. **Keep LLM as fallback** for backward compatibility
2. **Add `--use-ml` flag** to `gilt duplicates` command
3. **Auto-train on first run** if sufficient feedback events exist (>50)
4. **Gradual rollout**: Test ML on subset, compare with LLM assessments
5. **Make ML default** once validated (keep `--use-llm` flag for opt-in)

### Expected Results

For a workspace with 1000 transactions (100 candidate pairs):

| Mode | Time | Resources |
|------|------|-----------|
| Current LLM | **200-500s** | 16GB RAM, GPU recommended |
| Proposed ML | **1-2s** | <1GB RAM, CPU only |

### Accuracy Validation

Create `src/gilt/ml/evaluate.py` to compare:

```python
def compare_llm_vs_ml(test_pairs: List[TransactionPair]):
    """Compare LLM and ML predictions on same data."""
    llm_detector = DuplicateDetector(use_ml=False)
    ml_detector = DuplicateDetector(use_ml=True)

    results = []
    for pair in test_pairs:
        llm_result = llm_detector.assess_duplicate(pair)
        ml_result = ml_detector.assess_duplicate(pair)

        results.append({
            'pair': pair,
            'llm_duplicate': llm_result.is_duplicate,
            'llm_confidence': llm_result.confidence,
            'ml_duplicate': ml_result.is_duplicate,
            'ml_confidence': ml_result.confidence,
            'agreement': llm_result.is_duplicate == ml_result.is_duplicate
        })

    agreement_rate = sum(r['agreement'] for r in results) / len(results)
    return results, agreement_rate
```

### Testing Strategy

1. **Unit tests** for feature extraction
2. **Integration tests** with known duplicate/non-duplicate pairs
3. **Regression tests** against LLM on labeled examples
4. **Performance benchmarks** (speed, memory)

### Future Enhancements

1. **Online learning**: Update model as user provides feedback
2. **Ensemble**: Combine ML + LLM for difficult cases (ML < 0.6 confidence)
3. **Feature selection**: Use SHAP to identify most important features
4. **Model compression**: Quantize LightGBM model for even faster inference

## Decision Framework Alignment

This approach follows the project's Simple Design Heuristics:

1. ✅ **All tests pass** - Full test coverage for ML components
2. ✅ **Reveals intent** - Features are explicit and interpretable
3. ✅ **No knowledge duplication** - Single source of duplicate detection logic
4. ✅ **Minimal entities** - Removes unnecessary LLM complexity

## Privacy Compliance

- ✅ All processing remains local (scikit-learn, LightGBM are local libraries)
- ✅ No network I/O required
- ✅ Model training happens on-device
- ✅ No external API calls

## Recommendation

**Start with Phase 4 (training data) first**: Load existing user feedback from events, then implement Phases 1-3. This ensures we have real data to validate the approach before full implementation.

Estimated total implementation time: **6-10 hours** for full working system.
