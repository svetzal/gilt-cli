# System Design

This document describes the overall architecture and design decisions for Finance.

## Design Principles

### 1. Local-Only Operation

**Principle**: All processing happens on the user's machine.

**Implementation**:
- No network I/O in any module
- No external API calls
- No cloud services or remote databases
- All data stored in local CSV and YAML files

**Benefits**:
- Complete privacy control
- Works offline
- Fast processing
- No service dependencies

### 2. Privacy-First

**Principle**: User financial data never leaves their machine.

**Implementation**:
- Plain CSV files (user can inspect/modify)
- No encryption needed (user controls file system)
- No telemetry or analytics
- No update checks without permission

**Security Model**:
- User's file system permissions = Finance's security
- User can encrypt files at OS level
- User can backup/delete data anytime

### 3. Deterministic Behavior

**Principle**: Same inputs always produce same outputs.

**Implementation**:
- Transaction IDs from SHA-256 hash
- Reproducible imports (no timestamps)
- No random elements
- Idempotent operations

**Benefits**:
- Testable and predictable
- Safe to re-run operations
- Easy to debug issues

### 4. Safe by Default

**Principle**: Mutation requires explicit opt-in.

**Implementation**:
- `--write` flag required for changes
- Dry-run mode shows previews
- Confirmation dialogs in GUI
- Preview-before-commit pattern

**Safety Features**:
- Accidental data loss prevented
- User sees changes before applying
- Easy to experiment safely

## Architecture Layers

```
┌────────────────────────────────────────────────┐
│          Presentation Layer                    │
│  ┌──────────────┐    ┌───────────────────┐    │
│  │  CLI         │    │  GUI              │    │
│  │  (Typer)     │    │  (PySide6/Qt6)    │    │
│  └──────────────┘    └───────────────────┘    │
└────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────┐
│         Business Logic Layer                   │
│  ┌──────────────────────────────────────────┐ │
│  │  Services                                │ │
│  │  - TransactionService                    │ │
│  │  - CategoryService                       │ │
│  │  - BudgetService                         │ │
│  │  - ImportService                         │ │
│  └──────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────┐
│              Data Layer                        │
│  ┌──────────────┐    ┌───────────────────┐    │
│  │  Models      │    │  I/O               │    │
│  │  (Pydantic)  │    │  (CSV/YAML)        │    │
│  └──────────────┘    └───────────────────┘    │
└────────────────────────────────────────────────┘
```

### Presentation Layer

**CLI (Command Line Interface)**:
- Typer framework for commands
- Rich library for formatted output
- Flat command structure (`finance <verb>`)
- Pipeable output for scripting

**GUI (Graphical User Interface)**:
- PySide6 (Qt6) framework
- Model-View-Controller pattern
- Signal/slot communication
- Threading for long operations

### Business Logic Layer

**Services** contain all business logic:
- **TransactionService**: Load, filter, search transactions
- **CategoryService**: Manage categories and budgets
- **BudgetService**: Calculate budget vs actual
- **ImportService**: CSV import and normalization

Services are:
- UI-agnostic (work with CLI and GUI)
- Stateless (or minimal state)
- Testable in isolation

### Data Layer

**Models** define data structures:
- Pydantic models for validation
- Immutable where possible
- Type-safe

**I/O** handles persistence:
- CSV files for transaction data
- YAML files for configuration
- Simple, inspectable formats
- No binary databases

## Data Flow

### Import Flow

```
Bank CSV → ImportService → Normalize → Ledger CSV
                ↓
         Detect Transfers
                ↓
         Link Transfers → Update Metadata
```

**Steps**:
1. User exports CSV from bank
2. Places file in `ingest/` directory
3. `ImportService` reads raw CSV
4. Normalizes to standard schema
5. Generates transaction IDs
6. Writes to `data/accounts/<ACCOUNT>.csv`
7. Links inter-account transfers
8. Updates metadata in ledger files

### Categorization Flow

```
User Input → Service → Load Ledger → Update → Save Ledger
                                         ↓
                                    Dry-Run Preview
```

**Steps**:
1. User specifies transaction(s) and category
2. Service loads ledger from CSV
3. Finds matching transactions
4. In dry-run: returns preview
5. With `--write`: updates and saves CSV

### Budget Calculation Flow

```
Category Config + Ledger Data → Aggregate → Prorate → Compare
                                                         ↓
                                                    Budget Report
```

**Steps**:
1. Load categories with budgets from YAML
2. Load all transactions from ledger CSVs
3. Filter by date range
4. Aggregate spending by category
5. Prorate budgets for period
6. Calculate remaining/over budget
7. Generate report

## File Organization

### Standard Directory Structure

```
finance/
├── config/
│   ├── accounts.yml      # Account definitions
│   └── categories.yml    # Category hierarchy and budgets
├── ingest/               # Raw bank CSV files (input)
│   ├── 2025-11-16-rbc-chq.csv
│   └── ...
├── data/
│   └── accounts/         # Normalized ledger files (output)
│       ├── RBC_CHQ.csv
│       ├── RBC_MC.csv
│       └── ...
├── reports/              # Generated reports (optional)
│   └── budget_report_2025_10.md
└── src/finance/          # Source code
    ├── cli/              # CLI commands
    ├── gui/              # GUI application
    ├── model/            # Data models
    ├── ingest/           # Import logic
    └── transfer/         # Transfer linking
```

### File Conventions

