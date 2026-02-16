# Monthly Review Workflow

This guide provides a systematic approach for reviewing your finances each month. This workflow takes about 15-30 minutes and helps you stay on top of spending, categorization, and budget goals.

## Overview

The monthly review workflow consists of:

1. **Import new transactions** - Load the latest bank data
2. **Categorize spending** - Assign categories to new transactions
3. **Review budget status** - Check spending against budgets
4. **Analyze patterns** - Identify trends and outliers
5. **Document decisions** - Add notes to significant transactions
6. **Adjust as needed** - Update budgets or categories based on learnings

## Prerequisites

- ✅ Finance installed and configured
- ✅ Initial setup completed ([Initial Setup Workflow](initial-setup.md))
- ✅ Virtual environment activated

## Step 1: Import New Transactions

### Export New Bank Data

For each account:

1. Log in to your bank's website
2. Navigate to transaction history
3. Export transactions **since your last import**:
   - If you imported on October 16, export October 16 - November 16
   - Most banks let you filter by date range
4. Save with current date in filename:
   - `2025-11-16-checking.csv`
   - `2025-11-16-credit-card.csv`

!!! tip "Date Range Tip"
    Slightly overlapping date ranges are fine — Finance's deterministic transaction IDs prevent duplicates.

### Place in Ingest Directory

```bash
# Move new CSVs to ingest (overwrites old files with same name)
mv ~/Downloads/*checking*.csv ingest/
mv ~/Downloads/*credit*.csv ingest/
```

### Import

```bash
# Preview
finance ingest

# Execute
finance ingest --write
```

**Check the output:**
- Transaction counts should match your bank exports
- No parsing errors
- Transfer links detected automatically

### Review Recent Transactions

```bash
# Quick check of latest imports
finance ytd --account CHECKING --limit 30
finance ytd --account CREDIT_CARD --limit 30
```

