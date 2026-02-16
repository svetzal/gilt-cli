# Initial Setup Workflow

This guide walks you through setting up Finance for the first time and importing your first batch of transactions.

## Prerequisites

Before starting, ensure you have:

- ✅ Python 3.13+ installed
- ✅ Finance installed (see [Installation Guide](../installation.md))
- ✅ Access to your bank's online banking
- ✅ Virtual environment activated

## Step 1: Create Configuration Files

### Create Accounts Configuration

Create `config/accounts.yml` to define your bank accounts:

```bash
mkdir -p config
cat > config/accounts.yml << 'EOF'
accounts:
  - account_id: CHECKING
    description: "My Bank Checking Account"
    source_patterns:
      - "*checking*.csv"
      - "*chequing*.csv"

  - account_id: SAVINGS
    description: "My Bank Savings Account"
    source_patterns:
      - "*savings*.csv"

  - account_id: CREDIT_CARD
    description: "My Credit Card"
    source_patterns:
      - "*creditcard*.csv"
      - "*visa*.csv"
      - "*mastercard*.csv"
EOF
```

**Tips:**
- Use short, memorable account IDs (e.g., `MYBANK_CHQ`, `BANK2_VISA`)
- Account IDs become file names and command parameters
- Source patterns use wildcards to match CSV filenames
- Patterns are case-insensitive

### Create Categories Configuration

Create `config/categories.yml` to define spending categories:

```bash
cat > config/categories.yml << 'EOF'
categories:
  - name: "Housing"
    description: "Housing and utilities"
    budget:
      amount: 2000.00
      period: monthly
    subcategories:
      - name: "Rent"
        description: "Monthly rent payment"
      - name: "Utilities"
        description: "Electric, gas, water, internet"
      - name: "Maintenance"
        description: "Repairs and upkeep"

  - name: "Transportation"
    description: "Vehicle and transit costs"
    budget:
      amount: 500.00
      period: monthly
    subcategories:
      - name: "Fuel"
        description: "Gas for vehicle"
      - name: "Transit"
        description: "Bus, train, subway"
      - name: "Parking"
        description: "Parking fees"

  - name: "Groceries"
    description: "Food and household items"
    budget:
      amount: 600.00
      period: monthly

  - name: "Dining Out"
    description: "Restaurants and takeout"
    budget:
      amount: 400.00
      period: monthly

  - name: "Entertainment"
    description: "Recreation and leisure"
    budget:
      amount: 200.00
      period: monthly
    subcategories:
      - name: "Streaming"
        description: "Netflix, Spotify, etc."
      - name: "Movies"
        description: "Theater and rentals"

  - name: "Healthcare"
    description: "Medical and wellness"
    budget:
      amount: 150.00
      period: monthly
    subcategories:
      - name: "Prescriptions"
      - name: "Dental"
      - name: "Vision"

  - name: "Banking"
    description: "Bank fees and charges"
    subcategories:
      - name: "Fees"
        description: "Monthly fees, overdraft"
      - name: "Interest"
        description: "Interest charges"
EOF
```

**Tips:**
- Start with broad categories, add subcategories as needed
- Budget amounts can be added later
- Period can be `monthly` or `yearly`
- Categories without budgets are tracked but not monitored

### Verify Configuration

```bash
# List configured accounts
finance accounts

# List configured categories
finance categories
```

## Step 2: Export Bank Data

### For Each Bank Account:

1. **Log in to online banking**
2. **Navigate to transaction history**
3. **Select date range**:
   - For initial setup: 3-6 months recommended
   - You can always add older data later
4. **Export as CSV**:
   - Look for "Download", "Export", or "Report" options
   - Choose CSV format (not PDF or Excel)
5. **Save with descriptive filename**:
   - Good: `2025-11-16-checking.csv`
   - Good: `2025-11-16-visa-card.csv`
   - Bad: `transactions.csv` (too generic)

!!! tip "Filename Conventions"
    Use date prefixes (YYYY-MM-DD) in filenames. Finance uses this to infer import timestamps for the event log.

### Create Ingest Directory

