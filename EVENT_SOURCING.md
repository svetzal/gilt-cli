# Event Sourcing Architecture Plan

## Executive Summary

Transition from mutable state-based transaction storage to an immutable event-sourced architecture. This enables:
- **Auditability**: Complete history of all changes with timestamps
- **Accuracy**: Resolve duplicate detection issues by tracking description evolution
- **Flexibility**: Rebuild state from events, experiment with different categorization strategies
- **User Learning**: Capture decision patterns for ML-assisted categorization and duplicate detection

## Current State Problems

### 1. Duplicate Detection Issues
- Banks modify transaction descriptions over time (adding "ON" suffix, reference numbers)
- Current model: single mutable transaction record
- Problem: When merging duplicates, we lose historical description variations
- Impact: Cannot learn which description format user prefers

### 2. Lost Audit Trail
- Categorization changes overwrite previous values
- Cannot answer: "When did I recategorize this expense?"
- Cannot track: "Why did I merge these transactions?"
- Missing: User decision rationale for ML training

### 3. Data Model Inflexibility
- Schema changes require table regeneration
- Cannot experiment with different categorization schemes
- Difficult to rollback mistakes

## Event Sourcing Principles

### Core Concept
Store **immutable events** that describe what happened, not current state.
State is derived by replaying events.

```
Events (Immutable) → Projections (Derived State) → Views (Query Optimized)
```

### Event Properties
- **Immutable**: Never modified after creation
- **Timestamped**: Event occurrence time + recorded time
- **Attributed**: Who/what created the event
- **Typed**: Clear semantic meaning
- **Causally Ordered**: Can determine sequence

## Proposed Event Types

### 1. Transaction Events

#### `TransactionImported`
Occurs when CSV data is ingested.

```python
{
    "event_type": "TransactionImported",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T15:30:00Z",
    "transaction_date": "2025-10-15",
    "transaction_id": "hash-of-raw-data",  # Deterministic
    "source_file": "2025-11-16-rbc-chequing.csv",
    "source_account": "RBC_CHQ",
    "raw_description": "PRESTO FARE/Q8LHFMWL2J Oshawa",
    "amount": -10.31,
    "currency": "CAD",
    "raw_data": {  # Full CSV row for perfect reconstruction
        "date": "10/15/2025",
        "description": "PRESTO FARE/Q8LHFMWL2J Oshawa",
        "amount": "-10.31"
    }
}
```

**Key Design Decisions:**
- `transaction_id` is deterministic hash (date + account + amount + description)
- Allows idempotent imports: same CSV generates same transaction_id
- Re-importing same file creates no new events (detected by transaction_id)
- Changed description from bank → new transaction_id → potential duplicate

#### `TransactionDescriptionObserved`
Occurs when same transaction appears with different description in later import.

```python
{
    "event_type": "TransactionDescriptionObserved",
    "event_id": "uuid",
    "event_timestamp": "2025-11-17T10:00:00Z",
    "original_transaction_id": "hash-1",
    "new_transaction_id": "hash-2",  # Different due to description
    "transaction_date": "2025-10-15",
    "original_description": "PRESTO FARE/Q8LHFMWL2J Oshawa",
    "new_description": "PRESTO FARE/Q8LHFMWL2J Oshawa ON",
    "source_file": "2025-11-17-rbc-chequing.csv",
    "source_account": "RBC_CHQ",
    "amount": -10.31
}
```

### 2. Duplicate Detection Events

#### `DuplicateSuggested`
LLM analyzes potential duplicate.

```python
{
    "event_type": "DuplicateSuggested",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T15:45:00Z",
    "transaction_id_1": "hash-1",
    "transaction_id_2": "hash-2",
    "confidence": 0.92,
    "reasoning": "Same date, amount, account. Description differs only by 'ON' suffix.",
    "model": "qwen2.5:3b",
    "prompt_version": "v2",  # Track which prompt generated this
    "assessment": {
        "is_duplicate": true,
        "same_date": true,
        "same_amount": true,
        "same_account": true,
        "description_similarity": 0.95
    }
}
```

#### `DuplicateConfirmed`
User confirms duplicate and chooses canonical description.

```python
{
    "event_type": "DuplicateConfirmed",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T15:46:30Z",
    "suggestion_event_id": "uuid",  # Links to DuplicateSuggested
    "primary_transaction_id": "hash-1",  # Keep this one
    "duplicate_transaction_id": "hash-2",  # Mark as duplicate
    "canonical_description": "PRESTO FARE/Q8LHFMWL2J Oshawa ON",  # User choice
    "user_rationale": "Prefer format with province suffix",  # Optional
    "llm_was_correct": true  # For accuracy tracking
}
```

