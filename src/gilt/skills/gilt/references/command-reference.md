# Gilt CLI Command Reference

All commands are invoked as `uv run gilt [--data-dir PATH] <command> [OPTIONS]`.

**Workspace root:** All data paths are derived from a single workspace root. Set it with:
- `--data-dir PATH` (top-level option, before the command name)
- `GILT_DATA` environment variable
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
uv run gilt --data-dir ~/finances init
uv run gilt init
```

---

## accounts

List available accounts (IDs and descriptions).

No command-specific options. All paths derived from workspace root.

```bash
uv run gilt accounts
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
uv run gilt audit-ml
uv run gilt audit-ml --mode training --filter "PRESTO"
uv run gilt audit-ml --mode predictions --limit 10
uv run gilt audit-ml --mode features
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
uv run gilt auto-categorize
uv run gilt auto-categorize --confidence 0.8 --write
uv run gilt auto-categorize --account MYBANK_CHQ --interactive --write
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
uv run gilt backfill-events
uv run gilt backfill-events --write
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
uv run gilt budget
uv run gilt budget --year 2025
uv run gilt budget --year 2025 --month 10
uv run gilt budget --category "Dining Out"
```

---

## categories

List all defined categories with usage statistics.

No command-specific options. All paths derived from workspace root.

```bash
uv run gilt categories
```

---

## categorize

Categorize transactions (single, batch, or file-batch mode).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | None | Account ID (omit to categorize across all) |
| `--txid`, `-t` | String | None | Transaction ID prefix (single mode) |
| `--description`, `-d` | String | None | Exact description to match (batch mode) |
| `--desc-prefix`, `-p` | String | None | Description prefix (batch, case-insensitive) |
| `--pattern` | String | None | Regex on description (batch, case-insensitive) |
| `--amount`, `-m` | Float | None | Exact amount to match (batch mode) |
| `--category`, `-c` | String | None | Category name (`"Cat:Sub"` syntax) |
| `--subcategory`, `-s` | String | None | Subcategory (alternative to colon syntax) |
| `--yes`, `-y` | Bool | `False` | Skip batch confirmations |
| `--txid-file` | Path | None | File of `<txid-prefix> <category>` pairs (file-batch mode) |
| `--from-stdin` | Bool | `False` | Read `<txid-prefix> <category>` pairs from stdin (file-batch mode) |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

Use exactly one matching mode: `--txid`, `--description`, `--desc-prefix`, `--pattern`, `--txid-file`, or `--from-stdin`.

File/stdin format (one entry per line):
```
# Comments start with #
7f860a03 Housing:Utilities
9bc16ce1 Banking:Fees
```

File-batch is applied all-or-nothing — any unknown txid aborts the entire batch.

```bash
uv run gilt categorize -a MYBANK_CHQ --txid a1b2c3d4 -c "Housing:Utilities" --write
uv run gilt categorize --desc-prefix "SPOTIFY" -c "Entertainment:Subscriptions" --yes --write
uv run gilt categorize --pattern "Payment.*EXAMPLE UTILITY" -c "Housing:Utilities" --yes --write
uv run gilt categorize --txid-file batch.txt --write
uv run gilt categorize --from-stdin --write < batch.txt
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
uv run gilt category --add "Housing" --description "Housing expenses" --write
uv run gilt category --add "Housing:Utilities" --write
uv run gilt category --set-budget "Dining Out" --amount 400 --write
uv run gilt category --remove "Old Category" --write
```

---

## diagnose-categories

Find categories in transactions that aren't defined in config.

No command-specific options. All paths derived from workspace root.

```bash
uv run gilt diagnose-categories
```

---

## diagnose-duplicates

Read-only diagnostic for duplicate-projection issues. Reports orphan duplicate groups, stale primary references, and self-referential primaries.

No command-specific options.

```bash
uv run gilt diagnose-duplicates
```

---

## duplicates

Scan ledgers for duplicate transactions using ML or LLM analysis.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--model` | String | `qwen3.5:27b` | Ollama model for LLM mode |
| `--max-days` | Int | `1` | Maximum days between potential duplicates |
| `--amount-tolerance` | Float | `0.001` | Acceptable difference in amounts |
| `--min-confidence` | Float | `0.0` | Minimum confidence threshold (0.0-1.0) |
| `--interactive`, `-i` | Bool | `False` | Interactive mode (confirm/deny each) |
| `--llm` | Bool | `False` | Use LLM instead of ML |

By default uses ML. Falls back to LLM if insufficient training data. LLM mode requires Ollama.

```bash
uv run gilt duplicates
uv run gilt duplicates --interactive
uv run gilt duplicates --llm --model qwen3.5:27b
uv run gilt duplicates -i --min-confidence 0.7
```

---

## ingest

Ingest and normalize raw CSVs into standardized per-account ledgers.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

Drop raw bank CSVs into `ingest/` (relative to workspace root), then run:

```bash
uv run gilt ingest
uv run gilt ingest --write
```

