# Project Structure

This document describes the file and directory organization of the Finance project.

## Overview

Finance follows a standard Python package structure with clear separation between CLI, GUI, and core business logic.

```
finance/
├── config/                   # Configuration files
│   ├── accounts.yml         # Account definitions
│   └── categories.yml       # Category hierarchy
├── ingest/                  # Raw bank CSV files (gitignored)
├── data/                    # Processed data (gitignored)
│   └── accounts/           # Normalized ledger CSVs
├── reports/                 # Generated reports (gitignored)
├── docs/                    # Documentation (MkDocs)
├── src/                     # Source code
│   └── finance/            # Main package
│       ├── cli/            # Command-line interface
│       ├── gui/            # Graphical interface
│       ├── model/          # Data models
│       ├── ingest/         # Import logic
│       └── transfer/       # Transfer linking
├── tests/                   # Test files (if using separate directory)
├── pyproject.toml          # Python project configuration
├── mkdocs.yml              # Documentation configuration
├── README.md               # Project README
└── .gitignore              # Git ignore patterns
```

## Source Code Organization

### Core Package (`src/finance/`)

```
src/finance/
├── __init__.py             # Package initialization
├── cli/                    # Command-line interface
│   ├── __init__.py
│   ├── app.py             # Main CLI entry point (Typer)
│   └── command/           # Individual commands
│       ├── __init__.py
│       ├── accounts.py
│       ├── ingest.py
│       ├── categorize.py
│       ├── budget.py
│       └── ...
├── gui/                    # Graphical interface
│   ├── __init__.py
│   ├── app.py             # Main GUI entry point
│   ├── main_window.py     # Main window
│   ├── views/             # View components
│   │   ├── dashboard_view.py
│   │   ├── transactions_view.py
│   │   ├── categories_view.py
│   │   ├── budget_view.py
│   │   └── import_wizard.py
│   ├── dialogs/           # Modal dialogs
│   │   ├── categorize_dialog.py
│   │   ├── note_dialog.py
│   │   ├── preview_dialog.py
│   │   └── settings_dialog.py
│   ├── widgets/           # Custom widgets
│   │   └── transaction_table.py
│   ├── models/            # Qt data models
│   │   └── transaction_model.py
│   ├── services/          # Business logic
│   │   ├── transaction_service.py
│   │   ├── category_service.py
│   │   ├── budget_service.py
│   │   └── import_service.py
│   └── resources/         # UI resources
│       └── styles_dark.qss
├── model/                  # Core data models
│   ├── __init__.py
│   ├── account.py         # Account model
│   ├── category.py        # Category model
│   ├── category_io.py     # Category I/O
│   └── ledger_io.py       # Ledger CSV I/O
├── ingest/                 # Import/normalization
│   └── __init__.py        # Ingest logic
└── transfer/               # Transfer linking
    ├── __init__.py
    ├── linker.py          # Transfer linker
    └── matching.py        # Matching algorithms
```

## File Naming Conventions

### Python Files

- **Modules**: `snake_case.py` (e.g., `transaction_service.py`)
- **Test files**: `*_spec.py` (e.g., `transaction_service_spec.py`)
- **Private modules**: `_internal.py` (single underscore prefix)

### Configuration Files

- **YAML**: `.yml` extension (e.g., `accounts.yml`)
- **Config directory**: `config/`

### Data Files

- **Ledger CSVs**: `<ACCOUNT_ID>.csv` (e.g., `RBC_CHQ.csv`)
- **Directory**: `data/accounts/`

### Documentation

- **Markdown**: `.md` extension
- **Directory**: `docs/`
- **Structure**: Mirrors navigation in `mkdocs.yml`

## Import Conventions

### Absolute Imports

Always use absolute imports from the package root:

```python
# Good
from finance.model.account import Account
from finance.cli.command.util import validate_category

# Avoid
from ..model.account import Account
from .util import validate_category
```

### Module Organization

Group imports in this order:

```python
# 1. Standard library
import sys
from pathlib import Path
from typing import Optional

# 2. Third-party
from pydantic import BaseModel
from rich.console import Console

# 3. Local package
from finance.model.account import Account
from finance.model.ledger_io import load_ledger_csv
```

## Testing Structure

Tests use the `_spec.py` suffix and mirror the source structure:

```
src/finance/model/category.py      → src/finance/model/category_spec.py
src/finance/cli/command/budget.py  → src/finance/cli/command/budget_spec.py
```

Test discovery: `pytest` finds all `*_spec.py` files automatically.

## Configuration Files

### pyproject.toml

Project metadata and dependencies:

```toml
[project]
name = "finance"
version = "1.0.0"
dependencies = [...]

[project.optional-dependencies]
gui = ["PySide6", ...]
dev = ["pytest", "ruff", ...]

[project.scripts]
finance = "finance.cli.app:main"
finance-gui = "finance.gui.app:main"
```

### mkdocs.yml

Documentation configuration:

```yaml
site_name: Finance
theme:
  name: material
nav:
  - Home: index.md
  - User Guide: user/index.md
  - Developer Guide: developer/index.md
```

### accounts.yml

User account configuration (not in repo):

```yaml
accounts:
  - account_id: RBC_CHQ
    description: "RBC Chequing"
    source_patterns:
      - "*rbc*chq*.csv"
```

### categories.yml

User category configuration (not in repo by default):

```yaml
categories:
  - name: "Housing"
    budget:
      amount: 2500.00
      period: monthly
    subcategories:
      - name: "Rent"
      - name: "Utilities"
```

## Data Directory Structure

### Input (ingest/)

Raw bank CSV exports:

```
ingest/
├── 2025-11-16-rbc-chequing.csv
├── 2025-11-16-rbc-mc.csv
└── ...
```

### Output (data/accounts/)

Normalized ledger files:

```
data/accounts/
├── RBC_CHQ.csv
├── RBC_MC.csv
├── SCOTIA_CURR.csv
└── ...
```

### Reports (reports/)

Generated reports:

```
reports/
├── budget_report_2025_10.md
├── budget_report_2025_11.md
└── ...
```

## Related Documents

- [System Design](system-design.md) - Architecture overview
- [Data Model](data-model.md) - Schema details
- [Development Setup](../development/setup.md) - How to set up dev environment
