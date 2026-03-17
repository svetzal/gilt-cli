---
name: gilt
description: Local-only, privacy-first personal finance CLI. All mutations dry-run by default; pass --write to persist. Use for import, categorization, budgeting, duplicates, and reporting.
---

# Gilt CLI

Local-only CLI for managing personal finance ledgers. Run with `uv run gilt <command>`.

## Safety Model

**Every mutation is dry-run by default.** The CLI previews what would change; nothing is written until you add `--write`.

**Workflow:** Always run without `--write` first, review the preview, then re-run with `--write`.

### Write vs Read-Only Commands

| Write commands (need `--write`) | Read-only commands |
|---------------------------------|--------------------|
| `ingest` | `accounts` |
| `categorize` | `categories` |
| `recategorize` | `ytd` |
| `auto-categorize` | `uncategorized` |
| `category` | `budget` |
| `note` | `diagnose-categories` |
| `report` | `duplicates` |
| `mark-duplicate` | `audit-ml` |
| `backfill-events` | `prompt-stats` |
| `migrate-to-events` | |
| `rebuild-projections` (always writes) | |
| `init` (always writes) | |

## Quick Command Reference

### View

| Command | Purpose |
|---------|---------|
| `accounts` | List account IDs and descriptions |
| `categories` | List categories with usage stats |
| `ytd` | Year-to-date transactions for one account |
| `uncategorized` | Transactions missing categories |
| `budget` | Budget vs actual spending summary |

### Setup

| Command | Purpose |
|---------|---------|
| `init` | Initialize a new workspace with directories and starter config |

### Import

| Command | Purpose |
|---------|---------|
| `ingest` | Normalize raw bank CSVs into per-account ledgers |

### Categorize

| Command | Purpose |
|---------|---------|
| `categorize` | Assign category to transactions (single or batch) |
| `recategorize` | Rename a category across all ledgers |
| `auto-categorize` | ML-based auto-categorization |
| `category` | Add/remove categories, set budgets |
| `diagnose-categories` | Find categories in transactions not in config |

### Annotate

| Command | Purpose |
|---------|---------|
| `note` | Attach notes to transactions |

### Report

| Command | Purpose |
|---------|---------|
| `budget` | Terminal budget summary |
| `report` | Generate .md and .docx budget reports |

### Duplicates

| Command | Purpose |
|---------|---------|
| `duplicates` | Scan for duplicates (ML or LLM) |
| `mark-duplicate` | Manually mark a transaction pair as duplicates |

### ML / Debug

| Command | Purpose |
|---------|---------|
| `audit-ml` | Inspect ML training data and decisions |
| `prompt-stats` | LLM prompt learning statistics |

### Maintenance

| Command | Purpose |
|---------|---------|
| `rebuild-projections` | Rebuild projections from event store |
| `backfill-events` | Backfill events from CSVs (advanced) |
| `migrate-to-events` | One-command migration to event sourcing |

## Account IDs

| ID | Institution | Product | Nature |
|----|-------------|---------|--------|
| `MYBANK_CHQ` | MyBank | Chequing | asset |
| `BANK2_BIZ` | SecondBank | Business Chequing | asset |
| `BANK2_CHQ` | SecondBank | Personal Chequing | asset |
| `BANK2_LOC` | SecondBank | Line of Credit | liability |
| `MYBANK_CC` | MyBank | Credit Card | liability |

## Category Syntax

Categories use **colon notation**: `"TopLevel:Subcategory"`.

```
gilt categorize --txid abc12345 --category "Housing:Utilities" --write
```

Alternative: separate flags `--category Housing --subcategory Utilities`.

To add a new top-level category:
```
gilt category --add "NewCategory" --description "..." --write
```

To add a subcategory:
```
gilt category --add "Existing:NewSub" --write
```

Categories must exist in `config/categories.yml` before use. Use `gilt categories` to see all defined categories.

## Transaction Matching

Commands like `categorize` and `note` support 4 matching modes:

| Mode | Flag | Behavior |
|------|------|----------|
| Single | `--txid` / `-t` | Match one transaction by ID prefix (8+ chars) |
| Exact | `--description` / `-d` | Match all with exact description |
| Prefix | `--desc-prefix` / `-p` | Case-insensitive prefix match |
| Regex | `--pattern` | Case-insensitive regex on description |

**Combine with `--amount` / `-m`** to narrow batch matches to a specific dollar amount.

**Use only one matching mode per invocation.** Do not combine `--txid` with `--description`, etc.

In batch mode, add `--yes` / `-y` to skip per-transaction confirmations.

## Common Workflows

### Set up a new workspace
```bash
# Initialize workspace structure with starter config files
uv run gilt --data-dir ~/finances init

# Then edit the generated config files:
#   ~/finances/config/accounts.yml   — define your bank accounts
#   ~/finances/config/categories.yml — define spending categories

# Import your first data
uv run gilt --data-dir ~/finances ingest --write
uv run gilt --data-dir ~/finances migrate-to-events --write
```

The `init` command creates all required directories (`config/`, `data/accounts/`, `ingest/`, `reports/`) and writes starter `accounts.yml` and `categories.yml` with commented examples. It is idempotent — safe to run on an existing workspace (skips anything that already exists, never overwrites files).

