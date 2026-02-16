# Budget Tracking Workflow

This guide helps you set up comprehensive budget tracking, monitor spending against goals, and refine your budget over time.

## Overview

Effective budget tracking involves:

1. **Define categories** - Create a category structure that matches your spending
2. **Set budgets** - Assign realistic budget amounts to each category
3. **Categorize transactions** - Consistently label all transactions
4. **Monitor progress** - Regular check-ins on budget vs actual
5. **Refine and adjust** - Iterate based on real spending patterns

## Prerequisites

- ✅ Gilt installed and configured
- ✅ At least 2-3 months of transaction data imported
- ✅ Familiar with [Monthly Review workflow](monthly-review.md)

## Step 1: Analyze Historical Spending

Before setting budgets, understand your actual spending patterns.

### Import 3-6 Months of Data

More data = better understanding:

```bash
# If you haven't already, import several months
# See Initial Setup Workflow for details
gilt ingest --write
```

### Review Current Categories

```bash
# See what categories exist
gilt categories
```

### Categorize Existing Transactions

Before analyzing spending, categorize as much as possible:

```bash
# Batch categorize common patterns
gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Streaming" --yes --write
gilt categorize --desc-prefix "UBER" --category "Transportation:Rideshare" --yes --write
# ... etc (see Monthly Review for more patterns)

# Check progress
gilt uncategorized
```

**Goal**: Get at least 80% of transactions categorized before analyzing.

### Analyze Spending by Category

Look at historical spending without budgets set:

```bash
# Last 3 months individually
gilt budget --year 2025 --month 9
gilt budget --year 2025 --month 10
gilt budget --year 2025 --month 11
```

**Calculate averages:**
- Housing: $1,950 / $2,000 / $1,975 → Average: ~$1,975/month
- Dining Out: $520 / $480 / $550 → Average: ~$517/month
- Transportation: $350 / $380 / $310 → Average: ~$347/month

**Look for patterns:**
- Which categories are consistent?
- Which have high variability?
- Any seasonal trends (winter heating, summer AC)?
- One-time expenses that skew averages?

## Step 2: Define Budget Structure

### Start with Essential Categories

Begin with the basics:

```yaml
# config/categories.yml
categories:
  # Fixed/Essential
  - name: "Housing"
    description: "Rent, mortgage, utilities"
    subcategories:
      - name: "Rent"
      - name: "Utilities"
      - name: "Insurance"
      - name: "Maintenance"

  - name: "Transportation"
    description: "Vehicle and transit"
    subcategories:
      - name: "Fuel"
      - name: "Transit"
      - name: "Parking"
      - name: "Maintenance"

  # Variable/Lifestyle
  - name: "Groceries"
    description: "Food and household items"

  - name: "Dining Out"
    description: "Restaurants and takeout"

  - name: "Healthcare"
    description: "Medical and wellness"
    subcategories:
      - name: "Prescriptions"
      - name: "Dental"
      - name: "Vision"
      - name: "Fitness"

  # Discretionary
  - name: "Entertainment"
    description: "Recreation and leisure"
    subcategories:
      - name: "Streaming"
      - name: "Events"
      - name: "Hobbies"

  - name: "Shopping"
    description: "Clothing, electronics, etc"
    subcategories:
      - name: "Clothing"
      - name: "Electronics"
      - name: "Home"

  # Financial
  - name: "Banking"
    description: "Fees and charges"
    subcategories:
      - name: "Fees"
      - name: "Interest"

  - name: "Savings"
    description: "Transfers to savings"
```

### Add Your Specific Categories

Based on your spending:

```bash
# Work-related (if freelance/contractor)
gilt category --add "Work" --description "Business expenses" --write
gilt category --add "Work:Equipment" --write
gilt category --add "Work:Travel" --write

# Pets
gilt category --add "Pets" --description "Pet care" --write
gilt category --add "Pets:Food" --write
gilt category --add "Pets:Vet" --write

# Education
gilt category --add "Education" --description "Learning and development" --write
gilt category --add "Education:Courses" --write
gilt category --add "Education:Books" --write

# Gifts
gilt category --add "Gifts" --description "Gifts and charitable giving" --write
```

### Review Category Usage

```bash
# See which categories are being used
gilt categories
```

Remove any categories with zero usage that you don't plan to use.

## Step 3: Set Initial Budgets

