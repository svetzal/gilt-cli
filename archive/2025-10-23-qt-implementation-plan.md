# Qt6 User Interface Plan

**Finance - Qt6 GUI**

This document outlines the design and implementation plan for a feature-rich Qt6 graphical user interface for the Finance privacy-first financial management tool.

## Overview

The Qt6 UI will provide a modern, intuitive interface while maintaining the project's core principles:
- **Local-only**: No network I/O, all data processing happens locally
- **Privacy-first**: No data leaves the machine
- **Safe by default**: Preview-before-commit workflow with explicit confirmation
- **Deterministic**: All operations remain reproducible and idempotent

## Technology Stack

### Core Technologies
- **Qt6** (PySide6): Modern Python bindings for Qt6
- **Python 3.13**: Consistent with existing codebase
- **Existing backend**: Reuse all `finance.model`, `finance.ingest`, `finance.transfer` modules
- **Qt Charts**: For budget visualization (optional module)
- **Qt Data Visualization**: For advanced 3D charts (optional, future enhancement)

### Key Qt6 Modules
- `PySide6.QtWidgets`: Main UI components
- `PySide6.QtCore`: Core functionality, signals/slots, models
- `PySide6.QtGui`: Graphics and styling
- `PySide6.QtCharts`: Budget charts and spending visualization
- `PySide6.QtSql`: Optional for faster querying (in-memory SQLite views)

## Application Architecture

