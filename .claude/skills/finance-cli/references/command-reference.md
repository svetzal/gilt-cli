# Finance CLI Command Reference

All commands are invoked as `uv run finance [--data-dir PATH] <command> [OPTIONS]`.

**Workspace root:** All data paths are derived from a single workspace root. Set it with:
- `--data-dir PATH` (top-level option, before the command name)
- `FINANCE_DATA` environment variable
- Defaults to current working directory

---

## init

Initialize a new workspace with required directories and starter config files. Safe to run on an existing workspace — skips anything that already exists.

Creates:
- `config/` with starter `accounts.yml` and `categories.yml`
- `data/accounts/`
- `ingest/`
- `reports/`

No command-specific options.

```bash
uv run finance --data-dir ~/finances init
uv run finance init
```

---

## accounts

List available accounts (IDs and descriptions).

No command-specific options. All paths derived from workspace root.

```bash
uv run finance accounts
```

---

## audit-ml

Audit ML classifier training data and decisions.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mode`, `-m` | String | `summary` | Audit mode: `summary`, `training`, `predictions`, or `features` |
| `--filter`, `-f` | String | None | Regex pattern to filter descriptions |
| `--limit`, `-n` | Int | `20` | Maximum examples to show |

```bash
uv run finance audit-ml
uv run finance audit-ml --mode training --filter "PRESTO"
uv run finance audit-ml --mode predictions --limit 10
uv run finance audit-ml --mode features
```

---

## auto-categorize

Auto-categorize transactions using ML classifier.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | None | Account ID (omit for all accounts) |
| `--confidence`, `-c` | Float | `0.7` | Minimum confidence threshold (0.0-1.0) |
| `--min-samples` | Int | `5` | Minimum samples per category for training |
| `--interactive`, `-i` | Bool | `False` | Enable interactive review mode |
| `--limit`, `-n` | Int | None | Max transactions to auto-categorize |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

```bash
uv run finance auto-categorize
uv run finance auto-categorize --confidence 0.8 --write
uv run finance auto-categorize --account MYBANK_CHQ --interactive --write
```

---

## backfill-events

Backfill events from existing data (advanced/debugging). Most users should use `migrate-to-events` instead.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--event-store` | Path | None | Path to event store database (advanced override) |
| `--projections-db` | Path | None | Path to transaction projections database (advanced override) |
| `--budget-projections-db` | Path | None | Path to budget projections database (advanced override) |
| `--write` | Bool | `False` | **Actually write events (dry-run by default)** |

```bash
uv run finance backfill-events
uv run finance backfill-events --write
```

---

## budget

Display budget summary comparing actual spending vs budgeted amounts.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--year`, `-y` | Int | current year | Year to report |
| `--month`, `-m` | Int | None | Month to report (1-12, requires --year) |
| `--category`, `-c` | String | None | Filter to specific category |

```bash
uv run finance budget
uv run finance budget --year 2025
uv run finance budget --year 2025 --month 10
uv run finance budget --category "Dining Out"
```

---

## categories

List all defined categories with usage statistics.

No command-specific options. All paths derived from workspace root.

```bash
uv run finance categories
```

---

## categorize

Categorize transactions (single or batch mode).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | None | Account ID (omit to categorize across all) |
| `--txid`, `-t` | String | None | Transaction ID prefix (single mode) |
| `--description`, `-d` | String | None | Exact description to match (batch mode) |
| `--desc-prefix`, `-p` | String | None | Description prefix (batch, case-insensitive) |
| `--pattern` | String | None | Regex on description (batch, case-insensitive) |
| `--amount`, `-m` | Float | None | Exact amount to match (batch mode) |
| `--category`, `-c` | String | **required** | Category name (`"Cat:Sub"` syntax) |
| `--subcategory`, `-s` | String | None | Subcategory (alternative to colon syntax) |
| `--yes`, `-y` | Bool | `False` | Skip batch confirmations |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

Use exactly one matching mode: `--txid`, `--description`, `--desc-prefix`, or `--pattern`.

```bash
uv run finance categorize -a MYBANK_CHQ --txid a1b2c3d4 -c "Housing:Utilities" --write
uv run finance categorize --desc-prefix "SPOTIFY" -c "Entertainment:Subscriptions" --yes --write
uv run finance categorize --pattern "Payment.*EXAMPLE UTILITY" -c "Housing:Utilities" --yes --write
```

---

## category

Manage categories: add, remove, or set budget.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--add` | String | None | Add a new category (`"Cat:Sub"` syntax) |
| `--remove` | String | None | Remove a category |
| `--set-budget` | String | None | Set budget for a category |
| `--description` | String | None | Description for new category |
| `--amount` | Float | None | Budget amount |
| `--period` | String | `monthly` | Budget period (`monthly` or `yearly`) |
| `--force` | Bool | `False` | Skip confirmations when removing used categories |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

```bash
uv run finance category --add "Housing" --description "Housing expenses" --write
uv run finance category --add "Housing:Utilities" --write
uv run finance category --set-budget "Dining Out" --amount 400 --write
uv run finance category --remove "Old Category" --write
```

---

## diagnose-categories

Find categories in transactions that aren't defined in config.

No command-specific options. All paths derived from workspace root.

```bash
uv run finance diagnose-categories
```

---

## duplicates