### Calculate Budget Targets

Use your historical analysis from Step 1:

**Fixed Expenses** (start with actual averages):
- Housing: Historical $1,975 → Budget $2,000 (round up for cushion)
- Transportation: Historical $347 → Budget $350

**Variable Expenses** (start conservative):
- Groceries: Historical $580 → Budget $600 (10% cushion)
- Dining Out: Historical $517 → Budget $500 (trying to reduce)

**Discretionary** (set aspirational goals):
- Entertainment: Historical $220 → Budget $200 (slight reduction)
- Shopping: Historical $380 → Budget $300 (significant reduction goal)

### Set Budgets via CLI

```bash
# Essential expenses
gilt category --set-budget "Housing" --amount 2000 --period monthly --write
gilt category --set-budget "Transportation" --amount 350 --period monthly --write

# Food
gilt category --set-budget "Groceries" --amount 600 --period monthly --write
gilt category --set-budget "Dining Out" --amount 500 --period monthly --write

# Healthcare
gilt category --set-budget "Healthcare" --amount 200 --period monthly --write

# Discretionary
gilt category --set-budget "Entertainment" --amount 200 --period monthly --write
gilt category --set-budget "Shopping" --amount 300 --period monthly --write

# Financial (usually no budget, just tracking)
# Banking fees - track but don't budget
# Savings - track transfers but don't budget as "spending"
```

### Set Budgets via Config File

Alternatively, edit `config/categories.yml` directly:

```yaml
categories:
  - name: "Housing"
    description: "Rent, mortgage, utilities"
    budget:
      amount: 2000.00
      period: monthly
    subcategories:
      - name: "Rent"
      - name: "Utilities"
```

Then reload:

```bash
gilt categories
```

### Annual vs Monthly Budgets

Some expenses are annual:

```bash
# Annual expenses
gilt category --set-budget "Insurance" --amount 1200 --period yearly --write
gilt category --set-budget "Gifts" --amount 2000 --period yearly --write

# Gilt automatically pro-rates when viewing monthly reports
gilt budget --year 2025 --month 11
# Shows Insurance: $100/month (from $1200/year ÷ 12)
```

## Step 4: Track and Monitor

### Daily/Weekly Check-Ins (Optional)

For tight budget monitoring:

```bash
# Quick status of current month
gilt budget --year $(date +%Y) --month $(date +%m)
```

Add to your shell profile for convenience:

```bash
# Add to ~/.zshrc or ~/.bashrc
alias budget-now='gilt budget --year $(date +%Y) --month $(date +%m)'
```

### Weekly Categorization

Don't wait until month-end:

```bash
# Every Sunday, categorize the week
gilt uncategorized --limit 50

# Batch categorize common patterns
bash scripts/categorize-common.sh  # your saved patterns
```

### Mid-Month Review

Check progress halfway through the month:

```bash
# Day 15 check-in
gilt budget --year 2025 --month 11
```

**Questions to ask:**
- Am I on track (roughly 50% spent)?
- Any categories already over?
- Need to adjust behavior for rest of month?

### Month-End Review

Full analysis at month close:

```bash
# Complete view
gilt budget --year 2025 --month 11

# Category details for over-budget items
gilt budget --category "Dining Out" --year 2025 --month 11
```

## Step 5: Analyze and Adjust

### After First Month

Review results:

```bash
gilt budget --year 2025 --month 11
```

**For each category:**

| Status | Action |
|--------|--------|
| 🟢 Under 80% | Consider reducing budget, reallocate funds |
| 🟢 80-90% | Good! Budget is appropriate |
| 🟡 90-100% | Perfect utilization, monitor closely |
| 🔴 100-110% | Minor overage, acceptable for first month |
| 🔴 110%+ | Significant overage, needs attention |

### Common Adjustments

**Budget Too Low** (consistently over):

```bash
# Increase budget if spending is justified
gilt category --set-budget "Groceries" --amount 700 --period monthly --write

# Or reallocate from elsewhere
gilt category --set-budget "Entertainment" --amount 150 --period monthly --write
gilt category --set-budget "Groceries" --amount 700 --period monthly --write
```

**Budget Too High** (consistently under):

```bash
# Reduce and reallocate
gilt category --set-budget "Entertainment" --amount 150 --period monthly --write
gilt category --set-budget "Dining Out" --amount 550 --period monthly --write
```

