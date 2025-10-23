# Finance Local - Qt6 GUI

This is the graphical user interface for Finance Local, built with Qt6 (PySide6).

## Installation

### Prerequisites
- Python 3.13 or higher
- Virtual environment (activated)

### Install GUI Dependencies

```bash
# Make sure your virtual environment is activated
source .venv/bin/activate

# Install the package with GUI dependencies
pip install -e .[gui]
```

This will install PySide6 and all required dependencies.

## Running the GUI

Once installed, you can launch the GUI with:

```bash
finance-gui
```

Or directly with Python:

```bash
python -m finance.gui.app
```

## Features (Phase 1)

### Current Features
- **Transaction Viewing**: Browse all transactions across all accounts
- **Advanced Filtering**:
  - Filter by account (single or all)
  - Filter by date range
  - Filter by category
  - Search by description/counterparty
  - Show only uncategorized transactions
- **Sortable Columns**: Click any column header to sort
- **Color-coded Amounts**:
  - Red: Negative (debits)
  - Green: Positive (credits)
  - Blue: Transfer indicators
- **Settings Dialog**: Configure data directories and default currency
- **Status Bar**: Shows transaction count and selection info

### UI Layout

```
┌────────────────────────────────────────────────────┐
│  File  View  Help                                  │
├──────────┬─────────────────────────────────────────┤
│          │  ┌──────────────────────────────────┐   │
│ Finance  │  │  Filters                         │   │
│  Local   │  │  Account: [All ▼]  Date: [...] │   │
│          │  │  Search: [........]              │   │
│ ───────  │  └──────────────────────────────────┘   │
│          │                                          │
│ 💰 Trans │  ┌──────────────────────────────────┐   │
│ ⚙️  Setts │  │  Transaction Table               │   │
│          │  │  Date | Account | Description...│   │
│          │  │  ...  | ...     | ...          │   │
│          │  └──────────────────────────────────┘   │
│          │                                          │
│          │  Status: Showing 450 of 2,450 trans...  │
└──────────┴─────────────────────────────────────────┘
```

## Usage Guide

### Viewing Transactions

1. Launch the application: `finance-gui`
2. Transactions from `data/accounts/` are loaded automatically
3. Use filter controls to narrow down the view
4. Click column headers to sort
5. Select rows to see selection count in status bar

### Filtering Transactions

**By Account:**
- Select an account from the dropdown, or "All Accounts" to see everything

**By Date Range:**
- Click the date fields to open calendar pickers
- Default: Last month to today

**By Category:**
- Select a category from the dropdown
- Only shows categories that exist in your transactions

**By Search Text:**
- Type in the search box to filter by description or counterparty
- Search is case-insensitive
- Press Enter or click "Apply Filters"

**Uncategorized Only:**
- Check the box to show only transactions without categories
- Useful for identifying transactions that need categorization

### Settings

**File → Settings** or **Click ⚙️ Settings** in sidebar:

- **General Tab**:
  - Default Currency (e.g., CAD, USD)

- **Paths Tab**:
  - Data Directory: Where ledger CSV files are stored
  - Ingest Directory: Where raw bank CSVs are placed
  - Accounts Config: Path to accounts.yml
  - Categories Config: Path to categories.yml

**Note**: Changes to paths require restarting the application.

### Keyboard Shortcuts

- **Ctrl+,**: Open Settings
- **Ctrl+Q**: Quit application
- **F5**: Refresh data from disk

## Troubleshooting

### "ModuleNotFoundError: No module named 'PySide6'"

You need to install the GUI dependencies:
```bash
pip install -e .[gui]
```

### "No transactions displayed"

Check the following:
1. Data directory path in Settings (default: `data/accounts`)
2. Make sure ledger CSV files exist in the data directory
3. Try clicking "Reload from Disk"

### Settings don't persist

Settings are stored using Qt's QSettings:
- **macOS**: `~/Library/Preferences/com.Mojility.Finance Local.plist`
- **Linux**: `~/.config/Mojility/Finance Local.conf`
- **Windows**: Registry under `HKEY_CURRENT_USER\Software\Mojility\Finance Local`

### Application crashes on startup

Check the terminal output for error messages. Common issues:
- PySide6 not properly installed
- Corrupted settings (delete the settings file)
- Invalid data directory path

## Privacy & Security

The GUI maintains the same privacy-first principles as the CLI:
- **No network I/O**: All processing happens locally
- **No telemetry**: No analytics or usage tracking
- **No external services**: No data leaves your machine
- **Local storage only**: All data remains in CSV files on disk

## Development

### Project Structure

```
src/finance/gui/
├── __init__.py
├── app.py                    # Main application entry point
├── main_window.py            # Main window with navigation
├── models/                   # Qt data models
│   └── transaction_model.py  # Table model for transactions
├── services/                 # Business logic
│   └── transaction_service.py
├── views/                    # UI views
│   └── transactions_view.py
├── widgets/                  # Custom widgets
│   └── transaction_table.py
├── dialogs/                  # Dialog windows
│   └── settings_dialog.py
└── resources/                # Assets
    └── styles.qss            # Application stylesheet
```

### Architecture

The GUI follows the **Model-View-Controller (MVC)** pattern:

- **Models**: Qt models (`QAbstractTableModel`) that adapt domain data to Qt views
- **Views**: UI widgets that display data and handle user interaction
- **Services**: Business logic that manipulates domain data
- **Domain Layer**: Reuses existing `finance.model`, `finance.ingest`, etc.

### Running from Source

```bash
# From repository root, with venv activated
python -m finance.gui.app
```

## Future Phases

See `Qt.md` for the full roadmap. Upcoming phases include:

- **Phase 2**: Category management, note editing, batch categorization
- **Phase 3**: CSV import wizard
- **Phase 4**: Budget tracking with charts
- **Phase 5**: Themes, keyboard shortcuts, undo/redo
- **Phase 6**: Advanced features (transaction splitting, custom reports)

## Feedback

This is Phase 1 of the GUI implementation. Please report issues or suggest features!