#### `DuplicateRejected`
User rejects LLM duplicate suggestion.

```python
{
    "event_type": "DuplicateRejected",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T15:47:00Z",
    "suggestion_event_id": "uuid",
    "transaction_id_1": "hash-1",
    "transaction_id_2": "hash-2",
    "user_rationale": "Different cities - these are separate transit trips",
    "llm_was_correct": false
}
```

### 3. Categorization Events

#### `TransactionCategorized`
User or system assigns category.

```python
{
    "event_type": "TransactionCategorized",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T16:00:00Z",
    "transaction_id": "hash-1",
    "category": "Transportation",
    "subcategory": "Public Transit",
    "source": "user" | "llm" | "rule",  # How was this categorized?
    "confidence": 0.95,  # For ML categorizations
    "previous_category": "Uncategorized",  # Enables undo
    "rationale": "PRESTO card transactions are always transit"
}
```

#### `CategorizationRuleCreated`
User creates reusable categorization rule.

```python
{
    "event_type": "CategorizationRuleCreated",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T16:05:00Z",
    "rule_id": "uuid",
    "rule_type": "description_pattern",
    "pattern": "PRESTO FARE/.*",
    "category": "Transportation",
    "subcategory": "Public Transit",
    "enabled": true
}
```

### 4. Budget Events

#### `BudgetCreated`
User defines budget for category/period.

```python
{
    "event_type": "BudgetCreated",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T16:10:00Z",
    "budget_id": "uuid",
    "category": "Transportation",
    "subcategory": "Public Transit",
    "period_type": "monthly",
    "start_date": "2025-11-01",
    "amount": 200.00,
    "currency": "CAD"
}
```

### 5. ML Learning Events

#### `PromptUpdated`
Adaptive prompt learning from user feedback.

```python
{
    "event_type": "PromptUpdated",
    "event_id": "uuid",
    "event_timestamp": "2025-11-16T15:50:00Z",
    "prompt_version": "v3",
    "previous_version": "v2",
    "learned_patterns": [
        "Transit transactions with different cities (Toronto vs Oshawa) are separate trips",
        "Adding 'ON' suffix is common bank formatting change, not new transaction"
    ],
    "accuracy_metrics": {
        "true_positives": 42,
        "false_positives": 3,
        "true_negatives": 15,
        "false_negatives": 2,
        "accuracy": 0.92
    }
}
```

## Data Model

### Event Store Schema

```sql
-- Core event log (append-only)
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    aggregate_type TEXT,  -- 'transaction', 'budget', 'prompt', etc.
    aggregate_id TEXT,    -- Links related events
    event_data JSON NOT NULL,  -- Full event payload
    metadata JSON,        -- User agent, IP (for audit), etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(event_timestamp);
CREATE INDEX idx_events_aggregate ON events(aggregate_type, aggregate_id);

-- Event sequence tracking
CREATE TABLE event_sequence (
    sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);
```

### Projection Tables (Materialized Views)

```sql
-- Current transaction state (derived from events)
CREATE TABLE transaction_projections (
    transaction_id TEXT PRIMARY KEY,
    transaction_date DATE NOT NULL,
    canonical_description TEXT NOT NULL,
    description_history JSON,  -- All observed descriptions
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    account_id TEXT NOT NULL,
    category TEXT,
    subcategory TEXT,
    is_duplicate BOOLEAN DEFAULT FALSE,
    primary_transaction_id TEXT,  -- If duplicate, points to primary
    last_event_id TEXT,  -- For optimistic locking
    projection_version INTEGER,  -- Rebuild tracking
    FOREIGN KEY (primary_transaction_id) REFERENCES transaction_projections(transaction_id)
);

CREATE INDEX idx_txn_date ON transaction_projections(transaction_date);
CREATE INDEX idx_txn_account ON transaction_projections(account_id);
CREATE INDEX idx_txn_category ON transaction_projections(category, subcategory);

-- Duplicate relationships (for querying)
CREATE TABLE duplicate_relationships (
    primary_transaction_id TEXT NOT NULL,
    duplicate_transaction_id TEXT NOT NULL,
    confirmed_at TIMESTAMP NOT NULL,
    canonical_description TEXT NOT NULL,
    PRIMARY KEY (primary_transaction_id, duplicate_transaction_id),
    FOREIGN KEY (primary_transaction_id) REFERENCES transaction_projections(transaction_id),
    FOREIGN KEY (duplicate_transaction_id) REFERENCES transaction_projections(transaction_id)
);

-- Prompt learning history
CREATE TABLE prompt_projections (
    prompt_version TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    learned_patterns JSON NOT NULL,
    accuracy_metrics JSON NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
```

