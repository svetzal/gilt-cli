# Budgeting System

The budgeting system allows users to track spending against budgets organized by categories.

## Overview

The budgeting feature provides:

- **Category management**: Hierarchical categories with subcategories
- **Budget tracking**: Set monthly or yearly budget amounts
- **Spending analysis**: Track actual spending vs budgets
- **Visual indicators**: Color-coded status (green/yellow/red)
- **Automatic prorating**: Convert between monthly and yearly budgets

## Architecture

### Components

```
┌──────────────────────────────────────┐
│  User Interface (CLI/GUI)            │
│  - budget command                    │
│  - categories view                   │
│  - budget view                       │
└──────────────────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│  Services                            │
│  - CategoryService                   │
│  - BudgetService                     │
└──────────────────────────────────────┘
           ↓
┌──────────────────────────────────────┐
│  Data Layer                          │
│  - categories.yml                    │
│  - ledger CSVs                       │
└──────────────────────────────────────┘
```

### Data Flow

**Budget Setup**:
1. User defines categories in `config/categories.yml`
2. Sets budget amounts and periods (monthly/yearly)
3. CategoryService loads and validates configuration

**Transaction Categorization**:
1. User categorizes transactions (via CLI or GUI)
2. Category/subcategory written to ledger CSV
3. Transactions now associated with categories

**Budget Calculation**:
1. BudgetService loads categories with budgets
2. Loads all transactions from ledger files
3. Filters by date range and category
4. Aggregates spending by category
5. Prorates budgets for reporting period
6. Calculates remaining budget and percentage

## Category Configuration

### Schema

Categories are defined in `config/categories.yml`:

```yaml
categories:
  - name: "Housing"
    description: "Housing and utilities"
    budget:
      amount: 2500.00
      period: monthly
    subcategories:
      - name: "Rent"
        description: "Monthly rent payments"
      - name: "Utilities"
        description: "Electric, gas, water, internet"
      - name: "Maintenance"
        description: "Repairs and upkeep"

  - name: "Transportation"
    description: "Vehicle and transit expenses"
    budget:
      amount: 800.00
      period: monthly
    subcategories:
      - name: "Fuel"
      - name: "Transit"
      - name: "Maintenance"
      - name: "Insurance"

  - name: "Dining Out"
    description: "Restaurants and takeout"
    budget:
      amount: 400.00
      period: monthly
```

### Fields

**Category**:
- `name`: Category name (required, unique)
- `description`: Human-readable description
- `budget`: Optional budget configuration
  - `amount`: Budget amount (float)
  - `period`: `monthly` or `yearly`
- `subcategories`: List of subcategories
- `tax_deductible`: Boolean flag for tax purposes (optional)

**Subcategory**:
- `name`: Subcategory name (required)
- `description`: Optional description
- Note: Budgets only on main categories, not subcategories

### Validation

The `Category` Pydantic model validates:
- Names are non-empty
- Budget amounts are positive
- Periods are valid enum values
- No duplicate subcategory names
- Subcategory references are valid

## Transaction Categorization

### Ledger Schema

Transactions in ledger CSV files have category fields:

| Column | Type | Description |
|--------|------|-------------|
| `category` | string | Main category name |
| `subcategory` | string | Subcategory name (optional) |

### Syntax

Three equivalent ways to specify category:

```bash
# Separate flags
--category "Housing" --subcategory "Utilities"

# Colon syntax
--category "Housing:Utilities"

# Category only
--category "Housing"
```

### Categorization Commands

**CLI**:
```bash
# Single transaction
gilt categorize --account MYBANK_CHQ --txid abc123 \
  --category "Housing:Utilities" --write

# Batch by description
gilt categorize --desc-prefix "EXAMPLE UTILITY" \
  --category "Housing:Utilities" --yes --write

# Batch by pattern
gilt categorize --pattern "PAYMENT.*UTILITY" \
  --category "Housing:Utilities" --yes --write
```

**GUI**:
1. Right-click transaction(s)
2. Select "Categorize..."
3. Choose category and subcategory
4. Preview changes
5. Confirm

### Recategorization

Rename categories across all transactions:

```bash
# CLI
gilt recategorize --from "Old Category" \
  --to "New Category" --write

# With subcategory
gilt recategorize --from "Old:Sub" \
  --to "New:Sub" --write
```

## Budget Calculation

### Aggregation

The `BudgetService` aggregates spending:

```python
def get_spending_by_category(
    year: int,
    month: Optional[int] = None
) -> Dict[Tuple[str, str], float]:
    """Get spending grouped by (category, subcategory)."""
    spending = defaultdict(float)

    # Load all ledger files
    for ledger_file in data_dir.glob("*.csv"):
        transactions = load_ledger_csv(ledger_file)

        # Filter by date
        transactions = filter_by_date(transactions, year, month)

        # Aggregate negative amounts (expenses)
        for tx in transactions:
            if tx.amount < 0 and tx.category:
                key = (tx.category, tx.subcategory or "")
                spending[key] += abs(tx.amount)

    return dict(spending)
```