```bash
mkdir -p ingest
```

### Place CSV Files

Move all exported CSV files into the `ingest/` directory:

```bash
mv ~/Downloads/*checking*.csv ingest/
mv ~/Downloads/*visa*.csv ingest/
# etc.
```

Your structure should look like:

```
finance/
├── config/
│   ├── accounts.yml
│   └── categories.yml
└── ingest/
    ├── 2025-11-16-checking.csv
    ├── 2025-11-16-savings.csv
    └── 2025-11-16-visa.csv
```

## Step 3: Import Transactions

### Preview Import (Dry-Run)

Always preview first to catch configuration issues:

```bash
finance ingest
```

**What to look for:**
- ✅ All CSV files matched to correct accounts
- ✅ Transaction counts look reasonable
- ✅ No error messages
- ❌ Files marked as "no matching account" → fix `source_patterns` in `accounts.yml`
- ❌ Error parsing CSV → check CSV format, may need custom `import_hints`

### Execute Import

If preview looks good:

```bash
finance ingest --write
```

**What happens:**
1. Reads each CSV file
2. Matches to account using `source_patterns`
3. Normalizes column names and formats
4. Generates deterministic transaction IDs
5. Links inter-account transfers
6. Writes to `data/accounts/<ACCOUNT_ID>.csv`

**Progress output:**
```
Processing: 2025-11-16-checking.csv
  Matched to account: CHECKING
  Found 156 transactions

Processing: 2025-11-16-visa.csv
  Matched to account: CREDIT_CARD
  Found 89 transactions

✓ Import complete
  Total transactions: 245
  Accounts updated: 2
```

## Step 4: Migrate to Event Store

Convert the imported data to event-sourced format:

```bash
# Preview migration
finance backfill-events

# Execute with validation
finance backfill-events --write
```

**What happens:**
1. Generates `TransactionImported` events for each transaction
2. Generates `TransactionCategorized` events for any pre-categorized transactions
3. Generates `BudgetCreated` events from `categories.yml`
4. Validates that projections match original data
5. Reports statistics

**Expected output:**
```
Event Sourcing Migration - Phase 7
Backfilling events from existing data

Step 1: Backfilling transaction events
  Processing ledgers...

Step 2: Backfilling budget events
  Housing: $2000.0/monthly
  Transportation: $500.0/monthly
  ...

Migration Summary
TransactionImported events: 245
TransactionCategorized events: 0
BudgetCreated events: 7
Total events: 252

✓ Events successfully written to event store
Event store: data/events.db

Step 3: Validating projections
  ✓ Transaction count matches: 245
  ✓ Budget count matches: 7
  ✓ Sample transaction validation passed

✓ All validations passed
```

!!! note "One-Time Operation"
    Backfill is typically run once during initial setup. Future imports automatically generate events.

## Step 5: Verify Data

### List Accounts

```bash
finance accounts
```

Should show all your configured accounts with transaction counts.

### View Recent Transactions

```bash
# View last 20 transactions
finance ytd --account CHECKING --limit 20

# View specific year
finance ytd --account CREDIT_CARD --year 2025

# All transactions (no limit)
finance ytd --account CHECKING
```

### Check for Duplicates

Transfer linking should have automatically identified inter-account transfers:

```bash
# Look for "LINKED_TRANSFER" in metadata
finance ytd --account CHECKING | grep -i transfer
```

### Review Uncategorized Transactions

```bash
# All uncategorized
finance uncategorized

# By account
finance uncategorized --account CHECKING

# Only large amounts
finance uncategorized --min-amount 100
```

Most transactions will be uncategorized initially — that's normal! Categorization happens in the next workflow.

## Step 6: (Optional) Set Up Local LLM

For duplicate detection features, set up Ollama:

### Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai
```

### Pull a Model

```bash
# Recommended models (choose one)
ollama pull qwen3:30b       # Best performance (recommended)
ollama pull qwen3:8b        # Smaller, good balance
ollama pull llama3.2:3b     # Smallest, fastest