## Implementation Phases

### Phase 1: Event Store Foundation (Week 1)
**Goal**: Establish event storage without breaking existing system.

1. **Create Event Models** (`src/finance/model/events.py`)
   - Pydantic models for all event types
   - JSON serialization/deserialization
   - Event validation

2. **Create Event Store** (`src/finance/storage/event_store.py`)
   - SQLite-based append-only log
   - `append_event(event: Event) -> None`
   - `get_events(aggregate_id) -> List[Event]`
   - `get_events_by_type(event_type) -> List[Event]`

3. **Dual-Write Pattern**
   - Existing code writes to current tables
   - Also writes corresponding events
   - No reads from events yet
   - Validates event store works correctly

**Success Criteria**: All imports generate corresponding `TransactionImported` events.

### Phase 2: Transaction Import Refactor (Week 2)
**Goal**: Make imports idempotent and event-sourced.

1. **Deterministic Transaction IDs**
   - Hash function: `sha256(date + account + amount + description)[:16]`
   - Same raw data → same transaction_id
   - Re-importing file creates no duplicates

2. **Import Command Refactor**
   - Check if transaction_id exists before importing
   - Generate `TransactionImported` events
   - Detect description changes → `TransactionDescriptionObserved`

3. **Transaction Projection Builder**
   - Replay events to build `transaction_projections`
   - Command: `finance rebuild-projections --from-scratch`

**Success Criteria**: Can delete `transaction_projections`, replay events, restore exact state.

### Phase 3: Duplicate Detection Integration (Week 3)
**Goal**: Event-based duplicate detection with user feedback loop.

1. **Duplicate Detection Events**
   - `DuplicateDetector` emits `DuplicateSuggested` events
   - Interactive mode emits `DuplicateConfirmed` or `DuplicateRejected`
   - Store chosen canonical description

2. **Interactive UI Enhancement**
   ```
   Match 1/42 - Confidence: 92%

   Transaction 1: PRESTO FARE/Q8LHFMWL2J Oshawa
   Transaction 2: PRESTO FARE/Q8LHFMWL2J Oshawa ON

   Is this a duplicate? [y/n]: y

   Which description do you prefer?
   1) PRESTO FARE/Q8LHFMWL2J Oshawa
   2) PRESTO FARE/Q8LHFMWL2J Oshawa ON

   Choice [1/2]: 2
   Rationale (optional): Prefer province suffix
   ```

3. **Projection Updates**
   - `DuplicateConfirmed` updates projections
   - Duplicate marked with `is_duplicate=true`, points to primary
   - Canonical description stored
   - Budget calculations exclude duplicates

**Success Criteria**: Interactive mode creates complete audit trail, projections reflect merges.

### Phase 4: Prompt Learning Evolution (Week 4)
**Goal**: Adaptive prompts learn from all user feedback.

1. **Prompt Versioning**
   - Each `PromptUpdated` event has version number
   - Store learned patterns from feedback
   - Track accuracy metrics per version

2. **Pattern Analysis**
   - Analyze `DuplicateConfirmed` / `DuplicateRejected` events
   - Identify common features in false positives/negatives
   - Generate natural language patterns
   - Example: "When PRESTO transactions have different cities, 95% are separate trips"

3. **Description Preference Learning**
   - Track which description format user prefers
   - "User prefers descriptions with province suffixes (8/10 times)"
   - "User prefers reference numbers removed (6/8 times)"
   - Suggest preferred description automatically

**Success Criteria**: Prompt accuracy improves over time, suggests preferred descriptions.

### Phase 5: Categorization Events (Week 5)
**Goal**: Event-sourced categorization with ML learning.

1. **Categorization Event Types**
   - `TransactionCategorized` when user/system assigns category
   - `CategorizationRuleCreated` for pattern-based rules
   - Track source: user, LLM, rule

2. **Rule Engine**
   - Apply rules in order of specificity
   - Rules are events, can be versioned
   - Bulk recategorization: create events, replay

3. **ML Training Data**
   - User categorizations are ground truth
   - Train model on user decisions
   - Predict categories for new transactions