---

## ingest-receipts

Ingest receipt JSON sidecar files (`mailctl.receipt.v1` format) and enrich matching bank transactions by amount and date.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--source` | Path | **required** | Root directory containing receipt JSON files (recursive scan) |
| `--year`, `-y` | Int | None | Only process receipts from this year |
| `--account`, `-a` | String | None | Limit matching to this account |
| `--interactive`, `-i` | Bool | `False` | Interactively resolve ambiguous matches |
| `--write` | Bool | `False` | **Persist enrichment events (dry-run by default)** |

```bash
uv run gilt ingest-receipts --source ~/receipts
uv run gilt ingest-receipts --source ~/receipts --year 2025 --write
uv run gilt ingest-receipts --source ~/receipts --account MYBANK_CC --write
uv run gilt ingest-receipts --source ~/receipts --interactive --write
```

---

## infer-rules

Infer categorization rules from transaction history. Scans categorization history for descriptions consistently categorized the same way. Use `--apply` to match rules against uncategorized transactions.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--apply` | Bool | `False` | Apply inferred rules to uncategorized transactions |
| `--min-evidence` | Int | `3` | Minimum categorizations required to infer a rule (min 1) |
| `--min-confidence` | Float | `0.9` | Minimum consistency ratio to infer a rule (0.0–1.0) |
| `--export` | String | None | Export inferred rules to a JSON file |
| `--write` | Bool | `False` | **Persist rule applications (dry-run by default; requires `--apply`)** |

```bash
uv run gilt infer-rules                          # Preview inferred rules
uv run gilt infer-rules --apply                  # Preview which transactions would be updated
uv run gilt infer-rules --apply --write          # Apply and persist
uv run gilt infer-rules --min-evidence 5 --min-confidence 0.95
uv run gilt infer-rules --export rules.json
```

---

## history

Look up how similar transactions have been categorized in the past. Performs a case-insensitive substring match on transaction descriptions, groups results by category/subcategory, and displays counts, sums, min/max amounts, and the latest date.

Read-only — no `--write` flag needed.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `PATTERN` | String | **required** | Substring to search in transaction descriptions |
| `--account`, `-a` | String | None | Restrict to this account ID |
| `--include-uncategorized` | Bool | `False` | Include transactions with no category |
| `--limit`, `-n` | Int | None | Maximum result rows (ordered by count descending) |
| `--date-from` | String | None | Start date (YYYY-MM-DD, inclusive) |
| `--date-to` | String | None | End date (YYYY-MM-DD, inclusive) |

```bash
uv run gilt history "EXAMPLE PHARMACY"
uv run gilt history "ACME CORP" --account MYBANK_CHQ
uv run gilt history "SAMPLE STORE" --include-uncategorized
uv run gilt history "EXAMPLE UTILITY" --date-from 2025-01-01 --date-to 2025-12-31
uv run gilt history "EXAMPLE" --limit 5
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
uv run gilt mark-duplicate -p a1b2c3d4 -d e5f6g7h8
uv run gilt mark-duplicate -p a1b2c3d4 -d e5f6g7h8 --write
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
uv run gilt migrate-to-events
uv run gilt migrate-to-events --write
uv run gilt migrate-to-events --write --force
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
uv run gilt note -a MYBANK_CHQ --txid abc12345 --note "Reimbursed" --write
uv run gilt note -a MYBANK_CC --desc-prefix "AMAZON" --note "Office supplies" --yes --write
```

---

## prompt-stats