Look for:
- ✅ All expected transactions present
- ✅ Amounts match bank statements
- ✅ Inter-account transfers linked
- ❌ Duplicate entries (shouldn't happen with deterministic IDs)

## Step 2: Categorize New Transactions

### Check Uncategorized Count

```bash
# How many need categorization?
finance uncategorized --year 2025 --month 11
```

If count is high (>50), prioritize by amount.

### Categorize by Pattern

Start with recurring expenses you've already identified:

```bash
# Subscriptions
finance categorize --desc-prefix "SPOTIFY" --category "Entertainment:Streaming" --yes --write
finance categorize --desc-prefix "NETFLIX" --category "Entertainment:Streaming" --yes --write
finance categorize --desc-prefix "AMAZON PRIME" --category "Entertainment:Streaming" --yes --write

# Utilities (use regex for complex patterns)
finance categorize --pattern "Payment.*EXAMPLE UTILITY" --category "Housing:Utilities" --yes --write
finance categorize --pattern "Payment.*OTHER UTILITY" --category "Housing:Utilities" --yes --write

# Transit
finance categorize --desc-prefix "PRESTO" --category "Transportation:Transit" --yes --write
finance categorize --desc-prefix "UBER" --category "Transportation:Rideshare" --yes --write

# Groceries (common stores)
finance categorize --desc-prefix "LOBLAWS" --category "Groceries" --yes --write
finance categorize --desc-prefix "SOBEYS" --category "Groceries" --yes --write
finance categorize --desc-prefix "METRO" --category "Groceries" --yes --write

# Banking fees
finance categorize --description "Monthly Fee" --category "Banking:Fees" --yes --write
finance categorize --desc-prefix "NSF FEE" --category "Banking:Fees" --yes --write
```

!!! tip "Build a Script"
    Save your common categorization commands in a shell script (`scripts/categorize-common.sh`) for quick monthly execution.

### Review Large Uncategorized

Focus on significant transactions:

```bash
# Show only large amounts
finance uncategorized --min-amount 100 --year 2025 --month 11
```

Categorize these individually:

```bash
# 1. View the transaction details
finance ytd --account CHECKING --limit 50

# 2. Categorize by transaction ID
finance categorize --account CHECKING --txid a1b2c3d4 --category "Healthcare:Dental" --write
```

### Handle Edge Cases

Some transactions need special attention:

```bash
# Split transactions (can't be handled automatically yet)
# Add note explaining it's split, categorize to dominant category
finance note --account CHECKING --txid abc123 --note "Split: $200 groceries, $50 household" --write
finance categorize --account CHECKING --txid abc123 --category "Groceries" --write

# One-time expenses
finance categorize --account CREDIT_CARD --txid def456 --category "Healthcare:Dental" --write
finance note --account CREDIT_CARD --txid def456 --note "Root canal" --write

# Reimbursable expenses
finance categorize --account CREDIT_CARD --txid ghi789 --category "Work:Reimbursable" --write
finance note --account CREDIT_CARD --txid ghi789 --note "Client lunch - reimbursed Nov 20" --write
```

### Verify Categorization Progress

```bash
# Should be much smaller now
finance uncategorized --year 2025 --month 11

# If still too many, continue with patterns or prioritize by amount
```

## Step 3: Review Budget Status

### Current Month Summary

```bash
# Full budget view for current month
finance budget --year 2025 --month 11
```

**Interpret the output:**

| Category | Budgeted | Actual | Remaining | Used % |
|----------|----------|--------|-----------|--------|
| Housing | $2,000.00 | $1,950.00 | $50.00 | <span style="color:green">97.5%</span> |
| Dining Out | $400.00 | $520.00 | <span style="color:red">-$120.00</span> | <span style="color:red">130.0%</span> |
| Entertainment | $200.00 | $185.50 | $14.50 | <span style="color:yellow">92.8%</span> |

**Color coding:**
- 🟢 **Green** (< 90%): Under budget, comfortable
- 🟡 **Yellow** (90-100%): Approaching budget, watch carefully
- 🔴 **Red** (> 100%): Over budget, needs attention

### Investigate Over-Budget Categories

For any red categories:

```bash
# See all transactions in that category
finance ytd --account CREDIT_CARD --year 2025 | grep "Dining Out"

# Or generate a category-specific report
finance budget --category "Dining Out" --year 2025 --month 11
```

**Questions to ask:**
- Was this a one-time event (birthday dinner, visitors)?
- Is this a recurring pattern (eating out more often)?
- Are transactions miscategorized (check descriptions)?
- Is the budget too low for this category?

### Year-to-Date Trends

```bash
# Full year view
finance budget --year 2025
```

Compare month-to-month:
- Which categories consistently over budget?
- Which categories have room to spare?
- Any seasonal patterns (higher utilities in winter)?

### Review Specific Categories

```bash
# Detailed view of one category
finance budget --category "Housing" --year 2025 --month 11
finance budget --category "Transportation" --year 2025 --month 11
```

## Step 4: Analyze Patterns

### Identify Recurring Expenses

Look for patterns in descriptions:

```bash
# View transactions sorted by description
finance ytd --account CREDIT_CARD --year 2025 --month 11 | sort -k3
```

**Look for:**
- New subscription services
- Recurring charges you forgot about
- Amount changes in expected recurring charges

### Find Large One-Time Expenses

```bash
# Transactions over $500
finance ytd --account CHECKING --year 2025 | awk '$4 > 500 || $4 < -500'
```

**Questions:**
- Was this expected (planned purchase)?
- Properly categorized?
- Need a note for context?

### Check for Anomalies

```bash
# Compare categories month-over-month
finance budget --year 2025 --month 10  # Previous month
finance budget --year 2025 --month 11  # Current month
```

**Red flags:**
- Category spending doubled or halved (why?)
- New category with high spending (miscategorization?)
- Expected category has zero spending (missing transactions?)

### Review Inter-Account Transfers

```bash
# Check transfers were properly linked
finance ytd --account CHECKING | grep -i transfer
finance ytd --account CREDIT_CARD | grep -i "payment from"
```

## Step 5: Document Decisions

### Add Notes to Significant Transactions

For large or unusual expenses:

```bash
# Medical expenses
finance note --account CREDIT_CARD --txid abc123 \
  --note "Emergency room visit - covered by insurance" --write

# Major purchases
finance note --account CHECKING --txid def456 \
  --note "New laptop for work" --write

# Gifts
finance note --account CREDIT_CARD --txid ghi789 \
  --note "Birthday gift for spouse" --write

# Irregular bills
finance note --account CHECKING --txid jkl012 \
  --note "Annual car insurance payment" --write
```

### Document Category Decisions

If you made a non-obvious categorization choice:

```bash
# Mixed-purpose expense
finance note --account CREDIT_CARD --txid mno345 \
  --note "Costco run: mostly groceries, some household items" --write

# Work vs personal
finance note --account CREDIT_CARD --txid pqr678 \
  --note "Lunch meeting with client - business expense" --write
```

## Step 6: Adjust Budgets and Categories

### Adjust Over-Budget Categories

If consistently over budget and it's justified:

```bash
# Increase budget
finance category --set-budget "Dining Out" --amount 500 --period monthly --write

# Or reallocate from under-utilized category
finance category --set-budget "Entertainment" --amount 150 --period monthly --write
finance category --set-budget "Dining Out" --amount 450 --period monthly --write
```

### Add New Categories

If you discover a spending pattern:

```bash
# Add category
finance category --add "Pets" --description "Pet care and supplies" --write

# Set budget
finance category --set-budget "Pets" --amount 150 --period monthly --write

# Add subcategories if needed
finance category --add "Pets:Food" --description "Pet food and treats" --write
finance category --add "Pets:Vet" --description "Veterinary care" --write

# Recategorize existing transactions
finance recategorize --from "Uncategorized" --to "Pets" --write
```

### Rename or Consolidate Categories

If category structure isn't working:

```bash
# Rename category
finance recategorize --from "Subscriptions" --to "Entertainment:Streaming" --write

# Update config
# Edit config/categories.yml to match new structure
```

### Remove Unused Categories

```bash
# Check for unused categories
finance diagnose-categories

# Remove if truly unused
finance category --remove "Old Category" --write
```

## Step 7: Generate Report (Optional)

### Create Monthly Report File

```bash
# Create reports directory if needed
mkdir -p reports

# Generate markdown report
finance budget --year 2025 --month 11 > reports/budget_2025_11.md

# Or with custom formatting
{
  echo "# Budget Report - November 2025"
  echo
  echo "Generated: $(date)"
  echo
  finance budget --year 2025 --month 11
  echo
  echo "## Uncategorized Transactions"
  echo
  finance uncategorized --year 2025 --month 11 --limit 20
} > reports/budget_2025_11.md
```

### Version Control (Optional)

If you track reports in git:

```bash
git add reports/budget_2025_11.md
git commit -m "Monthly budget report - November 2025"
```

!!! warning "Privacy Note"
    Don't commit reports to public repositories — they contain your financial data!

## Complete Monthly Checklist

Print or save this checklist for your monthly reviews:

- [ ] Export new CSVs from all bank accounts
- [ ] Run `finance ingest --write`
- [ ] Verify transaction counts match bank statements
- [ ] Categorize recurring subscriptions and utilities
- [ ] Categorize large transactions (>$100)
- [ ] Review and categorize remaining uncategorized
- [ ] Run `finance budget` for current month
- [ ] Investigate any over-budget categories
- [ ] Add notes to significant or unusual transactions
- [ ] Adjust budgets if needed
- [ ] Add/remove categories based on spending patterns
- [ ] Generate monthly report (optional)
- [ ] Back up `data/` directory

## Time-Saving Tips

### Create Categorization Scripts

Save common categorization commands in shell scripts:

```bash
# scripts/categorize-monthly.sh
#!/bin/bash
set -e

echo "Categorizing subscriptions..."
finance categorize --desc-prefix "SPOTIFY" --category "Entertainment:Streaming" --yes --write
finance categorize --desc-prefix "NETFLIX" --category "Entertainment:Streaming" --yes --write

echo "Categorizing utilities..."
finance categorize --pattern "Payment.*HYDRO" --category "Housing:Utilities" --yes --write

echo "Categorizing transit..."
finance categorize --desc-prefix "PRESTO" --category "Transportation:Transit" --yes --write

echo "Done!"
```

Run monthly:

```bash
bash scripts/categorize-monthly.sh
```

### Use Shell Aliases

Add to `~/.zshrc` or `~/.bashrc`:

```bash
# Finance shortcuts
alias fin='finance'
alias fin-import='cd ~/finance && finance ingest --write'
alias fin-uncategorized='finance uncategorized --year $(date +%Y) --month $(date +%m)'
alias fin-budget='finance budget --year $(date +%Y) --month $(date +%m)'
```

### Set Calendar Reminders

- **1st of month**: Monthly review day
- **15th of month**: Mid-month check-in (optional)
- **Last day of month**: Quick preview of next month

## Troubleshooting

### Too Many Uncategorized Transactions

**Problem**: Hundreds of uncategorized transactions

**Solution**:
1. Focus on recurring patterns first (batch categorize)
2. Set minimum amount threshold: `finance uncategorized --min-amount 50`
3. Leave small, one-time expenses uncategorized (they don't affect budget tracking much)
4. Schedule extra time for first few months — it gets faster

### Budget Always Over in Same Category

**Problem**: "Dining Out" always 150% of budget

**Solutions**:
1. **Increase budget** to match actual spending
2. **Change behavior** to match budget (meal prep, cook more)
3. **Reallocate** from under-utilized categories
4. **Split category**: Separate "Restaurants" from "Coffee" to track differently

### Forgot to Import for Several Months

**Problem**: Last import was 3 months ago

**Solution**:
1. Export CSVs for full 3-month range from bank
2. Import all at once: `finance ingest --write`
3. Batch categorize recurring patterns
4. Focus on large amounts for individual categorization
5. Don't stress about perfect categorization for old data

### Spending Patterns Changed

**Problem**: Working from home changed transportation spending

**Solution**:
1. Adjust transportation budget down
2. May need to adjust groceries up (eating at home more)
3. Update after 2-3 months of new pattern
4. Re-evaluate budgets quarterly

## Success Metrics

After a few months of monthly reviews, you should see:

✅ **Faster categorization** (< 10 minutes per month)
✅ **More accurate budgets** (most categories within 10% of budget)
✅ **Fewer surprises** (no unexpected large expenses)
✅ **Better awareness** (know where your money goes)
✅ **Improved ML accuracy** (if using duplicate detection)

## Next Steps

- **Advanced**: Set up [Budget Tracking workflow](budget-tracking.md) with custom categories
- **Automate**: Create shell scripts for your common operations
- **Analyze**: Use event store time-travel queries to analyze historical patterns
- **Learn**: Check `finance prompt-stats` to see how duplicate detection is learning

## Related Workflows

- [Initial Setup](initial-setup.md) - First-time configuration
- [Budget Tracking](budget-tracking.md) - Detailed budget management
- [CLI Guide](../cli/index.md) - Complete command reference
