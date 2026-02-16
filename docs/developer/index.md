# Developer Guide

Welcome to the Gilt Developer Guide. This section helps you understand the architecture, contribute code, and extend Gilt's capabilities.

## Overview

Gilt is a privacy-first financial management tool built with Python, following these principles:

- **Local-only**: No network I/O
- **Privacy-first**: All data stays on the user's machine
- **Deterministic**: Same inputs → same outputs
- **Safe by default**: Dry-run mode with explicit write flags
- **Testable**: Comprehensive test coverage
- **Modular**: Clear separation of concerns

## Architecture

Gilt uses a layered architecture:

```
┌─────────────────────────────────────┐
│     Presentation Layer              │
│  (CLI Commands / GUI Views)         │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│      Business Logic Layer           │
│  (Services / Managers)              │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│         Data Layer                  │
│  (Models / I/O / CSV Files)         │
└─────────────────────────────────────┘
```

### Key Components

- **[System Design](architecture/system-design.md)**: Overall architecture and design decisions
- **[Project Structure](architecture/project-structure.md)**: File organization and module layout
- **[Data Model](architecture/data-model.md)**: Transaction schema and data structures

### Technical Implementation

- **[CLI Implementation](technical/cli-implementation.md)**: Command-line interface design
- **[GUI Implementation](technical/gui-implementation.md)**: Qt6 graphical interface (Phase 1-4)
- **[Budgeting System](technical/budgeting-system.md)**: Category and budget tracking
- **[Transfer Linking](technical/transfer-linking.md)**: Automatic transfer detection

## Development

### Getting Started

1. **[Development Setup](development/setup.md)**: Set up your development environment
2. **[Testing](development/testing.md)**: Run and write tests
3. **[Contributing](development/contributing.md)**: Contribution guidelines and workflow

### Technology Stack

**Core**:
- Python 3.13+
- Pydantic for data validation
- CSV for data storage
- YAML for configuration

**CLI**:
- Typer for command-line interface
- Rich for terminal output

**GUI**:
- PySide6 (Qt6) for UI
- Qt Charts for visualization
- Qt threading for background operations

**Testing**:
- pytest for test framework
- pytest-qt for GUI testing

### Code Organization

```
src/gilt/
├── cli/                  # Command-line interface
│   ├── app.py           # Main CLI entry point
│   └── command/         # Individual commands
├── gui/                  # Graphical interface
│   ├── app.py           # Main GUI entry point
│   ├── views/           # UI views
│   ├── dialogs/         # Modal dialogs
│   ├── widgets/         # Custom widgets
│   ├── models/          # Qt data models
│   └── services/        # Business logic
├── model/               # Data models
│   ├── account.py       # Account definitions
│   ├── category.py      # Category structure
│   └── ledger_io.py     # CSV I/O operations
├── ingest/              # CSV import/normalization
└── transfer/            # Transfer linking logic
```

## Design Patterns

### Dry-Run by Default

All mutation operations default to dry-run mode:

```python
def categorize_transactions(
    transactions: List[Transaction],
    category: str,
    write: bool = False  # Always defaults to False
) -> Result:
    # Perform operation
    if write:
        save_to_disk(transactions)
    return Result(preview=transactions)
```

### Preview-Before-Commit

GUI operations show previews before applying changes:

```python
# 1. Compute changes in dry-run
preview = service.categorize(txns, category, write=False)

# 2. Show preview dialog
dialog = PreviewDialog(preview)
if dialog.exec():
    # 3. User confirmed - now write
    service.categorize(txns, category, write=True)
```

### Separation of Concerns

- **Models**: Pure data structures (Pydantic)
- **I/O**: File reading/writing operations
- **Services**: Business logic
- **Views/Commands**: User interface

### Signal-Based Communication (GUI)

Qt signals for loose coupling:

```python
class CategoryService(QObject):
    categories_modified = Signal()  # Emitted after changes

class CategoriesView(QWidget):
    def __init__(self):
        self.service.categories_modified.connect(
            self.reload_categories
        )
```