Show prompt learning statistics and generate updates.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--generate-update`, `-g` | Bool | `False` | Generate a new PromptUpdated event |

Requires prior interactive duplicate detection feedback.

```bash
uv run gilt prompt-stats
uv run gilt prompt-stats --generate-update
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
uv run gilt rebuild-projections
uv run gilt rebuild-projections --from-scratch
```

---

## receipts

Display receipt attachment coverage for categorised transactions. Shows total transactions, how many have receipts attached, and coverage percentage grouped by subcategory (default) or account.

Read-only — no `--write` flag needed.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--by-account` | Bool | `False` | Group by account_id instead of subcategory |
| `--fy` | String | None | Fiscal year filter (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025. |
| `--missing` | Bool | `False` | List individual transactions without receipts instead of the summary table |
| `--category`, `-c` | String | `Mojility` | Category to report on |

```bash
uv run gilt receipts
uv run gilt receipts --fy FY25
uv run gilt receipts --by-account
uv run gilt receipts --missing
uv run gilt receipts --category Food
uv run gilt receipts --fy FY25 --missing
```

---

## recategorize

Rename a category or recategorize a filtered selection of transactions. Two modes:

- **Rename mode** (no selection flags): renames every transaction with `--from` category to `--to`. `--from` is required.
- **Selection mode** (any selection flag present): applies `--to` to the filtered subset. `--from` is optional narrowing filter.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--from` | String | None | Original category (`"Cat:Sub"` syntax); required in rename mode |
| `--to` | String | **required** | New category name (`"Cat:Sub"` syntax) |
| `--account`, `-a` | String | None | Restrict selection to this account ID |
| `--desc-prefix`, `-p` | String | None | Description prefix filter (case-insensitive) |
| `--pattern` | String | None | Regex pattern filter on descriptions |
| `--amount-eq` | Float | None | Exact signed amount to match |
| `--amount-min` | Float | None | Minimum signed amount (inclusive) |
| `--amount-max` | Float | None | Maximum signed amount (inclusive) |
| `--date-from` | String | None | Start date (YYYY-MM-DD, inclusive) |
| `--date-to` | String | None | End date (YYYY-MM-DD, inclusive) |
| `--fy` | String | None | Fiscal year filter (e.g. `FY25`); cannot combine with `--date-from`/`--date-to` |
| `--write` | Bool | `False` | **Persist changes (dry-run by default)** |

```bash
uv run gilt recategorize --from "Business" --to "Work" --write
uv run gilt recategorize --from "Business:Meals" --to "Work:Meals" --write
uv run gilt recategorize --desc-prefix "ACME CORP" --to "Work:Subscriptions" --write
uv run gilt recategorize --desc-prefix "ACME CORP" --amount-eq -18.30 --account MYBANK_CC --to "Work:Subscriptions" --write
uv run gilt recategorize --pattern "SAMPLE STORE" --fy FY25 --to "Groceries" --write
```

---

## reingest

Purge and re-ingest all transactions for a single account. Removes the account's ledger CSV, purges related events and projections, clears cached intelligence, then re-runs ingestion from the original source files. Use after changing `import_hints` (e.g. `amount_sign`) or when an account's data needs a clean slate without affecting other accounts.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | **required** | Account ID to reingest (e.g. `MYBANK_CC`) |
| `--write` | Bool | `False` | **Execute reingest (dry-run by default)** |

```bash
uv run gilt reingest --account MYBANK_CC          # Preview
uv run gilt reingest -a MYBANK_CC --write          # Execute
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
uv run gilt report
uv run gilt report --year 2025 --write
uv run gilt report --year 2025 --month 10 --write
```

---

## show

Show all stored fields for a single transaction. Displays the full projection record including description history, enrichment fields, duplicate status, and event metadata.

Read-only — no `--write` flag needed.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--txid`, `-t` | String | **required** | Transaction ID prefix (8+ characters) |

```bash
uv run gilt show --txid a1b2c3d4
uv run gilt show -t a1b2c3d4e5f6g7h8
```

---

## status

Display per-account freshness and coverage dashboard. Read-only — no `--write` flag needed.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--fy` | String | None | Fiscal year for Mojility columns (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025. |
| `--stale-threshold` | Int | `14` | Days since latest transaction before account is flagged stale (min 0) |

Shows: `account_id`, `latest_txn`, `days_since`, `total_txns`, `uncategorized`, `mojility_txns` (FY-filtered when `--fy` given), `mojility_w_receipt`, `mojility_receipt_pct`. Stale accounts are highlighted in red with a ⚠ marker.

```bash
uv run gilt status
uv run gilt status --fy FY25
uv run gilt status --stale-threshold 30
```

---

## summary

Display category or subcategory spending aggregation. Without `--category` shows the top-level category breakdown; with `--category <name>` drills into that category's subcategories.

Read-only — no `--write` flag needed.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--category`, `-c` | String | None | Drill into one category's subcategories |
| `--year`, `-y` | Int | current year | Calendar year |
| `--fy` | String | None | Fiscal year (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025. |
| `--account`, `-a` | String | None | Account ID to filter |
| `--include-uncategorized` | Bool | `False` | Include rows where category is null |

```bash
uv run gilt summary
uv run gilt summary --year 2025
uv run gilt summary --fy FY25
uv run gilt summary --category Housing
uv run gilt summary --category Housing --fy FY25
uv run gilt summary --account MYBANK_CHQ --year 2025
uv run gilt summary --include-uncategorized
```

---

## uncategorized

Display transactions without categories. Defaults to all accounts; use `--account` to narrow. Includes a per-account count summary below the main table.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--account`, `-a` | String | None | Account ID to filter (omit for all accounts) |
| `--year`, `-y` | Int | None | Calendar year to filter |
| `--fy` | String | None | Fiscal year to filter (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025. |
| `--limit`, `-n` | Int | None | Max transactions to show (min 1) |
| `--min-amount` | Float | None | Minimum absolute amount to include |

```bash
uv run gilt uncategorized
uv run gilt uncategorized --account MYBANK_CHQ --year 2025
uv run gilt uncategorized --fy FY25
uv run gilt uncategorized --min-amount 100 --limit 50
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
uv run gilt ytd --account MYBANK_CHQ
uv run gilt ytd -a MYBANK_CC --year 2024 --limit 50
uv run gilt ytd -a BANK2_LOC --include-duplicates
```
