# Auto-Categorization with Machine Learning

## Overview

The Gilt application now supports **automatic transaction categorization** using machine learning. The system learns from your manual categorizations and can automatically suggest categories for new transactions.

## How It Works

### Event-Driven Learning

Every time you categorize a transaction (via CLI or GUI), the system:

1. **Emits a `TransactionCategorized` event** to the event store
2. **Tracks the decision** with context:
   - Transaction description and amount
   - Assigned category and subcategory
   - Previous category (if re-categorizing)
   - Source: `user` (manual), `llm` (LLM-assisted), or `rule` (pattern-based)

3. **Builds training data** from accumulated events
4. **Trains a classifier** to predict categories for new transactions

### Machine Learning Model

- **Algorithm**: Random Forest Classifier
- **Features**:
  - TF-IDF vectors from transaction descriptions (captures semantic patterns)
  - Transaction amount (normalized with log transform)
  - Unigrams and bigrams for multi-word patterns

- **Training Requirements**:
  - Minimum 5 samples per category (configurable)
  - Uses 80/20 train/test split
  - Balanced class weights to handle imbalanced categories

## Usage

### Quick Start

The simplest way to use auto-categorization is through the CLI command:

```bash
# 1. Build training data by categorizing transactions manually
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
gilt categorize --desc-prefix "LOBLAWS" --category "Groceries" --yes --write

# 2. Auto-categorize new transactions (dry-run)
gilt auto-categorize

# 3. Review and apply
gilt auto-categorize --write
```

### CLI Command: `gilt auto-categorize`

**Basic Usage:**

```bash
# Dry-run with default confidence (0.7)
gilt auto-categorize

# Apply predictions with write flag
gilt auto-categorize --write

# Higher confidence threshold (fewer but more accurate predictions)
gilt auto-categorize --confidence 0.8 --write

# Interactive review mode
gilt auto-categorize --interactive --write

# Limit to specific account
gilt auto-categorize --account MYBANK_CHQ --write

# Process only first N transactions
gilt auto-categorize --limit 50 --write
```

**Options:**

- `--confidence, -c FLOAT` - Minimum confidence threshold (0.0-1.0), default: 0.7
- `--interactive, -i` - Enable interactive review mode
- `--account, -a ACCOUNT` - Filter to specific account
- `--limit, -n N` - Max number of transactions to process
- `--min-samples N` - Minimum samples per category for training, default: 5
- `--write` - Persist changes (default: dry-run)

### Interactive Review Mode

Review each prediction and approve/reject/modify:

```bash
gilt auto-categorize --interactive --write
```

For each transaction, you can:
- **`a`** - Approve the prediction
- **`r`** - Reject and leave uncategorized
- **`m`** - Modify to a different category
- **`q`** - Quit and save approved so far

Example session:
```
Transaction 1/5
  Account:     MYBANK_CC
  Date:        2025-02-15
  Description: SPOTIFY PREMIUM
  Amount:      $-12.99
  Suggested:   Entertainment:Music (85.3% confident)

Action [a/r/m/q] (a): a
✓ Approved

Transaction 2/5
  Account:     MYBANK_CHQ
  Date:        2025-02-16
  Description: UNKNOWN MERCHANT
  Amount:      $-50.00
  Suggested:   Shopping:Online (62.1% confident)

Action [a/r/m/q] (a): m

Available categories:
  - Entertainment
  - Groceries
  - Shopping
    - Shopping:Online
  - Housing
    - Housing:Utilities

Enter category (Category or Category:Subcategory) [Shopping:Online]: Groceries
✓ Modified to Groceries
```

### Programmatic Usage

For more control, use the Python API directly:

### 1. Categorize Transactions Manually

First, build up training data by categorizing transactions:

```bash
# Categorize recurring subscriptions
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
gilt categorize --desc-prefix "NETFLIX" --category "Entertainment:Streaming" --yes --write

# Categorize groceries
gilt categorize --desc-prefix "LOBLAWS" --category "Groceries" --yes --write
gilt categorize --desc-prefix "SOBEYS" --category "Groceries" --yes --write

# Categorize utilities
gilt categorize --pattern "Payment.*EXAMPLE UTILITY" --category "Housing:Utilities" --yes --write
```

### 2. Train the Classifier

Once you have sufficient categorizations (at least 5 per category):

```python
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.ml.categorization_classifier import CategorizationClassifier

# Initialize
event_service = EventSourcingService()
event_store = event_service.get_event_store()

# Create and train classifier
classifier = CategorizationClassifier(
    event_store,
    min_samples_per_category=5,
)

metrics = classifier.train()
print(f"Training complete!")
print(f"Accuracy: {metrics['test_accuracy']:.2%}")
print(f"Categories learned: {metrics['num_categories']}")
```

### 3. Auto-Categorize New Transactions

Use the trained classifier to suggest categories:

```python
# Single transaction
category, confidence = classifier.predict_single(
    description="SPOTIFY PREMIUM SUBSCRIPTION",
    amount=-12.99,
    account="MC",
    confidence_threshold=0.7,
)

if category:
    print(f"Suggested: {category} (confidence: {confidence:.2%})")
else:
    print("No confident prediction - manual categorization needed")

# Batch predictions
transactions = [
    {"description": "LOBLAWS GROCERY", "amount": -45.67, "account": "CHQ", ...},
    {"description": "NETFLIX MONTHLY", "amount": -15.99, "account": "MC", ...},
]

predictions = classifier.predict(transactions, confidence_threshold=0.7)
for txn, (category, confidence) in zip(transactions, predictions):
    if category:
        print(f"{txn['description']}: {category} ({confidence:.2%})")
```

## Confidence Thresholds

The classifier returns a confidence score (0.0-1.0) for each prediction:

- **0.9-1.0**: Very confident - safe to auto-apply
- **0.7-0.9**: Confident - good for suggestions
- **0.5-0.7**: Uncertain - review before applying
- **< 0.5**: Not confident - requires manual categorization

Set `confidence_threshold` based on your tolerance for errors:

```python
# Conservative (fewer errors, more manual work)
predictions = classifier.predict(txns, confidence_threshold=0.9)

# Balanced (recommended)
predictions = classifier.predict(txns, confidence_threshold=0.7)

# Aggressive (more automation, some errors)
predictions = classifier.predict(txns, confidence_threshold=0.5)
```

## Model Insights

### Feature Importance

See which words/patterns are most important for classification:

```python
important_features = classifier.get_feature_importance(top_n=20)

for feature, importance in important_features:
    print(f"{feature}: {importance:.4f}")
```

Example output:
```
spotify: 0.0856
loblaws: 0.0743
netflix: 0.0621
utility: 0.0512
amount: 0.0489
grocery: 0.0432
...
```

### Training Metrics

The `train()` method returns detailed metrics:

```python
{
    "total_samples": 145,
    "num_categories": 12,
    "train_accuracy": 0.95,
    "test_accuracy": 0.89,
    "train_size": 116,
    "test_size": 29,
    "categories": [
        "Entertainment:Music",
        "Entertainment:Streaming",
        "Groceries",
        "Housing:Utilities",
        ...
    ]
}
```

## Architecture

### Event Flow

```
User categorizes       TransactionCategorized      Training Data
transaction      →     event emitted          →    Builder extracts
(CLI/GUI)              to event store              features

                                                    ↓

Predict category  ←    RandomForest           ←    Classifier trains
for new txn            Classifier                  on features
```

### Components

1. **`CategorizationService`** (`src/gilt/services/categorization_service.py`)
   - Emits `TransactionCategorized` events when categorizing
   - Optional `event_store` parameter enables tracking

2. **`CategorizationTrainingBuilder`** (`src/gilt/ml/categorization_training_builder.py`)
   - Extracts training data from categorization events
   - Builds TF-IDF features from descriptions
   - Filters categories with too few samples