**Ledger Files** (`data/accounts/<ACCOUNT>.csv`):
- One file per account
- Standard schema (transaction_id, date, amount, etc.)
- Append-only (new imports add rows)
- Updates modify existing rows (by transaction_id)

**Config Files** (`config/*.yml`):
- YAML format (human-readable)
- Version controlled (safe to commit)
- No sensitive data

**Ingest Files** (`ingest/*.csv`):
- Raw bank exports (immutable)
- Not parsed directly by app (copied during import)
- Can be deleted after import (if backed up elsewhere)

## Key Design Decisions

### Why CSV for Transactions?

**Pros**:
- Human-readable
- Easy to inspect/edit
- Standard format
- No database overhead
- Version control friendly

**Cons**:
- Slower for large datasets (10k+ transactions)
- No indexing
- Full file read/write

**Decision**: CSV is good enough for personal finance (typically < 10k transactions). If needed, can add SQLite cache layer without changing CSV storage.

### Why YAML for Config?

**Pros**:
- Human-readable
- Comments supported
- Hierarchical data
- Python libraries available

**Cons**:
- Whitespace-sensitive
- Can be verbose

**Decision**: YAML is better than JSON for config (comments, readability) and simpler than TOML for our needs.

### Why Separate CLI and GUI?

**Pros**:
- CLI can be used on servers
- GUI is optional dependency
- Different user preferences
- Each optimized for its interface

**Cons**:
- More code to maintain
- Duplication of business logic (mitigated by services)

**Decision**: Both interfaces valuable. Services layer prevents duplication.

### Why Qt6 for GUI?

**Pros**:
- Mature, cross-platform
- Native look and feel
- Rich widget library
- Charts and visualization built-in
- Python bindings (PySide6)

**Cons**:
- Large dependency (~100 MB)
- Learning curve

**Decision**: Qt6 is the best option for desktop Python GUI. Alternatives (tkinter, wxPython) lack polish or are less maintained.

## Transaction ID Design

### Requirements

- Unique identifier for each transaction
- Deterministic (same transaction → same ID)
- Short enough to type (for CLI)
- Collision-resistant

### Implementation

```python
def generate_transaction_id(
    account_id: str,
    date: str,
    amount: float,
    description: str
) -> str:
    """Generate deterministic transaction ID."""
    content = f"{account_id}|{date}|{amount}|{description}"
    hash_bytes = hashlib.sha256(content.encode('utf-8')).digest()
    return hash_bytes.hex()[:16]  # First 16 hex chars
```

**Properties**:
- 16 characters (8 bytes)
- Hex encoding (readable)
- SHA-256 (collision-resistant)
- Includes all identifying fields

**Usage**:
- CLI commands accept 8-char prefix (usually unique)
- Full ID stored in CSV
- Used for duplicate detection on import

## Performance Considerations

### Current Performance

For typical personal finance:
- **Transaction count**: 1,000 - 5,000 per year
- **Load time**: < 1 second
- **Import time**: < 2 seconds
- **Memory usage**: < 50 MB

### Scalability

If performance becomes an issue:

1. **Add in-memory caching**
   - Load ledgers once, cache in memory
   - Invalidate on file changes
   - 10x speedup for repeated operations

2. **Add SQLite read cache**
   - Build SQLite database from CSVs
   - Use for queries and filters
   - Rebuild when CSVs change
   - 100x speedup for searches

3. **Lazy loading**
   - Load only visible transactions
   - Pagination in GUI
   - Stream processing for reports

**Decision**: Optimize only when needed. CSV is simple and fast enough for now.

## Error Handling

### Principles

1. **Fail fast**: Detect errors early
2. **Clear messages**: Tell user what went wrong and how to fix
3. **Graceful degradation**: Continue when possible
4. **No silent failures**: Always log or display errors

### Implementation

**CLI**:
```python
try:
    result = import_service.import_file(path)
except FileNotFoundError:
    console.print(f"[red]Error:[/red] File not found: {path}")
    sys.exit(1)
except ValidationError as e:
    console.print(f"[red]Validation error:[/red] {e}")
    sys.exit(1)
```

**GUI**:
```python
try:
    result = service.categorize(txids, category, write=True)
    self.show_success("Categorized successfully")
except Exception as e:
    QMessageBox.critical(
        self,
        "Categorization Failed",
        f"Error: {str(e)}\n\nPlease try again."
    )
```

## Testing Strategy

### Unit Tests

Test individual components:
- Models (validation)
- I/O functions (read/write)
- Business logic (services)

### Integration Tests

Test component interactions:
- Import → categorize → report
- CLI command workflows
- GUI dialog workflows

### Test Coverage

Target: 80%+ coverage for:
- Business logic (services)
- Data models
- I/O operations

UI tests are lower priority (harder to maintain).

## Future Enhancements

### Considered but Deferred

**Multi-currency support**:
- Currently assumes single currency per account
- Could add currency conversion
- Requires exchange rate data (privacy concern)

**Machine learning categorization**:
- Auto-suggest categories based on description
- Would need to run locally (privacy)
- Complexity not justified yet

**Cloud sync**:
- Violates privacy-first principle
- User can use their own sync (Dropbox, etc.)
- Not planned

**Mobile app**:
- Would require significant work
- Web view could work (local server)
- Not planned

## Related Documents

- [Project Structure](project-structure.md) - File organization
- [Data Model](data-model.md) - Schema details
- [CLI Implementation](../technical/cli-implementation.md) - CLI design
- [GUI Implementation](../technical/gui-implementation.md) - GUI design