### Import new bank data
```bash
# Drop CSV files into ingest/, then:
uv run gilt ingest                  # Preview
uv run gilt ingest --write          # Persist
uv run gilt rebuild-projections     # Update projections
```

### Categorize transactions
```bash
# Find uncategorized
uv run gilt uncategorized --account MYBANK_CHQ --year 2025

# Single transaction
uv run gilt categorize -a MYBANK_CHQ --txid abc12345 -c "Groceries" --write

# Batch by description prefix
uv run gilt categorize --desc-prefix "SPOTIFY" -c "Entertainment:Subscriptions" --yes --write

# ML auto-categorize
uv run gilt auto-categorize --confidence 0.8 --write
```

### Budget review
```bash
uv run gilt budget                              # Current year
uv run gilt budget --year 2025 --month 10       # Specific month
uv run gilt report --year 2025 --write          # Generate .docx
```

### Handle duplicates
```bash
uv run gilt duplicates                          # ML-based scan
uv run gilt duplicates --interactive            # Train ML with feedback
uv run gilt mark-duplicate -p abc12345 -d def67890 --write
```

### Manage categories
```bash
uv run gilt categories                          # View all
uv run gilt category --add "Travel:Flights" --write
uv run gilt category --set-budget "Dining Out" --amount 500 --write
uv run gilt recategorize --from "OldName" --to "NewName" --write
uv run gilt diagnose-categories                 # Find orphaned categories
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Forgetting `--write` | Nothing persists without it. Re-run with `--write`. |
| `--data-dir` after command | `--data-dir` is a **top-level** option: `gilt --data-dir PATH budget`, not `gilt budget --data-dir PATH`. |
| Category doesn't exist | Add it first: `gilt category --add "Cat:Sub" --write` |
| Wrong amount sign | Expenses are **negative**, income is **positive** in ledgers. Match accordingly with `--amount`. |
| Combining match modes | Use only one of `--txid`, `--description`, `--desc-prefix`, `--pattern` per call. |
| Workspace not initialized | Run `gilt --data-dir PATH init` to create directories and starter config. |
| Missing projections DB | Run `gilt migrate-to-events --write` or `gilt rebuild-projections`. |
| Missing event store | Run `gilt migrate-to-events --write` first. |
| Batch without `--yes` | Without `--yes`, each match prompts interactively (won't work in non-interactive shells). |

## Workspace and Data Paths

All paths are resolved from a single **workspace root** directory. The CLI determines the workspace root using this priority:

1. `--data-dir PATH` (top-level CLI option, applies to all commands)
2. `GILT_DATA` environment variable
3. Current working directory (default)

```bash
# Use current directory as workspace (default)
uv run gilt budget

# Explicit workspace root
uv run gilt --data-dir /path/to/my/finances budget

# Via environment variable
GILT_DATA=/path/to/my/finances uv run gilt budget
```

**`--data-dir` is a top-level option, not a per-command option.** It must appear before the command name.

### Workspace Layout

All paths below are relative to the workspace root:

| Path | Contents | Workspace Property |
|------|----------|--------------------|
| `config/accounts.yml` | Account definitions | `accounts_config` |
| `config/categories.yml` | Category tree and budgets | `categories_config` |
| `data/accounts/` | Per-account ledger CSVs | `ledger_data_dir` |
| `data/events.db` | Immutable event store | `event_store_path` |
| `data/projections.db` | Materialized transaction view | `projections_path` |
| `data/budget_projections.db` | Materialized budget view | `budget_projections_path` |
| `ingest/` | Drop raw bank CSVs here | `ingest_dir` |
| `reports/` | Generated report output | `reports_dir` |

### Workspace in Code

Path resolution is centralized in `gilt.workspace.Workspace`. All command modules and services accept a `workspace: Workspace` parameter instead of individual path arguments.

```python
from gilt.workspace import Workspace

# Resolve from env/CWD (used by CLI callback)
workspace = Workspace.resolve()

# Explicit root (used in tests)
workspace = Workspace(root=Path("/tmp/test"))

# Access paths as properties
workspace.event_store_path      # root / "data" / "events.db"
workspace.projections_path      # root / "data" / "projections.db"
workspace.ledger_data_dir       # root / "data" / "accounts"
workspace.categories_config     # root / "config" / "categories.yml"
```

The `EventSourcingService` also accepts `workspace=` to derive its paths:

```python
es_service = EventSourcingService(workspace=workspace)
```

### Testing with Workspace

Tests create a `Workspace` pointing at a temp directory. Use the `init` command's `run()` to scaffold the workspace, or create directories manually if you only need a subset:

```python
from gilt.workspace import Workspace
from gilt.cli.command.init import run as init_workspace

def test_with_full_workspace():
    with TemporaryDirectory() as tmpdir:
        workspace = Workspace(root=Path(tmpdir))
        init_workspace(workspace=workspace)  # creates all dirs + starter config
        rc = run(workspace=workspace, ...)

def test_with_minimal_dirs():
    with TemporaryDirectory() as tmpdir:
        workspace = Workspace(root=Path(tmpdir))
        (Path(tmpdir) / "data" / "accounts").mkdir(parents=True)
        (Path(tmpdir) / "config").mkdir(parents=True)
        rc = run(workspace=workspace, ...)
```

## Full Command Reference

For complete option listings and examples for all 20 commands, see [references/command-reference.md](references/command-reference.md).