3. **`CategorizationClassifier`** (`src/gilt/ml/categorization_classifier.py`)
   - RandomForest classifier for category prediction
   - Confidence scoring for prediction quality
   - Feature importance analysis

## Best Practices

### 1. Build Diverse Training Data

Categorize a variety of transactions for each category:

```bash
# Good: Multiple merchants per category
gilt categorize --desc-prefix "LOBLAWS" --category "Groceries" --write
gilt categorize --desc-prefix "SOBEYS" --category "Groceries" --write
gilt categorize --desc-prefix "METRO" --category "Groceries" --write

# Bad: Only one merchant pattern
gilt categorize --desc-prefix "LOBLAWS" --category "Groceries" --write
```

### 2. Re-train Periodically

Re-train the classifier as you categorize more transactions:

```python
# After categorizing more transactions
classifier.train()
```

The model will improve with more training data.

### 3. Use Confidence Thresholds Appropriately

- **High threshold (0.8+)**: Auto-apply categories without review
- **Medium threshold (0.6-0.8)**: Show suggestions for user confirmation
- **Low threshold (< 0.6)**: Require manual categorization

### 4. Review Auto-Categorizations

Even with high confidence, occasionally review auto-categorized transactions:

```bash
# Review recent categorizations
gilt ytd --limit 50 | grep "Entertainment"
```

### 5. Handle Ambiguous Cases

Some transactions may be legitimately ambiguous:

```
"AMAZON.CA" → Shopping:Online or Groceries or Books?
```

For these, establish a rule or pattern:
- Amazon Fresh orders → Groceries
- Amazon books → Entertainment:Books
- Other Amazon → Shopping:Online

## Integration with CLI

The categorization events are automatically tracked when using the CLI:

```bash
# Every --write categorization creates an event
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --write
# → TransactionCategorized event emitted to event store
```

No additional flags needed - event tracking happens transparently.

## Future Enhancements

### Planned Features

1. **Auto-categorization command**
   ```bash
   gilt auto-categorize --confidence 0.7 --write
   ```

2. **Interactive review mode**
   ```bash
   gilt review-suggestions
   # Shows predictions, allows approve/reject/modify
   ```

3. **LLM-assisted learning**
   - Use local LLM to explain categorization reasoning
   - Learn from corrections to improve prompts

4. **Rule generation**
   - Extract high-confidence patterns as categorization rules
   - `"SPOTIFY*" → Entertainment:Music (confidence: 0.95)`

5. **Category similarity**
   - Suggest related categories for edge cases
   - "Did you mean Entertainment:Music or Entertainment:Podcasts?"

## Troubleshooting

### "Insufficient training data"

You need at least `min_samples_per_category` (default: 5) for each category.

**Solution**: Categorize more transactions or lower the threshold:

```python
classifier = CategorizationClassifier(
    event_store,
    min_samples_per_category=3,  # Lower threshold
)
```

### Low accuracy

Training accuracy < 70% indicates poor model performance.

**Causes**:
- Too few training samples
- Very similar descriptions across different categories
- Inconsistent categorizations

**Solutions**:
- Categorize more diverse examples
- Review and fix inconsistent categorizations
- Create more specific subcategories

### Predictions always None

All predictions below confidence threshold.

**Solution**: Lower the threshold or categorize more examples:

```python
predictions = classifier.predict(txns, confidence_threshold=0.5)
```

## Privacy & Security

- **Local-only**: All training and inference happens on your machine
- **No network I/O**: Model never transmitted or uploaded
- **Event store**: Contains sensitive financial data - keep secure
- **Scikit-learn only**: No external ML services or APIs

## See Also

- [Event Sourcing Architecture](event-sourcing-architecture.md)
- [ML Duplicate Detection](duplicate-detection-ml-proposal.md)
- [Categorization Service](../developer/technical/budgeting-system.md#transaction-categorization)