### Budget Proration

Budgets are automatically prorated for the reporting period:

**Monthly Report**:
- Monthly budget → use as-is
- Yearly budget → divide by 12

**Yearly Report**:
- Yearly budget → use as-is
- Monthly budget → multiply by 12

**Implementation**:
```python
def prorate_budget(
    amount: float,
    budget_period: BudgetPeriod,
    report_period: BudgetPeriod
) -> float:
    """Prorate budget amount for reporting period."""
    if budget_period == report_period:
        return amount

    if budget_period == BudgetPeriod.MONTHLY:
        if report_period == BudgetPeriod.YEARLY:
            return amount * 12
    elif budget_period == BudgetPeriod.YEARLY:
        if report_period == BudgetPeriod.MONTHLY:
            return amount / 12

    return amount
```

### Budget Status

Calculate budget status with percentage:

```python
def calculate_budget_status(
    budgeted: float,
    actual: float
) -> BudgetStatus:
    """Calculate budget status and percentage."""
    remaining = budgeted - actual
    if budgeted > 0:
        percent = (actual / budgeted) * 100
    else:
        percent = 0

    # Color coding
    if percent > 100:
        status = "over"    # Red
    elif percent > 90:
        status = "warning" # Yellow
    else:
        status = "good"    # Green

    return BudgetStatus(
        remaining=remaining,
        percent=percent,
        status=status
    )
```

## CLI Commands

### List Categories

```bash
gilt categories

# Output:
┌─────────────┬─────────────┬──────────────────┬─────────┬────────┐
│ Category    │ Subcategory │ Description      │ Budget  │ Count  │
├─────────────┼─────────────┼──────────────────┼─────────┼────────┤
│ Housing     │             │ Housing expenses │ $2,500  │ 145    │
│             │ Rent        │ Monthly rent     │         │ 45     │
│             │ Utilities   │ Electric, gas... │         │ 100    │
│ Transport   │             │ Vehicle expenses │ $800    │ 87     │
└─────────────┴─────────────┴──────────────────┴─────────┴────────┘
```

### Manage Categories

```bash
# Add category
gilt category --add "Housing" \
  --description "Housing expenses" \
  --write

# Add subcategory
gilt category --add "Housing:Utilities" \
  --description "Electric, gas, water" \
  --write

# Set budget
gilt category --set-budget "Housing" \
  --amount 2500 --period monthly --write

# Remove category
gilt category --remove "Old Category" --write
```

### Find Uncategorized

```bash
gilt uncategorized

# Filter by account
gilt uncategorized --account MYBANK_CHQ

# Filter by year
gilt uncategorized --year 2025

# Filter by amount
gilt uncategorized --min-amount 100
```

### Budget Report

```bash
# Current month
gilt budget

# Specific month
gilt budget --year 2025 --month 10

# Whole year
gilt budget --year 2025

# Single category
gilt budget --category "Dining Out" --year 2025

# Output:
┌─────────────┬──────────┬──────────┬───────────┬──────┐
│ Category    │ Budget   │ Actual   │ Remaining │ %    │
├─────────────┼──────────┼──────────┼───────────┼──────┤
│ Housing     │ $2,500   │ $2,125   │ $375      │ 85%  │
│ Transport   │ $800     │ $960     │ -$160     │ 120% │ (red)
│ Dining Out  │ $400     │ $260     │ $140      │ 65%  │
└─────────────┴──────────┴──────────┴───────────┴──────┘

Total: $3,700 budgeted, $3,345 actual, $355 remaining (90.4%)
⚠ 1 category over budget
```

### Diagnose Categories

Find categories in transactions that aren't defined in config:

```bash
gilt diagnose-categories

# Output if issues found:
❌ Found orphaned categories:

┌─────────────┬──────────┬───────┐
│ Category    │ Subcat   │ Count │
├─────────────┼──────────┼───────┤
│ Transpor... │          │ 12    │ (likely typo of "Transportation")
│ Entertainment │ Musci  │ 5     │ (likely typo of "Music")
└─────────────┴──────────┴───────┘

Suggested actions:
1. Add missing categories to config/categories.yml
2. Fix typos using: gilt recategorize --from "..." --to "..."
```

## GUI Views

### Categories View

Manage categories with tree view and detail panel:

**Layout**:
```
┌────────────────────────────────────────────────┐
│ Categories                                     │
├────────────────────────────────────────────────┤
│ [Add Category] [Add Subcategory] [Set Budget] │
│ [Remove] [Reload]                              │
├────────────────────────────────────────────────┤
│ Category      Subcat   Description   Budget    │
│ Housing                Housing...     $2,500   │
│   Rent                 Monthly...              │
│   Utilities            Electric...              │
│ Transport              Vehicle...     $800     │
└────────────────────────────────────────────────┘
```