## Key Algorithms

### Transaction ID Generation

Deterministic hash for duplicate detection:

```python
def generate_transaction_id(
    account_id: str,
    date: str,
    amount: float,
    description: str
) -> str:
    content = f"{account_id}|{date}|{amount}|{description}"
    hash = hashlib.sha256(content.encode()).hexdigest()
    return hash[:16]  # First 16 characters
```

### Transfer Linking

Match transfers between accounts using:
- Date window (within N days)
- Amount matching (with epsilon tolerance)
- Interac e-Transfer detection
- Directional matching (debit ↔ credit)

See [Transfer Linking](technical/transfer-linking.md) for details.

### Budget Proration

Automatic period conversion:

```python
def prorate_budget(
    amount: float,
    period: BudgetPeriod,
    target_period: BudgetPeriod
) -> float:
    if period == BudgetPeriod.MONTHLY:
        if target_period == BudgetPeriod.YEARLY:
            return amount * 12
    elif period == BudgetPeriod.YEARLY:
        if target_period == BudgetPeriod.MONTHLY:
            return amount / 12
    return amount
```

## Testing Strategy

### Unit Tests

Test individual components in isolation:

```python
def test_transaction_id_deterministic():
    """Transaction ID should be same for same inputs."""
    tx1 = create_transaction("MYBANK_CHQ", "2025-01-01", -50.0, "Grocery")
    tx2 = create_transaction("MYBANK_CHQ", "2025-01-01", -50.0, "Grocery")
    assert tx1.transaction_id == tx2.transaction_id
```

### Integration Tests

Test component interactions:

```python
def test_import_and_categorize_workflow():
    """Full workflow: import → categorize → verify."""
    # Import transactions
    result = import_service.import_file("test.csv", write=True)

    # Categorize
    categorize_service.categorize(
        result.transactions[0].transaction_id,
        "Housing:Rent",
        write=True
    )

    # Verify persisted
    ledger = load_ledger_csv("MYBANK_CHQ.csv")
    assert ledger[0].category == "Housing"
```

### GUI Tests

Test GUI workflows with pytest-qt:

```python
def test_categorize_dialog(qtbot):
    """Test categorization dialog workflow."""
    dialog = CategorizeDialog(transactions)
    qtbot.addWidget(dialog)

    # Select category
    dialog.category_combo.setCurrentText("Housing")
    dialog.subcategory_combo.setCurrentText("Rent")

    # Verify preview
    assert dialog.preview_table.rowCount() == len(transactions)

    # Accept
    qtbot.mouseClick(dialog.apply_button, Qt.LeftButton)
```

## Implementation History

Gilt has evolved through several phases:

- **[Phase 2](history/phase2-summary.md)**: Data Management (categories, notes, categorization)
- **[Phase 3](history/phase3-summary.md)**: CSV Import Wizard
- **[Phase 4](history/phase4-summary.md)**: Budget & Dashboard

Each phase built incrementally on previous work, maintaining backward compatibility.

## Contributing

We welcome contributions! See the [Contributing Guide](development/contributing.md) for:

- Code style guidelines
- Pull request process
- Development workflow
- Testing requirements

## Resources

### Documentation

- **User Guide**: Learn to use Gilt
- **API Reference**: Module and function documentation
- **Architecture Docs**: Deep dives into design

### External Resources

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)

## Questions?

- **Issues**: [GitHub Issues](https://github.com/svetzal/gilt/issues)
- **Discussions**: Start a discussion on GitHub
- **Code**: Explore the source code for examples

## What's Next?

New to Gilt development? Start here:

1. [Development Setup](development/setup.md)
2. [System Architecture](architecture/system-design.md)
3. [Run Tests](development/testing.md)

Want to contribute? Check out:

- [Contributing Guidelines](development/contributing.md)
- [Open Issues](https://github.com/svetzal/gilt/issues)
- Implementation history for context