### MVC Pattern
```
┌─────────────────────────────────────────────────────┐
│                   GUI Layer (Qt6)                    │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Views    │  │ Controllers  │  │  Qt Models  │ │
│  │ (Widgets)  │  │  (Signals)   │  │ (QAbstract) │ │
│  └────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────────────┐
│              Business Logic Layer                    │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Services  │  │  Managers    │  │  Validators │ │
│  │ (Actions)  │  │ (State)      │  │             │ │
│  └────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────────────┐
│                Data Layer (Existing)                 │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Models   │  │   Ledger I/O │  │  Category   │ │
│  │ (Pydantic) │  │    (CSV)     │  │    I/O      │ │
│  └────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Project Structure
```
src/finance/
├── gui/
│   ├── __init__.py
│   ├── app.py                    # Main QApplication entry point
│   ├── main_window.py            # Main window with navigation
│   ├── models/                   # Qt data models
│   │   ├── transaction_model.py  # QAbstractTableModel for transactions
│   │   ├── category_model.py     # QAbstractItemModel for categories
│   │   └── account_model.py      # Model for account listings
│   ├── views/                    # UI widgets and dialogs
│   │   ├── dashboard_view.py     # Overview/dashboard
│   │   ├── transactions_view.py  # Transaction table with filters
│   │   ├── budget_view.py        # Budget tracking and charts
│   │   ├── categories_view.py    # Category management
│   │   ├── import_wizard.py      # CSV import wizard
│   │   └── reports_view.py       # Report generation
│   ├── dialogs/                  # Modal dialogs
│   │   ├── categorize_dialog.py  # Categorization dialog
│   │   ├── note_dialog.py        # Transaction note editor
│   │   ├── settings_dialog.py    # Application settings
│   │   └── preview_dialog.py     # Change preview before commit
│   ├── widgets/                  # Custom reusable widgets
│   │   ├── transaction_table.py  # Enhanced transaction table
│   │   ├── category_tree.py      # Category tree widget
│   │   ├── amount_widget.py      # Currency amount display
│   │   └── date_range_picker.py  # Date range selection
│   ├── services/                 # Business logic services
│   │   ├── transaction_service.py # Transaction operations
│   │   ├── category_service.py   # Category operations
│   │   ├── import_service.py     # Import/ingest logic
│   │   └── budget_service.py     # Budget calculations
│   └── resources/                # UI resources
│       ├── styles.qss            # Qt stylesheets
│       ├── icons/                # Application icons
│       └── themes/               # Color themes (light/dark)
```

## Main Window Design

### Layout Overview
```
┌─────────────────────────────────────────────────────────────┐
│  Finance                                    [_][□][×] │
├─────────────────────────────────────────────────────────────┤
│  File  Edit  View  Tools  Help                              │
├──────────┬──────────────────────────────────────────────────┤
│          │  ┌────────────────────────────────────────────┐  │
│ 📊 Dash  │  │                                            │  │
│ 🏦 Accts │  │         MAIN CONTENT AREA                  │  │
│ 💰 Trans │  │      (Tabbed or Stacked Widget)            │  │
│ 📁 Categ │  │                                            │  │
│ 📈 Budgt │  │                                            │  │
│ 📥 Imprt │  │                                            │  │
│ 📊 Reprt │  │                                            │  │
│          │  └────────────────────────────────────────────┘  │
│          │                                                   │
│ ⚙️ Setts │  Status: Ready | 2,450 transactions | RBC_CHQ   │
└──────────┴──────────────────────────────────────────────────┘
```

### Navigation Sidebar
- **Dashboard**: Overview with key metrics and recent activity
- **Accounts**: List of accounts with balances and activity
- **Transactions**: Searchable, filterable transaction table
- **Categories**: Category tree management
- **Budget**: Budget vs. actual with charts
- **Import**: CSV import wizard
- **Reports**: Report generation and export
- **Settings**: Application configuration

## Feature Details

### 1. Dashboard View

**Purpose**: Quick overview of financial status

**Components:**
- **Summary Cards** (top row):
  - Total balance across all accounts
  - Month-to-date spending
  - Budget status (on track / over budget)
  - Uncategorized transaction count
- **Recent Transactions** (middle):
  - Last 10 transactions across all accounts
  - Quick-categorize buttons
- **Budget Summary Chart** (bottom):
  - Horizontal bar chart showing category budget vs. actual
  - Color-coded: green (under), yellow (90-100%), red (over)
- **Quick Actions**:
  - Import new transactions
  - Categorize uncategorized
  - Generate monthly report

**Implementation:**
- `QWidget` with `QGridLayout`
- Custom `SummaryCardWidget` for metrics
- `QTableView` for recent transactions
- `QChartView` with `QHorizontalBarSeries` for budget chart

---

### 2. Accounts View

**Purpose**: Manage and view account information

**Components:**
- **Account List** (left panel):
  - Tree or list view of all accounts
  - Shows account ID, description, current balance
  - Color indicators for account types
- **Account Details** (right panel):
  - Account metadata (ID, description, source patterns)
  - Transaction count and date range
  - Quick stats (total credits, debits, balance)
- **Actions**:
  - Filter transactions by account
  - View account-specific YTD
  - Edit account configuration

**Implementation:**
- `QListWidget` or `QTreeWidget` for account list
- Custom delegate for rich display
- Detail panel with `QFormLayout`

---

### 3. Transactions View

**Purpose**: Browse, search, filter, and manage transactions

**Components:**
- **Filter Bar** (top):
  - Account selector (multi-select dropdown)
  - Date range picker (preset ranges + custom)
  - Amount range (min/max)
  - Category filter (tree-based multi-select)
  - Search box (description/counterparty)
  - "Show only uncategorized" checkbox
- **Transaction Table** (center):
  - Columns: Date, Account, Description, Amount, Currency, Category, Subcategory, Notes, Transfer
  - Sortable by any column
  - Color-coded amounts (negative=red, positive=green)
  - Transfer indicators (icon/badge)
  - Multi-select rows (Ctrl/Shift+click)
  - Inline editing for notes
  - Context menu (right-click):
    - Categorize
    - Add/edit note
    - Copy transaction ID
    - View transfers (if linked)
- **Actions Toolbar** (bottom):
  - Batch categorize selected
  - Add note to selected
  - Export filtered results to CSV
  - Clear filters
- **Status Bar**:
  - Shows count of displayed vs. total transactions
  - Sum of filtered amounts

**Implementation:**
- `QTableView` with custom `TransactionTableModel` (QAbstractTableModel)
- Custom delegates for amount formatting, category display
- `QSortFilterProxyModel` for filtering
- Signal/slot connections for filter changes

**Advanced Features:**
- **Quick categorize**: Drag transactions to category tree in sidebar
- **Smart search**: Regex support, search history
- **Column customization**: Show/hide columns, reorder
- **Saved filters**: Save common filter combinations

---

### 4. Categories View

**Purpose**: Manage category hierarchy and budgets

**Layout:**
```
┌─────────────────────────┬────────────────────────────────┐
│   Category Tree         │   Category Details             │
│                         │                                │
│ ▼ Housing               │  Name: Housing                 │
│   ├─ Rent              │  Description: Housing expenses │
│   ├─ Utilities         │  Budget: $2,500.00 / monthly   │
│   └─ Maintenance       │                                │
│ ▼ Transportation        │  Subcategories:                │
│   ├─ Fuel              │  ☑ Rent                        │
│   ├─ Maintenance       │  ☑ Utilities                   │
│   └─ Insurance         │  ☑ Maintenance                 │
│ ▶ Dining Out           │  [+ Add Subcategory]           │
│                         │                                │
│ [+ Add Category]        │  Usage:                        │
│                         │  • 145 transactions            │
│                         │  • $23,456.78 total            │
│                         │  • Most recent: 2025-10-22     │
│                         │                                │
│                         │  [Save] [Delete] [Diagnose]    │
└─────────────────────────┴────────────────────────────────┘
```

**Components:**
- **Category Tree** (left):
  - Hierarchical tree view
  - Drag-to-reorder support
  - Color-coded by budget status
  - Expand/collapse all button
  - Context menu: Add, Edit, Delete, Set Budget
- **Category Details** (right):
  - Name and description editor
  - Budget amount and period selector
  - Subcategory management
  - Usage statistics (transaction count, total amount)
  - Orphaned category indicator (if used but not defined)
- **Actions**:
  - Add new category/subcategory
  - Edit existing
  - Delete (with safety checks)
  - Set/update budget
  - Diagnose orphaned categories
  - Recategorize (bulk rename)

**Implementation:**
- `QTreeView` with custom `CategoryTreeModel` (QAbstractItemModel)
- Drag-and-drop for reordering (Qt::ItemIsDragEnabled)
- Detail panel with `QFormLayout`
- Validation before deletion (check usage)

---

### 5. Budget View

**Purpose**: Track spending against budgets with visual feedback

**Layout:**
```
┌──────────────────────────────────────────────────────────┐
│  Period: [October 2025 ▼] [Month ▼]  [Year to Date]     │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │          Budget vs. Actual Chart                   │  │
│  │  ┌─────────────────────────────────────────────┐   │  │
│  │  │ Housing      ████████████░░ 85% ($2,125)    │   │  │
│  │  │ Transport    ███████████████ 120% ($960)    │   │  │
│  │  │ Dining Out   ██████░░░░░░░ 65% ($260)       │   │  │
│  │  │ ...                                          │   │  │
│  │  └─────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │          Spending Trend (Line Chart)              │  │
│  │  Daily/Weekly/Monthly spending over time          │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────┐            │
│  │ Category      Budget    Actual   Remain  │            │
│  ├──────────────────────────────────────────┤            │
│  │ Housing       $2,500    $2,125   $375    │ (green)   │
│  │ Transport     $800      $960     -$160   │ (red)     │
│  │ Dining Out    $400      $260     $140    │ (green)   │
│  │ ...                                      │            │
│  └──────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────┘
```

**Components:**
- **Period Selector** (top):
  - Month/year picker
  - Preset ranges (This Month, Last Month, YTD, Last Year)
  - Custom date range
- **Budget Chart** (top-center):
  - Horizontal stacked bar chart (budgeted vs. actual)
  - Color gradient based on percentage (green → yellow → red)
  - Click to drill down into category details
- **Spending Trend Chart** (middle):
  - Line chart showing spending over time
  - Toggle between daily, weekly, monthly aggregation
  - Multiple series for different categories
- **Budget Table** (bottom):
  - Category, Budget, Actual, Remaining, Percentage
  - Sort by any column
  - Export to CSV/PDF
- **Summary Panel** (sidebar or top):
  - Total budgeted vs. actual
  - Categories over/under budget
  - Projected end-of-period total

**Implementation:**
- `QChartView` with `QHorizontalBarSeries`
- `QLineSeries` for trend charts
- Custom `BudgetTableModel`
- Real-time calculation using `budget_service.py`

---

### 6. Import Wizard

**Purpose**: Guide users through importing raw bank CSV files

**Wizard Steps:**

**Step 1: Select Files**
- File browser to select one or more CSV files
- Preview of selected files (name, size, modified date)
- Drag-and-drop support

**Step 2: Account Mapping**
- Auto-detect accounts based on source_patterns
- Manual override if needed
- Preview first few rows of each file
- Warning if account not found in config

**Step 3: Preview & Verify**
- Show parsed transactions in table
- Highlight new vs. existing (duplicate detection)
- Show detected transfers
- Column mapping verification
- Error/warning indicators for problematic rows

**Step 4: Import Options**
- Write to ledgers (checkbox, default: off for dry-run)
- Link transfers (checkbox, default: on)
- Backup existing ledgers (checkbox, default: on)

**Step 5: Execute & Review**
- Progress bar for processing
- Log output (success/error messages)
- Summary: X transactions imported, Y duplicates skipped, Z transfers linked
- Option to view imported transactions immediately

**Implementation:**
- `QWizard` with custom `QWizardPage` subclasses
- `QFileDialog` for file selection
- `QTableView` for previews
- Threading (`QThread`) for long-running import operations
- Progress reporting via signals

---

### 7. Reports View

**Purpose**: Generate and export financial reports

**Components:**
- **Report Type Selector**:
  - Budget Report (Markdown + DOCX)
  - Transaction Report (CSV)
  - Category Summary (CSV/PDF)
  - Year-End Summary
- **Parameters** (based on report type):
  - Date range
  - Accounts to include
  - Categories to include
  - Grouping (by month, category, account)
- **Preview Panel**:
  - Live preview of report content
  - Markdown rendering for budget reports
- **Output Options**:
  - Format selector (CSV, Markdown, DOCX, PDF)
  - Output directory picker
  - File name template
- **Actions**:
  - Generate report
  - Save to disk
  - Print (for PDF reports)
  - Email (if enabled, with privacy warnings)

**Implementation:**
- Reuse existing `finance.cli.command.report` logic
- `QTextEdit` or `QWebEngineView` for Markdown preview
- `QPrintDialog` for printing
- Export via existing backend functions

---

### 8. Settings Dialog

**Purpose**: Configure application behavior

**Categories:**
- **General**:
  - Data directory path
  - Ingest directory path
  - Default currency
  - Date format preference
- **Accounts**:
  - Path to accounts.yml
  - Quick-edit account configurations
- **Categories**:
  - Path to categories.yml
  - Default budget period
- **Import**:
  - Transfer linking parameters (window_days, epsilon, etc.)
  - Auto-backup before import
  - Duplicate detection strategy
- **Appearance**:
  - Theme (Light, Dark, System)
  - Font size
  - Color scheme for amounts
  - Chart colors
- **Advanced**:
  - Enable experimental features
  - Debug logging
  - Performance options (in-memory caching)

**Implementation:**
- `QDialog` with `QTabWidget` for categories
- `QSettings` for persistent configuration
- Validation for paths and numeric values

---

## Custom Widgets

### TransactionTableWidget
**Features:**
- Fast rendering for thousands of rows (virtualization)
- Multi-column sorting
- Inline editing for notes
- Context menu
- Drag-and-drop to categorize
- Keyboard shortcuts (Ctrl+C for copy, Delete for remove note, etc.)

### CategoryTreeWidget
**Features:**
- Drag-to-reorder
- Color-coded nodes (by budget status)
- Usage badges (transaction count)
- Expand/collapse animations
- Quick-add via double-click on empty space

### AmountWidget
**Features:**
- Formatted currency display (respects locale)
- Color-coded (negative=red, positive=green, zero=gray)
- Tooltip with full precision
- Right-aligned in tables

### DateRangePickerWidget
**Features:**
- Dual calendar for start/end dates
- Preset buttons (Today, This Week, This Month, This Year, YTD, Last 30 Days, Custom)
- Smart defaults (e.g., "This Month" selects 1st to today)
- Validation (end >= start)

---

## Data Models (Qt)

### TransactionTableModel (QAbstractTableModel)
**Responsibilities:**
- Load transactions from ledger files
- Provide data to `QTableView`
- Handle sorting, filtering (via proxy)
- Emit signals on data changes
- Support batch updates

**Key Methods:**
- `rowCount()`, `columnCount()`, `data()`, `headerData()`
- `setData()` for inline editing
- `flags()` to enable editing
- `update_transactions(new_data)` to refresh

### CategoryTreeModel (QAbstractItemModel)
**Responsibilities:**
- Represent category hierarchy as tree
- Support drag-and-drop reordering
- Provide data for `QTreeView`
- Handle category CRUD operations

**Key Methods:**
- `index()`, `parent()`, `rowCount()`, `columnCount()`
- `data()`, `setData()`
- `flags()` to enable drag-and-drop
- `mimeData()`, `dropMimeData()` for DnD

### AccountListModel (QAbstractListModel)
**Responsibilities:**
- List all accounts
- Provide account metadata
- Support filtering by account type

---

## Services Layer

### TransactionService
**Responsibilities:**
- Load/save transactions from ledger files
- Apply filters (date, amount, category, search text)
- Batch categorization
- Note management
- Transaction search

**Key Methods:**
- `load_transactions(account_id=None, year=None) -> List[TransactionGroup]`
- `filter_transactions(criteria) -> List[TransactionGroup]`
- `categorize_transactions(txids, category, subcategory, write=False) -> Result`
- `add_note(txid, note_text, write=False) -> Result`
- `search(query_text) -> List[TransactionGroup]`

### CategoryService
**Responsibilities:**
- Load/save categories from config
- CRUD operations
- Budget management
- Usage statistics
- Orphaned category detection

**Key Methods:**
- `load_categories() -> List[Category]`
- `add_category(name, description, budget=None) -> Result`
- `delete_category(name, force=False) -> Result`
- `set_budget(name, amount, period) -> Result`
- `get_usage_stats(name) -> Dict`
- `diagnose_orphans() -> List[str]`

### ImportService
**Responsibilities:**
- Import wizard logic
- Account detection
- Duplicate detection
- Transfer linking
- Progress reporting

**Key Methods:**
- `detect_account(file_path) -> Optional[str]`
- `parse_csv(file_path) -> List[Transaction]`
- `import_file(file_path, account_id, write=False) -> ImportResult`
- `link_transfers(write=False) -> int`

### BudgetService
**Responsibilities:**
- Budget vs. actual calculations
- Period handling (month, year, custom range)
- Spending trends
- Chart data preparation

**Key Methods:**
- `get_budget_summary(year, month=None) -> Dict`
- `get_spending_by_category(start_date, end_date) -> Dict`
- `calculate_trend(category, period) -> List[DataPoint]`
- `get_chart_data(period) -> ChartData`

---

## Threading & Performance

### Background Operations
Use `QThread` for long-running operations to keep UI responsive:
- **Import/Ingest**: Parsing large CSVs
- **Transfer linking**: Analyzing all transactions
- **Report generation**: Rendering large reports
- **Recategorization**: Bulk updates

**Pattern:**
```python
class ImportWorker(QThread):
    progress = Signal(int)  # 0-100
    finished = Signal(object)  # ImportResult
    error = Signal(str)

    def __init__(self, file_path, account_id):
        super().__init__()
        self.file_path = file_path
        self.account_id = account_id

    def run(self):
        try:
            result = import_service.import_file(
                self.file_path,
                self.account_id,
                write=True,
                progress_callback=lambda pct: self.progress.emit(pct)
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
```

### Caching Strategy
- Cache loaded transactions in memory
- Invalidate cache on file changes (QFileSystemWatcher)
- Use proxy models for filtering (avoid reloading data)
- Lazy-load transaction details (only when viewed)

### Optimization
- Virtual scrolling for large tables (Qt handles this)
- Batch updates (beginResetModel/endResetModel)
- Debounce search input (QTimer)
- Pagination for very large datasets (10,000+ transactions)

---

## Preview-Before-Commit Pattern

**Critical for Privacy/Safety:**

All mutation operations must show a preview before committing.

**Implementation:**
1. User initiates action (e.g., "Categorize selected transactions")
2. Service computes changes in dry-run mode
3. `PreviewDialog` shows:
   - Table of affected transactions
   - Before/after comparison
   - Warning if operation is destructive
   - Checkbox: "I understand these changes will be permanent"
4. User confirms or cancels
5. If confirmed, service executes with `write=True`
6. Success/error notification

**Example: PreviewDialog**
```
┌──────────────────────────────────────────────────────┐
│  Preview Changes                                     │
├──────────────────────────────────────────────────────┤
│  Action: Categorize 15 transactions                  │
│  Category: Housing:Utilities                         │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │ Date       Description      Current  → New      │ │
│  ├─────────────────────────────────────────────────┤ │
│  │ 2025-10-01 HYDRO ONE       (none)   → Housing:… │ │
│  │ 2025-09-01 HYDRO ONE       (none)   → Housing:… │ │
│  │ ...                                             │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ☑ I understand these changes will be permanent     │
│                                                       │
│               [Cancel]  [Apply Changes]              │
└──────────────────────────────────────────────────────┘
```

---

## Keyboard Shortcuts

### Global
- `Ctrl+N`: New transaction (manual entry)
- `Ctrl+O`: Import wizard
- `Ctrl+S`: Save changes (if any pending)
- `Ctrl+F`: Focus search box
- `Ctrl+Q`: Quit
- `F5`: Refresh all data from disk

### Transactions View
- `Ctrl+A`: Select all (filtered)
- `Ctrl+C`: Copy selected transaction IDs
- `Delete`: Clear note from selected
- `Ctrl+E`: Edit note
- `Ctrl+K`: Categorize selected
- `Space`: Quick-categorize (popup selector)

### Categories View
- `Ctrl+N`: New category
- `Delete`: Delete selected category
- `F2`: Rename selected

### Budget View
- `Ctrl+P`: Export/print report
- `Ctrl+E`: Export data to CSV

---

## Styling & Themes

### Light Theme (Default)
- Clean, modern interface
- Soft colors (blues, greens for positive, red for negative)
- High contrast for readability

### Dark Theme
- Dark gray backgrounds (#2b2b2b)
- Muted colors for reduced eye strain
- Syntax highlighting for amounts (green/red still visible)

### Custom Stylesheet (styles.qss)
```css
/* Amount colors */
QLabel.amount-positive { color: #27ae60; }
QLabel.amount-negative { color: #e74c3c; }
QLabel.amount-zero { color: #95a5a6; }

/* Budget status indicators */
QProgressBar.budget-good { background-color: #27ae60; }
QProgressBar.budget-warning { background-color: #f39c12; }
QProgressBar.budget-danger { background-color: #e74c3c; }

/* Category tree */
QTreeView::item:selected { background-color: #3498db; }
```

---

## Privacy & Security in UI

### Hardened Privacy
- **No screenshots by default**: Set `Qt::AA_DisableWindowContextHelpButton` to prevent screen capture on some platforms (optional)
- **Clipboard sanitization**: Warn when copying sensitive data
- **Session timeout**: Auto-lock after inactivity (optional feature)
- **Audit log**: Log all write operations locally (optional)

### User Warnings
- Display warning on first launch about privacy expectations
- Confirmation dialogs for exports (CSV, PDF) reminding user data is sensitive
- No telemetry, no analytics, no update checks without explicit user consent

### Data Validation
- Validate all file paths (prevent directory traversal)
- Sanitize user input (category names, notes)
- Confirm before overwriting files

---

## Error Handling & User Feedback

### Error Display
- **Toast notifications** for non-critical errors (file not found, validation failure)
- **Modal dialogs** for critical errors (data corruption, write failures)
- **Status bar messages** for informational updates

**Example:**
```python
def show_error(parent, title, message):
    QMessageBox.critical(parent, title, message)

def show_warning(parent, title, message):
    QMessageBox.warning(parent, title, message)

def show_info(parent, title, message):
    QMessageBox.information(parent, title, message)

def show_toast(main_window, message, duration_ms=3000):
    # Custom toast widget that auto-hides
    toast = ToastWidget(main_window, message)
    toast.show()
    QTimer.singleShot(duration_ms, toast.hide)
```

### Progress Indication
- **Progress bar** in status bar for long operations
- **Spinner** for indeterminate operations
- **Detailed log** in import wizard

---

## Implementation Phases

### Phase 1: Foundation (Core UI)
**Goal**: Basic functional UI with transaction viewing

**Deliverables:**
1. Main window with navigation sidebar
2. Transaction view with filtering
3. Qt models for transactions and categories
4. Service layer integration
5. Settings dialog (basic paths only)

**Tasks:**
- Set up PySide6 project structure
- Implement `TransactionTableModel`
- Create `TransactionTableWidget` with sorting/filtering
- Implement `TransactionService`
- Wire up to existing ledger I/O

**Testing:**
- Load existing ledger files
- Display transactions correctly
- Filter by date, account, category
- Sort by columns

---

### Phase 2: Data Management
**Goal**: Full CRUD for categories and notes

**Deliverables:**
1. Categories view with tree
2. Note editing (inline and dialog)
3. Categorize dialog with preview
4. Preview-before-commit pattern

**Tasks:**
- Implement `CategoryTreeModel`
- Create `CategoryTreeWidget` with drag-and-drop
- Build `CategorizeDialog` with preview table
- Build `NoteDialog`
- Implement `CategoryService`
- Add preview dialogs for all write operations

**Testing:**
- Add/edit/delete categories
- Categorize transactions (single and batch)
- Preview changes before committing
- Verify dry-run safety

---

### Phase 3: Import & Ingest
**Goal**: Import wizard for CSV files

**Deliverables:**
1. Import wizard (all steps)
2. Account detection logic
3. Progress reporting
4. Transfer linking integration

**Tasks:**
- Build `QWizard` with 5 steps
- Implement `ImportService`
- Add threading for long operations
- Integrate existing `finance.ingest` logic
- Add transfer linking post-import

**Testing:**
- Import real bank CSV files
- Verify account detection
- Check duplicate handling
- Confirm transfer linking works
- Test dry-run mode

---

### Phase 4: Budget & Reporting
**Goal**: Visual budget tracking and reports

**Deliverables:**
1. Budget view with charts
2. Dashboard with summary
3. Reports generation
4. Chart widgets

**Tasks:**
- Implement `BudgetService`
- Create chart widgets using Qt Charts
- Build budget table with color coding
- Add dashboard summary cards
- Integrate report generation (reuse CLI logic)

**Testing:**
- Verify budget calculations
- Check chart rendering
- Test report generation (Markdown, DOCX)
- Validate period selection

---

### Phase 5: Polish & UX
**Goal**: Refined user experience

**Deliverables:**
1. Themes (light/dark)
2. Keyboard shortcuts
3. Drag-and-drop for categorization
4. Undo/redo support
5. Saved filters
6. Column customization

**Tasks:**
- Create QSS stylesheets
- Implement theme switcher
- Add keyboard shortcut handlers
- Build undo/redo stack (QUndoCommand)
- Add user preferences storage
- Polish animations and transitions

**Testing:**
- Test all keyboard shortcuts
- Verify theme switching
- Check undo/redo correctness
- Validate saved preferences

---

### Phase 6: Advanced Features (Optional)
**Goal**: Power-user features

**Deliverables:**
1. Multi-currency support visualization
2. Advanced search (regex, saved queries)
3. Transaction splitting UI
4. Custom report templates
5. Batch import (multiple files at once)
6. Data export wizard

**Tasks:**
- Design split transaction UI
- Implement advanced search builder
- Create report template editor
- Add batch import queue
- Build export wizard

---

## Testing Strategy

### Unit Tests
- Test Qt models (data, rowCount, columnCount, etc.)
- Test services (transaction filtering, categorization logic)
- Mock file I/O

### Integration Tests
- Test UI workflows (import → categorize → budget)
- Verify data persistence
- Test undo/redo correctness

### Manual Testing
- User acceptance testing for wizard flows
- Visual regression testing for charts
- Performance testing with large datasets (10,000+ transactions)

### Test Framework
- `pytest` with `pytest-qt` plugin
- `QTest` for widget testing
- Mock backend services for isolated UI tests

---

## Packaging & Distribution

### Entry Point
```python
# src/finance/gui/app.py
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Finance")
    app.setOrganizationName("Mojility")

    # Load settings
    settings = QSettings()

    # Apply theme
    apply_theme(app, settings.value("theme", "light"))

    # Show main window
    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

### pyproject.toml Updates
```toml
[project.optional-dependencies]
gui = [
    "PySide6>=6.5",
    "PySide6-Charts",
]

[project.scripts]
finance-gui = "finance.gui.app:main"
```

### Installation
```bash
# Install with GUI support
pip install -e .[gui]

# Launch GUI
finance-gui
```

### Platform-Specific Packaging
- **macOS**: `.app` bundle using `py2app`
- **Windows**: `.exe` installer using `PyInstaller` or `cx_Freeze`
- **Linux**: `.AppImage` or distribution packages

---

## Future Enhancements

### Charts & Visualization
- Pie charts for spending breakdown
- Trend analysis (detect unusual spending)
- Comparative charts (this month vs. last month)

### Smart Features
- Auto-categorization suggestions (ML-based, local only)
- Recurring transaction detection
- Budget forecasting

### Data Analysis
- SQL query interface (read-only, in-memory SQLite)
- Custom pivot tables
- Export to Excel with formulas

### Collaboration (Privacy-Preserving)
- Export anonymized datasets for sharing
- Import category templates (no transaction data)

---

## Migration from CLI

**Coexistence:**
- GUI and CLI can coexist peacefully
- Both use same backend (ledger files, config)
- No migration needed; users can use both

**CLI Wrapper:**
- GUI can launch CLI commands in background (for debugging)
- Show CLI output in a console widget (advanced users)

---

## Summary

This Qt6 UI plan provides:
1. **Full feature parity** with CLI
2. **Enhanced UX** with visual feedback, charts, wizards
3. **Privacy-first design** maintaining local-only principles
4. **Scalable architecture** using Qt best practices (MVC, signals/slots)
5. **Phased implementation** for iterative development
6. **Professional polish** with themes, shortcuts, animations

The GUI will make Finance accessible to non-technical users while preserving the power and flexibility of the CLI for advanced workflows.