**Wrong Granularity**:

```bash
# Too broad? Split into subcategories
gilt category --add "Entertainment:Streaming" --write
gilt category --add "Entertainment:Events" --write
gilt category --add "Entertainment:Hobbies" --write

# Set sub-budgets (optional)
gilt category --set-budget "Entertainment:Streaming" --amount 50 --period monthly --write

# Recategorize existing
gilt recategorize --from "Entertainment" --to "Entertainment:Streaming" --write
```

**Category Not Useful**:

```bash
# Consolidate or remove
gilt recategorize --from "OldCategory" --to "NewCategory" --write
gilt category --remove "OldCategory" --write
```

### After 2-3 Months

Look for trends:

```bash
# Compare 3 months
gilt budget --year 2025 --month 9
gilt budget --year 2025 --month 10
gilt budget --year 2025 --month 11
```

**Calculate averages:**
- Which budgets are consistently over/under?
- Any seasonal patterns?
- Life changes affecting spending (new job, moved, etc)?

**Adjust budgets** to reflect reality:

```bash
# Housing consistently at $2,100
gilt category --set-budget "Housing" --amount 2100 --period monthly --write

# Dining out averaging $450 (reduction goal achieved!)
gilt category --set-budget "Dining Out" --amount 450 --period monthly --write
```

## Step 6: Advanced Tracking

### Zero-Based Budgeting

Allocate every dollar:

```bash
# Calculate total monthly income
INCOME=5000

# Allocate to all categories (should sum to $5000)
gilt category --set-budget "Housing" --amount 2000 --period monthly --write
gilt category --set-budget "Savings" --amount 1000 --period monthly --write
gilt category --set-budget "Groceries" --amount 600 --period monthly --write
# ... etc until all $5000 allocated
```

Verify allocation:

```bash
# Sum all budgets
gilt categories | awk '{sum+=$NF} END {print "Total: $" sum}'
```

### Envelope System Simulation

Track "envelopes" via categories:

```bash
# Discretionary spending envelope
gilt category --set-budget "Discretionary" --amount 500 --period monthly --write

# Check remaining in envelope
gilt budget --category "Discretionary" --year 2025 --month 11
```

When envelope is empty, stop spending in that category.

### Sinking Funds

Save for irregular expenses:

```bash
# Annual car insurance = $1,200
# Save $100/month in "Insurance" category
gilt category --set-budget "Insurance" --amount 100 --period monthly --write

# Track as transfers to savings:
gilt categorize --desc-prefix "TRANSFER TO SAVINGS" --category "Savings:Insurance" --write
```

### Budget Rollover (Manual)

If under-spent this month, increase next month's budget:

```bash
# November: Budgeted $400, spent $350, $50 remaining
# December: Set budget to $450 (400 + 50 rollover)
gilt category --set-budget "Dining Out" --amount 450 --period monthly --write
```

## Budget Templates

### Conservative Template

Good for debt payoff or aggressive saving:

```yaml
Housing: $1,800 (36%)        # Keep low with roommates/modest rent
Transportation: $300 (6%)    # Public transit focus
Groceries: $500 (10%)        # Cook at home
Dining Out: $150 (3%)        # Rare treats
Healthcare: $150 (3%)        # Basic coverage
Entertainment: $100 (2%)     # Free/cheap activities
Shopping: $200 (4%)          # Essentials only
Savings: $1,800 (36%)        # Aggressive saving!
Total: $5,000
```

### Balanced Template

Moderate lifestyle with savings:

```yaml
Housing: $2,000 (40%)
Transportation: $400 (8%)
Groceries: $600 (12%)
Dining Out: $400 (8%)
Healthcare: $200 (4%)
Entertainment: $300 (6%)
Shopping: $300 (6%)
Savings: $800 (16%)
Total: $5,000
```

### Lifestyle Template

Higher income, enjoy life now:

```yaml
Housing: $3,000 (30%)
Transportation: $800 (8%)
Groceries: $800 (8%)
Dining Out: $800 (8%)
Healthcare: $300 (3%)
Entertainment: $500 (5%)
Shopping: $800 (8%)
Travel: $1,000 (10%)        # Monthly allocation
Savings: $2,000 (20%)
Total: $10,000
```

## Reporting and Visualization

### Monthly Reports

