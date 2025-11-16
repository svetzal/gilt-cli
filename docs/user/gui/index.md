# GUI Overview

The Finance GUI provides a modern, visual interface for managing your financial data built with Qt6.

## Overview

The GUI is ideal for:

- **Interactive exploration**: Browse and filter transactions visually
- **Visual analysis**: Charts and dashboards for spending trends
- **Drag-and-drop**: Intuitive workflows
- **Comfort**: Users who prefer graphical tools over command line

## Installation

Install GUI dependencies:

```bash
pip install -e .[gui]
```

This installs PySide6 and Qt Charts (~100 MB download).

## Launching

Start the GUI:

```bash
finance-gui
```

Or directly:

```bash
python -m finance.gui.app
```

## Main Window

The application has a navigation sidebar and content area:

```
┌──────────┬────────────────────────────────────┐
│          │                                    │
│ 📊 Dash  │                                    │
│ 💰 Trans │         Content Area               │
│ 📁 Categ │                                    │
│ 📈 Budgt │                                    │
│ 📥 Imprt │                                    │
│ ⚙️  Setts │                                    │
│          │                                    │
│          │  Status Bar                        │
└──────────┴────────────────────────────────────┘
```

### Navigation

Click navigation items to switch views:

- **📊 Dashboard**: Overview with key metrics
- **💰 Transactions**: Browse and filter all transactions
- **📁 Categories**: Manage category hierarchy
- **📈 Budget**: Track spending vs budgets
- **📥 Import**: CSV import wizard
- **⚙️ Settings**: Configure application

### Keyboard Shortcuts

- `Ctrl+I` - Open import wizard
- `Ctrl+,` - Open settings
- `Ctrl+Q` - Quit application
- `F5` - Refresh current view

### Status Bar

Shows contextual information:

- Transaction count
- Selection info
- Operation status
- Success/error messages

## Core Features

### Dashboard

Overview with summary cards:

- **This Month's Spending**: Total expenses
- **Budget Status**: Percentage used with color coding
- **Uncategorized**: Count of transactions needing attention
- **Year to Date**: Total spending for year

Quick actions to navigate to other views.

[Learn more →](dashboard.md)

### Transactions

Browse and manage all transactions:

- **Filter by**: Account, date range, category, search text
- **Sort by**: Any column
- **Context menu**: Right-click for actions
  - Categorize selected
  - Edit note
  - Copy transaction ID
- **Color-coded amounts**: Red=negative, green=positive

[Learn more →](transactions.md)

### Categories

Manage category hierarchy:

- **Tree view**: Expandable categories and subcategories
- **Add/Remove**: Create or delete categories
- **Set budgets**: Assign monthly/yearly amounts
- **Visual hierarchy**: Bold categories, indented subcategories

[Learn more →](categories.md)

### Budget

Track spending against budgets:

- **Period selector**: Year and month
- **Budget table**: Category, budget, actual, remaining, %
- **Color coding**: Green (good), yellow (warning), red (over)
- **Summary stats**: Total budgeted, actual, remaining

[Learn more →](budget.md)

### Import

Import wizard for CSV files:

- **Step 1**: Select files (drag-and-drop supported)
- **Step 2**: Map files to accounts (auto-detection)
- **Step 3**: Preview data
- **Step 4**: Configure options (dry-run or write)
- **Step 5**: Execute with progress bar

[Learn more →](importing.md)

### Settings

Configure application:

- **General**: Default currency
- **Paths**: Data directory, config files
- Theme selection (automatic)

## Design Patterns

### Preview-Before-Commit

All data-modifying operations show previews:

1. User initiates action (e.g., categorize)
2. Preview dialog shows before → after
3. User reviews changes
4. User checks "I understand..." checkbox
5. User confirms
6. Changes written to CSV files

### Automatic Reload

After any data change:

1. CSV files updated
2. Views automatically reload
3. UI reflects latest data
4. Success message shown

### Context Menus

Right-click for context-sensitive actions:

- Transaction table: Categorize, edit note, copy ID
- Category tree: Add, edit, remove

### Signal-Based Updates

Views communicate via Qt signals:

- Categories modified → Reload transactions
- Import completed → Reload dashboard
- Settings changed → Reconfigure views

## Themes

The GUI respects your system theme:

- **Light mode**: Clean, bright interface
- **Dark mode**: Dark gray backgrounds, muted colors

Theme is detected automatically from system preferences.

## Privacy & Security

Same privacy principles as CLI:

- ✅ No network I/O
- ✅ Local CSV/YAML files only
- ✅ No telemetry or tracking
- ✅ You control all data

**Settings Storage**:
- macOS: `~/Library/Preferences/com.Mojility.Finance.plist`
- Linux: `~/.config/Mojility/Finance.conf`
- Windows: Registry under `HKEY_CURRENT_USER\Software\Mojility\Finance`

Settings contain only paths and preferences (no financial data).

## Performance

**Typical Performance**:
- Load 5,000 transactions: < 1 second
- Filter/search: Instant
- Import 1,000 transactions: 1-2 seconds
- Budget calculation: < 1 second

**Large Datasets**:
- Tested up to 50,000 transactions
- UI remains responsive
- Uses Qt's virtualization for tables

## Troubleshooting

### GUI Won't Start

**Problem**: `ModuleNotFoundError: No module named 'PySide6'`

**Solution**: Install GUI dependencies:
```bash
pip install -e .[gui]
```

### No Transactions Displayed

**Checklist**:
1. Verify data directory in Settings
2. Check ledger CSV files exist in `data/accounts/`
3. Click "Reload from Disk"
4. Check terminal for errors

### Settings Don't Persist

**Problem**: Settings reset on restart

**Solution**: Check settings file permissions:
```bash
# macOS
ls -la ~/Library/Preferences/com.Mojility.Finance.plist

# Linux
ls -la ~/.config/Mojility/Finance.conf
```

### Application Crashes

**Steps**:
1. Check terminal output for errors
2. Verify PySide6 installed correctly
3. Try deleting settings file (will reset to defaults)
4. Reinstall GUI dependencies

### Import Fails

**Common issues**:
- CSV encoding problems → Ensure UTF-8 encoding
- Missing account config → Add to `config/accounts.yml`
- Invalid CSV format → Check bank export settings

## Best Practices

### Workflow

1. **Start with Dashboard**: See overview
2. **Import new data**: Use import wizard
3. **Categorize**: Right-click uncategorized transactions
4. **Review budget**: Check spending vs budgets
5. **Adjust**: Update categories or budgets as needed

### Organization

- **Use filters**: Narrow down large transaction lists
- **Batch operations**: Categorize similar transactions together
- **Regular imports**: Import monthly to stay current
- **Review budgets**: Check spending weekly or monthly

### Data Safety

- **Backup regularly**: Copy `data/` and `config/` directories
- **Test imports**: Use dry-run mode first
- **Preview changes**: Always review before confirming
- **Keep originals**: Don't delete bank CSV exports

## Comparison with CLI

| Feature | CLI | GUI |
|---------|-----|-----|
| Transaction browsing | Table output | Interactive table with filters |
| Categorization | Batch commands | Right-click menu with preview |
| Budget tracking | Text report | Visual table with colors |
| Import | Single command | Step-by-step wizard |
| Speed | Fastest | Fast (< 1 sec for most operations) |
| Automation | Excellent (scriptable) | Good (manual workflows) |
| Learning curve | Steeper | Gentler |
| Visual feedback | Limited | Excellent |

**Recommendation**: Use both! Import with CLI automation, analyze with GUI visualization.

## Next Steps

Explore individual GUI features:

- [Dashboard](dashboard.md) - Overview and metrics
- [Transactions](transactions.md) - Browse and filter
- [Categories](categories.md) - Manage hierarchy
- [Budget Tracking](budget.md) - Monitor spending
- [Importing](importing.md) - CSV import wizard