**Features**:
- Tree view with expandable categories
- Bold/highlighted main categories
- Indented subcategories
- Add/edit/remove operations
- Set budget dialog
- Immediate save to YAML

### Budget View

Track spending vs budgets with visual indicators:

**Layout**:
```
┌────────────────────────────────────────────────┐
│ Budget Tracking                                │
├────────────────────────────────────────────────┤
│ Year: [2025 ▼] Month: [All ▼] [Refresh]       │
├────────────────────────────────────────────────┤
│ Category    Budget    Actual   Remaining   %   │
│ Housing     $2,500    $2,125   $375       85%  │ (green)
│   Rent                $1,800                    │
│   Utilities           $325                      │
│ Transport   $800      $960     -$160      120% │ (red)
└────────────────────────────────────────────────┘
Total: $3,300 budgeted | $3,085 actual | $215 remaining
```

**Features**:
- Color-coded percentages (green/yellow/red)
- Over-budget highlighted in red and bold
- Period selector (year and month)
- Summary statistics
- Resizable columns
- F5 to refresh

### Dashboard

Overview with budget summary card:

**Budget Status Card**:
```
┌──────────────────┐
│ Budget Status    │
│                  │
│  93.5%           │ (color-coded)
│  $215 remaining  │
└──────────────────┘
```

Quick actions:
- View Budget → Navigate to Budget view
- View Transactions → Navigate to Transactions view
- Manage Categories → Navigate to Categories view

## Best Practices

### Category Organization

**Recommended structure**:
- 5-10 main categories
- 2-5 subcategories per category
- Clear, descriptive names
- Avoid deep nesting (max 2 levels)

**Common categories**:
- Housing (Rent, Utilities, Maintenance)
- Transportation (Fuel, Transit, Insurance)
- Food (Groceries, Dining Out)
- Entertainment (Movies, Music, Books)
- Health (Medical, Dental, Pharmacy)
- Shopping (Clothing, Electronics, Household)
- Business (Supplies, Services, Travel)

### Budget Setting

**Tips**:
- Start with broad estimates
- Adjust based on actual spending
- Use monthly budgets for recurring expenses
- Use yearly budgets for irregular expenses
- Leave some buffer (don't budget 100%)

**Review cycle**:
1. Set initial budgets
2. Track for 1-2 months
3. Review actual vs budget
4. Adjust budgets
5. Repeat monthly

### Categorization Workflow

**Efficient categorization**:
1. Find uncategorized: `gilt uncategorized`
2. Batch categorize recurring expenses first
3. Categorize one-off transactions individually
4. Review and adjust as needed

**Batch categorization examples**:
```bash
# Recurring subscriptions
gilt categorize --desc-prefix "SPOTIFY" \
  --category "Entertainment:Music" --yes --write

gilt categorize --desc-prefix "NETFLIX" \
  --category "Entertainment:Video" --yes --write

# Utilities
gilt categorize --pattern "EXAMPLE UTILITY|OTHER UTILITY" \
  --category "Housing:Utilities" --yes --write

# Transit
gilt categorize --desc-prefix "COMPASS CARD" \
  --category "Transportation:Transit" --yes --write
```

## Testing

### Unit Tests

Test budget calculations:
```python
def test_prorate_monthly_to_yearly():
    """Monthly budget * 12 = yearly."""
    amount = prorate_budget(
        500.0,
        BudgetPeriod.MONTHLY,
        BudgetPeriod.YEARLY
    )
    assert amount == 6000.0

def test_budget_status_over():
    """Over 100% should be 'over' status."""
    status = calculate_budget_status(1000.0, 1200.0)
    assert status.status == "over"
    assert status.percent == 120.0
    assert status.remaining == -200.0
```

### Integration Tests

Test full workflow:
```python
def test_categorize_and_budget_report():
    """Categorize transactions, then generate budget report."""
    # Import transactions
    import_service.import_file("test.csv", write=True)

    # Categorize
    categorize_service.categorize(
        desc_prefix="GROCERY",
        category="Food:Groceries",
        write=True
    )

    # Generate budget report
    summary = budget_service.get_budget_summary(2025, 10)

    # Verify spending tracked
    food_budget = summary.find_category("Food")
    assert food_budget.actual > 0
```

## Related Documents

- [System Design](../architecture/system-design.md) - Overall architecture
- [Data Model](../architecture/data-model.md) - Schema details
- [CLI Guide](../../user/cli/budgeting.md) - User guide for budgeting commands
- [Phase 4 Summary](../history/phase4-summary.md) - Budget feature implementation