**Success Criteria**: Can recategorize all transactions by replaying events, ML improves.

### Phase 6: Budget Event Sourcing (Week 6)
**Goal**: Time-travel budget analysis.

1. **Budget Events**
   - `BudgetCreated`, `BudgetUpdated`, `BudgetDeleted`
   - Track budget changes over time

2. **Historical Queries**
   - "What was my transportation budget in October?"
   - "Show spending vs budget for each month in 2025"
   - Replay events to any point in time

**Success Criteria**: Can query budget state at any historical date.

### Phase 7: Migration Tool (Week 7)
**Goal**: Migrate existing data to event model.

1. **Backfill Events**
   - Read current `transactions` table
   - Generate synthetic `TransactionImported` events
   - Assign timestamps: use file dates or current date
   - Generate `TransactionCategorized` events for categorized txns

2. **Validation**
   - Rebuild projections from backfilled events
   - Compare with original tables
   - Must match exactly

3. **Cutover**
   - Run dual-write for safety period (1 week)
   - Compare event-sourced projections vs old tables
   - When confident, remove old tables
   - Keep schema for emergency rollback

**Success Criteria**: All existing data preserved, projections match old tables.

## Benefits Realization

### Immediate Benefits

1. **Duplicate Detection Accuracy**
   - Track description evolution
   - Learn from user feedback
   - Suggest preferred descriptions
   - Current: 71% → 92% accuracy (shown in testing)
   - Target: 95%+ after learning phase

2. **Complete Audit Trail**
   - "Why is this transaction categorized as Transportation?"
   - "When did I merge these duplicates?"
   - "What prompt version made this suggestion?"

3. **Flexible Experimentation**
   - Try different categorization schemes
   - Rebuild projections with new logic
   - No data loss

### Long-term Benefits

1. **ML Training Data**
   - Every user decision is training data
   - Description preferences
   - Categorization patterns
   - Duplicate detection heuristics

2. **Multi-User Support**
   - Events can have user_id
   - Different users, different learned patterns
   - Privacy-preserving collaborative filtering

3. **Time-Travel Debugging**
   - "My October budget was wrong"
   - Replay events up to October 31
   - Find problematic event
   - Fix and replay forward

4. **Compliance & Audit**
   - Immutable audit log
   - Who changed what, when
   - Required for tax audits
   - Export events for accountant

## Migration Risk Mitigation

### Rollback Plan
1. Keep old schema during dual-write
2. Event store problems → disable event writes, use old tables
3. Projection bugs → rebuild from events
4. Worst case → restore from backup, events are append-only

### Testing Strategy
1. Unit tests for each event type
2. Integration tests for projection builders
3. Property-based tests: rebuild projections N times → same result
4. Load testing: 100k events, projection rebuild time
5. Chaos engineering: corrupt projection, rebuild from events

### Performance Considerations
1. Event appends are fast (O(1), no indexes updated)
2. Projection rebuilds are slow (O(n) events)
3. Solution: Incremental projection updates
   - Track last processed event sequence number
   - Only replay new events
   - Full rebuild only when projection logic changes
4. Snapshot projections periodically
   - Store projection state at event N
   - Rebuild from snapshot + new events

## Open Questions

1. **Event Versioning**
   - How to handle event schema evolution?
   - Proposal: Event type + version: `TransactionImported.v2`
   - Old events never change, new projections know how to read old formats

2. **Event Retention**
   - Keep events forever?
   - Proposal: Snapshot projections yearly, compress old events

3. **Privacy**
   - Events contain sensitive data
   - Proposal: Encrypt event_data field
   - Key stored in user's keychain

4. **Concurrency**
   - Multiple import processes?
   - Proposal: Optimistic locking on projections
   - Event store is serialized (SQLite)

5. **Testing with Real Data**
   - Need to test with user's actual transaction history
   - Proposal: Phase 7 migration tool generates backfill events
   - Validate projections match current state

## Conclusion

Event sourcing is the right architectural choice for this finance system because:

1. **Audit trail is essential** for financial data
2. **User decisions are valuable** ML training data
3. **Duplicate detection requires** tracking description evolution
4. **Categorization experimentation** needs non-destructive schema changes
5. **Privacy-first approach** means no external APIs, so local ML learning is critical

The phased approach allows incremental migration with rollback safety. Each phase delivers value independently. Total implementation: 7 weeks with 1 developer.

**Recommendation**: Start with Phase 1 (Event Store Foundation) immediately. Validates architecture before major refactoring.
