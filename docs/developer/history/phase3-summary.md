# Phase 3 Summary - CSV Import Wizard

Phase 3 implemented a full-featured CSV import wizard with account detection, preview, and progress reporting.

## Implementation Overview

**Goal**: Provide a user-friendly wizard for importing bank CSV files through the GUI.

**Status**: ✅ Complete

## Features Implemented

### 1. Import Service

Complete business logic for CSV import operations in `src/finance/gui/services/import_service.py`.

**Key Features**:
- Load and cache accounts configuration
- Detect account from filename using source patterns
- Preview CSV files (first N rows)
- Create file mappings with account detection
- Count existing transactions and estimate duplicates
- Execute import with progress reporting
- Plan multi-file imports (dry-run)

### 2. Import Wizard - 5 Steps

Complete QWizard implementation in `src/finance/gui/views/import_wizard.py`:

**Step 1 - File Selection**:
- File browser with CSV filter
- Drag-and-drop support for CSV files
- File list with add/remove
- Status indicator

**Step 2 - Account Mapping**:
- Table showing selected files
- Auto-detect account based on source_patterns
- Dropdown to manually override detected account
- Status column (✓ Ready or ⚠ Unknown)
- Validation (all files must have account)

**Step 3 - Preview & Verify**:
- Preview raw CSV data (first few rows)
- Table displays raw CSV columns
- Summary showing total files
- Warning about normalization

**Step 4 - Import Options**:
- Write checkbox (default: unchecked for dry-run)
- Information about dry-run mode
- Explanation of duplicate detection

**Step 5 - Execute & Review**:
- Progress bar (0-100%)
- Background threading (QThread) for responsiveness
- Live log output
- Summary of results
- Success/failure indicators

### 3. Import Worker Thread

Background processing with `ImportWorker` (QThread):

- Runs import in background
- Reports progress via signals
- Handles errors gracefully
- Emits completion signal with results
- Keeps UI responsive during import

### 4. Main Window Integration

Added Import to navigation and menu:

**Navigation**:
- 📊 Dashboard
- 💰 Transactions
- 📁 Categories
- 📥 Import ← **NEW**
- ⚙️ Settings

**File Menu**:
- Import CSV Files... (Ctrl+I) ← **NEW**
- Settings...
- Quit

## User Workflows

### Workflow 1: Import New Bank CSV Files

1. Click "📥 Import" or press `Ctrl+I`
2. Add files via browser or drag-and-drop
3. Review auto-detected accounts (override if needed)
4. Preview raw CSV data
5. Choose dry-run (default) or write mode
6. Watch progress and review log
7. ✅ Import completes, transactions reload

### Workflow 2: Dry-Run Import (Safety Check)

1. Open Import wizard
2. Select CSV files
3. Map to accounts
4. **Leave "Write changes" unchecked**
5. Execute dry-run
6. Review log to see what would be imported
7. Cancel or restart with write mode

### Workflow 3: Multi-File Import

1. Select multiple CSV files at once
2. Wizard auto-detects account for each
3. Override any misdetected accounts
4. Execute imports all files sequentially
5. Progress bar updates across all files
6. Log shows per-file results

## Technical Implementation

### Account Detection

Uses existing `ingest.infer_account_for_file()`:

1. Matches filename against `source_patterns` from config
2. Supports glob patterns (e.g., `*rbc*chequing*.csv`)
3. Falls back to heuristic matching
4. User can always override

### Duplicate Detection

Leverages existing `normalize_file()` behavior:

- Computes stable `transaction_id` hash
- Loads existing ledger CSV
- Filters out transactions with existing IDs
- Only writes new transactions
- Automatic, transparent, reliable

### Progress Reporting

Multi-level progress tracking:

1. Service accepts optional `progress_callback`
2. Worker receives progress (0-100) per file
3. Worker computes overall progress across files
4. Emits signal to update UI progress bar
5. Log provides detailed textual feedback

### Threading Architecture

```python
class ImportWorker(QThread):
    progress = Signal(int)
    finished = Signal(object)
    error = Signal(str)

    def run(self):
        # Runs in background thread
        for file in files:
            result = import_service.import_file(
                file,
                write=True,
                progress_callback=lambda pct: self.progress.emit(pct)
            )
            # Update overall progress
```

UI remains responsive during long imports.

## Files Created

**New Services**:
- `src/finance/gui/services/import_service.py` - Import business logic

**New Views**:
- `src/finance/gui/views/import_wizard.py` - 5-step wizard + worker thread

**Modified**:
- `src/finance/gui/main_window.py` - Added Import nav item + menu

## Privacy & Safety

**All operations maintain privacy**:
- ✅ No network I/O
- ✅ Local CSV files only
- ✅ **Default to dry-run** (write must be enabled)
- ✅ Preview-before-commit workflow
- ✅ Automatic duplicate detection
- ✅ Background threading doesn't block UI
- ✅ User controls when changes apply

**Safety Features**:
- Dry-run as default
- Preview raw data before import
- Progress bar shows status
- Detailed log of actions
- Error handling with clear messages
- Wizard prevents closing on failure
- Automatic deduplication

## Statistics

- **Services Created**: 1
- **Wizards Created**: 1 (5 pages)
- **Worker Threads**: 1
- **Lines of Code**: ~900

## Integration Points

Reuses existing code:
- **finance.ingest**: `load_accounts_config`, `infer_account_for_file`, `normalize_file`
- **finance.model.account**: `Account`, `TransactionGroup`
- **finance.model.ledger_io**: `load_ledger_csv`
- **config/accounts.yml**: Source patterns
- **data/accounts/*.csv**: Ledger files

## What's Next

Phase 4 adds:
- Budget tracking view with charts
- Dashboard with summary cards
- Budget vs. actual calculations
- Spending trends
- Report generation

## Related Documents

- [GUI Implementation](../technical/gui-implementation.md) - Overall GUI design
- [Phase 2 Summary](phase2-summary.md) - Previous phase
- [Phase 4 Summary](phase4-summary.md) - Next phase