Generate reports for review:

```bash
# Markdown format
gilt budget --year 2025 --month 11 > reports/2025-11-budget.md

# Add context
{
  echo "# November 2025 Budget Review"
  echo
  echo "## Budget vs Actual"
  gilt budget --year 2025 --month 11
  echo
  echo "## Uncategorized (need attention)"
  gilt uncategorized --year 2025 --month 11 --limit 10
  echo
  echo "## Notes"
  echo "- Higher dining out due to birthday celebrations"
  echo "- Transportation low - worked from home more"
} > reports/2025-11-budget.md
```

### Quarterly Reviews

```bash
# Create quarterly summary
{
  echo "# Q4 2025 Budget Summary"
  echo
  echo "## October"
  gilt budget --year 2025 --month 10
  echo
  echo "## November"
  gilt budget --year 2025 --month 11
  echo
  echo "## December"
  gilt budget --year 2025 --month 12
  echo
  echo "## Q4 Totals"
  gilt budget --year 2025  # Shows year-to-date
} > reports/2025-Q4-budget.md
```

### Year-End Review

```bash
# Annual summary
gilt budget --year 2025 > reports/2025-annual-budget.md
```

## Troubleshooting

### Budgets Always Exceeded

**Problem**: Every category over budget

**Causes:**
- Budgets unrealistically low
- Income insufficient for lifestyle
- Missing major expense categories

**Solutions:**
1. Review actual spending over 3+ months
2. Set budgets based on reality, not wishes
3. If income is the issue, consider:
   - Increasing income (side gig, raise, new job)
   - Reducing expenses (move, cut subscriptions, cook more)
   - Both (dual approach)

### Can't Stick to Discretionary Budgets

**Problem**: Consistently over on dining/entertainment/shopping

**Solutions:**
1. **Increase budget** to match reality (if income allows)
2. **Remove temptation**:
   - Unsubscribe from marketing emails
   - Delete shopping apps
   - Use cash for discretionary spending
3. **Implement waiting period**:
   - Wait 24-48 hours before non-essential purchases
   - Track "wants" vs "needs"
4. **Find free alternatives**:
   - Entertainment: library, parks, free events
   - Dining: meal prep, pack lunches
   - Shopping: borrowing, swapping, secondhand

### Budget Tracking Takes Too Much Time

**Problem**: Spending hours each month on categorization

**Solutions:**
1. **Automate patterns**:
   ```bash
   # Save to scripts/auto-categorize.sh
   gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Streaming" --yes --write
   # ... 20+ common patterns
   ```
2. **Focus on large amounts**:
   ```bash
   # Only categorize >$50
   gilt uncategorized --min-amount 50
   ```
3. **Batch processing**:
   - Do weekly mini-sessions (10 min) vs monthly marathon
4. **Accept imperfection**:
   - 80% categorized is enough for useful insights
   - Small, rare expenses don't need perfect categorization

### Categories Too Complex

**Problem**: 30+ categories, hard to remember what goes where

**Solutions:**
1. **Consolidate**:
   ```bash
   # Too many entertainment sub-categories
   gilt recategorize --from "Entertainment:Concerts" --to "Entertainment:Events" --write
   gilt recategorize --from "Entertainment:Theater" --to "Entertainment:Events" --write
   ```
2. **Rule of thumb**: 10-15 main categories, 2-4 subcategories each
3. **Combine rare categories**:
   ```bash
   gilt recategorize --from "Pet:Toys" --to "Pet:Food" --write
   ```

## Success Criteria

After 3-6 months of budget tracking:

✅ **90%+ transactions categorized**
✅ **Most categories within ±10% of budget**
✅ **Clear understanding of spending patterns**
✅ **Budgets adjusted based on reality, not guesses**
✅ **Monthly review takes < 30 minutes**
✅ **Achieving savings goals**
✅ **No surprise expenses**

## Next Steps

- **Refine**: Continue monthly reviews and adjustments
- **Automate**: Create scripts for common operations
- **Analyze**: Use event sourcing to track budget changes over time
- **Optimize**: Identify areas for spending reduction

## Related Workflows

- [Initial Setup](initial-setup.md) - First-time configuration
- [Monthly Review](monthly-review.md) - Regular financial check-ins
- [CLI Budgeting Guide](../cli/budgeting.md) - Complete command reference