# Verify
ollama list
```

### Test Duplicate Detection

Next time you import, Finance will automatically use the LLM to suggest duplicates:

```bash
finance ingest --write
```

If duplicates are found, you'll see an interactive prompt:

```
Potential duplicate:
1) [2025-10-15] TRANSIT FARE/REF1234ABCD Anytown     -10.31
2) [2025-10-15] TRANSIT FARE/REF1234ABCD Anytown ON  -10.31

Keep transaction (1), (2), or (N)ot duplicates? [1]:
```

Your choices are recorded and the system learns your preferences over time.

## Next Steps

Now that your data is imported, you can:

1. **[Categorize transactions](budget-tracking.md)** - Organize spending into categories
2. **[Set up budget tracking](budget-tracking.md)** - Monitor spending against budgets
3. **[Perform monthly review](monthly-review.md)** - Regular financial check-in workflow

## Troubleshooting

### CSV Files Not Matched

**Problem**: `finance ingest` shows "no matching account" for your CSV

**Solution**: Update `source_patterns` in `config/accounts.yml`:

```yaml
accounts:
  - account_id: MY_BANK
    source_patterns:
      - "*my*bank*.csv"      # Add wildcards to match your filenames
      - "*mybank*.csv"
      - "*MB*.csv"
```

### Transaction Count Seems Wrong

**Problem**: Import shows fewer transactions than expected

**Possible causes:**
- CSV has header rows that were skipped (correct behavior)
- Date filter was applied during bank export
- Some transactions are pending (not yet in export)

**Check:**
```bash
# Count lines in CSV (subtract 1 for header)
wc -l ingest/your-file.csv

# View first few transactions
finance ytd --account YOUR_ACCOUNT --limit 10
```

### Import Fails with Parse Error

**Problem**: Error like "Could not parse date" or "Invalid amount format"

**Solution**: Add `import_hints` to account in `config/accounts.yml`:

```yaml
accounts:
  - account_id: MY_BANK
    source_patterns:
      - "*mybank*.csv"
    import_hints:
      header_row: 0              # First row (0-indexed)
      date_format: "%m/%d/%Y"    # MM/DD/YYYY format
      # or "%Y-%m-%d" for YYYY-MM-DD
      # or "%d/%m/%Y" for DD/MM/YYYY
```

### Validation Failed After Backfill

**Problem**: `finance backfill-events --write` reports validation errors

**Solution**:
1. Check the specific validation error message
2. Most common: amount formatting differences (strings vs floats)
3. Re-run backfill (it's idempotent - safe to repeat)
4. If errors persist, check CSV data for unusual characters

### Ollama Model Not Found

**Problem**: Duplicate detection fails with "model not found"

**Solution**:
```bash
# List available models
ollama list

# Pull recommended model
ollama pull qwen3:30b

# Or configure different model in code
# (see developer documentation)
```

## Tips for Success

### Account IDs

✅ **Good:**
- `MYBANK_CHQ` (bank + account type)
- `BANK2_VISA` (bank + card type)
- `CHECKING_JOINT` (type + ownership)

❌ **Bad:**
- `Account1` (not descriptive)
- `My Bank Checking Account` (too long, spaces)
- `12345678` (not memorable)

### Category Budgets

Start conservative:
- Track spending for 2-3 months first
- Set budgets based on actual spending
- Adjust monthly as patterns emerge
- Don't feel obligated to budget every category

### Import Frequency

Recommended:
- **Weekly**: If you want tight budget monitoring
- **Monthly**: Most common, good balance
- **Quarterly**: Minimum for useful tracking

### Data Organization

Keep it clean:
- Use `.gitignore` to exclude `ingest/` and `data/` from version control
- Create backups before major operations
- Archive old CSVs after successful import

## What You've Accomplished

After completing this workflow, you have:

✅ Configured accounts and categories
✅ Imported historical transaction data
✅ Converted to event-sourced architecture
✅ Verified data integrity
✅ (Optional) Set up local LLM for duplicate detection

You're now ready to start categorizing transactions and tracking your budget!

**Next:** [Budget Tracking Workflow](budget-tracking.md)