Scan ledgers for duplicate transactions using ML or LLM analysis.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--model` | String | `qwen3:30b` | Ollama model for LLM mode |
| `--max-days` | Int | `1` | Maximum days between potential duplicates |
| `--amount-tolerance` | Float | `0.001` | Acceptable difference in amounts |
| `--min-confidence` | Float | `0.0` | Minimum confidence threshold (0.0-1.0) |
| `--interactive`, `-i` | Bool | `False` | Interactive mode (confirm/deny each) |
| `--llm` | Bool | `False` | Use LLM instead of ML |

By default uses ML. Falls back to LLM if insufficient training data. LLM mode requires Ollama.

```bash
uv run finance duplicates
uv run finance duplicates --interactive
uv run finance duplicates --llm --model qwen3:30b
uv run finance duplicates -i --min-confidence 0.7
```

---

## ingest

Ingest and normalize raw CSVs into standardized per-account ledgers.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

Drop raw bank CSVs into `ingest/` (relative to workspace root), then run:

```bash
uv run finance ingest
uv run finance ingest --write
```

---

## mark-duplicate

Manually mark a specific pair of transactions as duplicates.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--primary`, `-p` | String | **required** | Transaction ID to keep (8+ char prefix) |
| `--duplicate`, `-d` | String | **required** | Transaction ID to mark as duplicate (8+ char prefix) |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

The primary is kept; the duplicate is hidden from budgets/reports but preserved in the event store.

```bash
uv run finance mark-duplicate -p a1b2c3d4 -d e5f6g7h8
uv run finance mark-duplicate -p a1b2c3d4 -d e5f6g7h8 --write
```

---

## migrate-to-events

One-command migration to event sourcing (recommended for upgrades).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--event-store` | Path | None | Path to event store database (advanced override) |
| `--projections-db` | Path | None | Path to transaction projections database (advanced override) |
| `--budget-projections-db` | Path | None | Path to budget projections database (advanced override) |
| `--write` | Bool | `False` | **Actually perform migration (dry-run by default)** |
| `--force` | Bool | `False` | Overwrite existing event store |

```bash
uv run finance migrate-to-events
uv run finance migrate-to-events --write
uv run finance migrate-to-events --write --force
```

---

## note

Attach or update notes on transactions.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | **required** | Account ID containing the transaction |
| `--txid`, `-t` | String | None | Transaction ID prefix (single mode) |
| `--description`, `-d` | String | None | Exact description to match (batch mode) |
| `--desc-prefix`, `-p` | String | None | Description prefix (batch, case-insensitive) |
| `--pattern` | String | None | Regex on description (batch, case-insensitive) |
| `--amount`, `-m` | Float | None | Exact amount to match (batch mode) |
| `--note`, `-n` | String | **required** | Note text to set |
| `--yes`, `-y` | Bool | `False` | Skip batch confirmations |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

Use exactly one matching mode: `--txid`, `--description`, `--desc-prefix`, or `--pattern`.

```bash
uv run finance note -a MYBANK_CHQ --txid abc12345 --note "Reimbursed" --write
uv run finance note -a MYBANK_CC --desc-prefix "AMAZON" --note "Office supplies" --yes --write
```

---

## prompt-stats

Show prompt learning statistics and generate updates.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--generate-update`, `-g` | Bool | `False` | Generate a new PromptUpdated event |

Requires prior interactive duplicate detection feedback.

```bash
uv run finance prompt-stats
uv run finance prompt-stats --generate-update
```

---

## rebuild-projections

Rebuild transaction projections from event store.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--from-scratch` | Bool | `False` | Delete existing projections and rebuild |
| `--incremental` | Bool | `False` | Only apply new events since last rebuild |
| `--events-db` | Path | None | Path to events database (advanced override) |
| `--projections-db` | Path | None | Path to projections database (advanced override) |

Note: This command always writes. No `--write` flag needed.

```bash
uv run finance rebuild-projections
uv run finance rebuild-projections --from-scratch
```

---

## recategorize

Rename a category across all ledger files.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--from` | String | **required** | Original category name (`"Cat:Sub"` syntax) |
| `--to` | String | **required** | New category name (`"Cat:Sub"` syntax) |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

```bash
uv run finance recategorize --from "Business" --to "Work" --write
uv run finance recategorize --from "Business:Meals" --to "Work:Meals" --write
```

---

## report

Generate budget report as markdown and Word document (.docx).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--year`, `-y` | Int | current year | Year to report |
| `--month`, `-m` | Int | None | Month (1-12, requires --year) |
| `--output`, `-o` | Path | `reports/budget_report_YYYY[-MM]` | Output path (without extension) |
| `--write` | Bool | `False` | **Persist files (dry-run by default)** |

Requires `pandoc` for .docx generation (`brew install pandoc` on macOS).

```bash
uv run finance report
uv run finance report --year 2025 --write
uv run finance report --year 2025 --month 10 --write
```

---

## uncategorized

Display transactions without categories.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | None | Account ID to filter (omit for all) |
| `--year`, `-y` | Int | None | Year to filter |
| `--limit`, `-n` | Int | None | Max transactions to show |
| `--min-amount` | Float | None | Minimum absolute amount |

```bash
uv run finance uncategorized
uv run finance uncategorized --account MYBANK_CHQ --year 2025
uv run finance uncategorized --min-amount 100 --limit 50
```

---

## ytd

Show year-to-date transactions for a single account.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | **required** | Account ID to display |
| `--year`, `-y` | Int | current year | Year to filter |
| `--limit`, `-n` | Int | None | Max rows to show |
| `--default-currency` | String | None | Fallback currency for legacy rows |
| `--include-duplicates` | Bool | `False` | Include transactions marked as duplicates |

Loads from projections database. Duplicates excluded by default.

```bash
uv run finance ytd --account MYBANK_CHQ
uv run finance ytd -a MYBANK_CC --year 2024 --limit 50
uv run finance ytd -a BANK2_LOC --include-duplicates
```
