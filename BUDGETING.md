# Budgeting Capabilities — Design & Implementation Plan

## Overview

This document outlines the budgeting features for tracking, categorizing, and reporting on transactions across accounts. The design leverages the existing `category` and `subcategory` columns in the ledger schema and follows the project's flat command structure conventions.

## Design Principles

1. **Leverages existing schema**: Uses the ledger's existing `category` and `subcategory` fields
2. **Follows project conventions**: Dry-run defaults with `--write` flag, local-only operations
3. **Flat command structure**: Consistent with existing commands (`ingest`, `note`, `ytd`, `accounts`)
4. **Batch operations**: Supports both single-transaction and batch categorization
5. **Config-driven categories**: Categories defined in `config/categories.yml` for consistency with `config/accounts.yml`

---

## Command Structure

The budgeting feature uses a flat command structure with clear verbs:
- `finance categories` — list all categories
- `finance category` — add/remove/manage categories
- `finance categorize` — assign categories to transactions
- `finance uncategorized` — find unassigned transactions
- `finance budget` — summary of spending by category

---

## Category Storage

Categories are stored in `config/categories.yml` with optional metadata (description, budget amounts, tax-deductible flag). This approach:
- Allows pre-defining categories before use
- Supports metadata (budget limits, descriptions, tax flags)
- Enables version control of category definitions
- Provides validation during categorization
- Maintains consistency with `config/accounts.yml` pattern

---

## Subcategory Support

The design supports hierarchical categories with optional subcategories using three equivalent syntaxes:
```
--category "Housing"
--category "Housing" --subcategory "Utilities"
--category "Housing:Utilities"  # shorthand syntax
```

---

## Command Design

### 1. List Categories
```bash
finance categories [--config config/categories.yml]
```
**Purpose**: Display all defined categories (from config) with descriptions and usage counts.

**Output**: Rich table showing category name, description, transaction count, total amount.

---

### 2. Manage Categories
```bash
# Add a new category
finance category --add "Housing" --description "Housing and utilities" [--write]

# Add with subcategory
finance category --add "Housing:Utilities" --description "Electric, gas, water" [--write]

# Remove a category (requires confirmation if transactions are categorized)
finance category --remove "Housing:Utilities" [--write]

# Set budget amount for a category
finance category --set-budget "Dining Out" --amount 500 --period monthly [--write]
```

**Safety**: Dry-run by default. Removing a category with transactions requires `--force` or interactive confirmation.

---

### 3. Categorize Transactions
```bash
# Single transaction
finance categorize --account RBC_CHQ --txid a1b2c3d4 --category "Housing" [--subcategory "Utilities"] [--write]

# Batch by description prefix
finance categorize --account RBC_CHQ --desc-prefix "HYDRO ONE" --category "Housing:Utilities" [--yes] [--write]

# Batch by exact description
finance categorize --account RBC_MC --description "SPOTIFY" --category "Entertainment:Music" [--write]

# Batch by description and amount
finance categorize --account RBC_CHQ --description "Monthly Fee" --amount -12.95 --category "Banking:Fees" [--write]

# Multi-account (all accounts in data/accounts/)
finance categorize --desc-prefix "AMAZON" --category "Shopping:Online" [--yes] [--write]
```

**Safety**: 
- Dry-run by default
- Shows all matching transactions before categorizing
- Warns if re-categorizing (changing existing category)
- Requires `--yes` for batch operations with multiple matches

---

### 4. Find Uncategorized Transactions
```bash
# Single account
finance uncategorized --account RBC_CHQ [--year 2025] [--limit 50]

# All accounts
finance uncategorized [--year 2025]

# With amount filtering
finance uncategorized --account RBC_CHQ --min-amount 100
```

**Output**: Rich table showing transactions without categories, sorted by description then date.

**Purpose**: Help identify which transactions still need categorization.

---

### 5. Budget Summary (New)
```bash
# Current month summary
finance budget [--year 2025] [--month 10]

# Year-to-date summary
finance budget --year 2025

# Specific category detail
finance budget --category "Dining Out" --year 2025
```

**Output**: 
- Summary table with category, budgeted amount (if set), actual spending, difference
- Highlights over-budget categories
- Shows percentage of budget used

---

## Storage Design

### config/categories.yml
```yaml
categories:
  - name: "Housing"
    description: "Housing expenses including rent, mortgage, utilities"
    subcategories:
      - name: "Rent"
        description: "Monthly rent payments"
      - name: "Utilities"
        description: "Electric, gas, water, internet"
      - name: "Maintenance"
        description: "Repairs and maintenance"
    budget:
      amount: 2500.00
      period: monthly  # monthly, yearly
    
  - name: "Transportation"
    description: "Vehicle and transit expenses"
    subcategories:
      - name: "Fuel"
      - name: "Maintenance"
      - name: "Insurance"
      - name: "Transit"
    budget:
      amount: 800.00
      period: monthly
    
  - name: "Dining Out"
    description: "Restaurants and takeout"
    budget:
      amount: 400.00
      period: monthly
    tax_deductible: false
    
  - name: "Business:Meals"
    description: "Business meal expenses"
    tax_deductible: true
    
  - name: "Entertainment"
    subcategories:
      - name: "Music"
      - name: "Movies"
      - name: "Books"
```

**Schema validation**: Use Pydantic model (like `Account` in `finance.model.account`).

---

## Implementation Plan

### Phase 1: Foundation (Core Infrastructure)
**Files to create/modify**:

1. **src/finance/model/category.py** (new)
   - `Category` Pydantic model
   - `Subcategory` model
   - `Budget` model
   - Validation logic

2. **src/finance/model/category_io.py** (new)
   - `load_categories_config(path: Path) -> List[Category]`
   - `save_categories_config(path: Path, categories: List[Category])`
   - Error handling for missing/invalid config

3. **config/categories.yml** (new)
   - Initial category definitions (start with common categories)
   - Follow YAML structure above

4. **Tests**: 
   - **src/finance/model/category_spec.py**: Test Category model validation
   - **src/finance/model/category_io_spec.py**: Test YAML loading/saving

**Acceptance criteria**:
- Can load categories from YAML
- Validation catches invalid category definitions
- Subcategories properly nested

---

### Phase 2: Category Management Commands
**Files to create**:

1. **src/finance/cli/command/categories.py** (new)
   - `run(config: Path, data_dir: Path) -> int`
   - Load categories and count usage from ledgers
   - Display rich table with name, description, count, total amount

2. **src/finance/cli/command/category.py** (new)
   - `run(action: str, name: str, ..., write: bool) -> int`
   - Actions: add, remove, set-budget
   - Modify config/categories.yml
   - Dry-run safety

3. **src/finance/cli/app.py** (modify)
   - Add `@app.command() def categories(...)`
   - Add `@app.command() def category(...)`

4. **Tests**:
   - **src/finance/cli/command/categories_spec.py**
   - **src/finance/cli/command/category_spec.py**

**Acceptance criteria**:
- `finance categories` lists all categories with counts
- `finance category --add` creates new categories (dry-run and --write modes)
- `finance category --remove` deletes categories with safety checks

---

### Phase 3: Transaction Categorization
**Files to create/modify**:

1. **src/finance/cli/command/categorize.py** (new)
   - `run(account: Optional[str], txid: Optional[str], description: Optional[str], desc_prefix: Optional[str], amount: Optional[float], category: str, subcategory: Optional[str], assume_yes: bool, data_dir: Path, write: bool) -> int`
   - Similar structure to `note.py` command
   - Support single and batch modes
   - Validate category exists in config
   - Load ledger, update category fields, save back

2. **src/finance/cli/command/util.py** (modify)
   - Add `validate_category(category: str, subcategory: Optional[str], categories: List[Category]) -> bool`
   - Shared utility for category validation

3. **src/finance/cli/app.py** (modify)
   - Add `@app.command() def categorize(...)`

4. **Tests**:
   - **src/finance/cli/command/categorize_spec.py**

**Acceptance criteria**:
- Can categorize single transaction by txid
- Can batch categorize by description prefix
- Validates category exists before applying
- Dry-run shows what would change
- `--write` persists changes to ledger CSV
- Warns when re-categorizing

---

### Phase 4: Uncategorized Transactions View
**Files to create**:

1. **src/finance/cli/command/uncategorized.py** (new)
   - `run(account: Optional[str], year: Optional[int], limit: Optional[int], min_amount: Optional[float], data_dir: Path) -> int`
   - Load ledgers, filter for empty category
   - Display rich table sorted by description, then date
   - Read-only command (no --write)

2. **src/finance/cli/app.py** (modify)
   - Add `@app.command() def uncategorized(...)`

3. **Tests**:
   - **src/finance/cli/command/uncategorized_spec.py**

**Acceptance criteria**:
- Lists all transactions without categories
- Filters by account, year, amount
- Sorted by description then date
- Shows helpful info (txid, date, description, amount) for easy categorization

---

### Phase 5: Budget Reporting
**Files to create**:

1. **src/finance/cli/command/budget.py** (new)
   - `run(year: Optional[int], month: Optional[int], category: Optional[str], data_dir: Path, config: Path) -> int`
   - Load categories with budget info
   - Load ledgers and aggregate by category
   - Display rich table with budget vs actual
   - Highlight over-budget items

2. **src/finance/cli/app.py** (modify)
   - Add `@app.command() def budget(...)`

3. **Tests**:
   - **src/finance/cli/command/budget_spec.py**

**Acceptance criteria**:
- Shows summary by category
- Compares actual vs budgeted amounts
- Filters by year/month/category
- Clearly indicates over/under budget

---

### Phase 6: Integration & Documentation
**Files to modify**:

1. **README.md**
   - Add section on budgeting features
   - Document all new commands with examples
   - Update schema documentation to highlight category/subcategory usage

2. **PATTERNS.md** (if exists, else create)
   - Document category management patterns
   - Best practices for categorization
   - Example category hierarchies

3. **Integration testing**:
   - End-to-end workflow test
   - Ingest → Categorize → Report flow

**Acceptance criteria**:
- Complete user documentation
- Example workflows
- Migration guide for existing users

---

## Migration & Compatibility

### Backward Compatibility
- Existing ledgers with empty category fields remain valid
- No schema changes required (category/subcategory already exist)
- Commands work with or without categories.yml (graceful degradation)

### Migration Path
1. Users continue using existing workflow
2. Create `config/categories.yml` when ready
3. Gradually categorize transactions using `finance categorize`
4. Use `finance uncategorized` to find remaining transactions

---

## Privacy & Safety Considerations

### Privacy (Maintained)
- All operations remain local-only
- No network I/O
- Category definitions are local configuration
- Reports stay on local machine

### Safety (Enhanced)
- Dry-run default for all mutation commands
- Interactive confirmation for destructive operations (removing categories)
- Validation prevents invalid category assignments
- Clear warnings when re-categorizing

---

## Testing Strategy

### Unit Tests
- Model validation (Category, Budget)
- Config loading/saving
- Category validation logic
- Transaction matching logic

### Integration Tests
- Full command workflows
- Multi-account categorization
- Budget calculations
- Edge cases (missing config, invalid categories, empty ledgers)

### Manual Testing Checklist
- [ ] Create categories.yml with sample categories
- [ ] List categories with `finance categories`
- [ ] Categorize single transaction (dry-run and --write)
- [ ] Batch categorize by description prefix
- [ ] View uncategorized transactions
- [ ] Generate budget report
- [ ] Remove category with transactions (verify safety)
- [ ] Verify ledger CSV correctly updated
- [ ] Re-ingest after categorization (verify persistence)

---

## Future Enhancements (Out of Scope)

- **Export to tax software**: Generate CSV/JSON for tax preparation tools
- **Category templates**: Pre-built category sets (US tax, Canadian tax, etc.)
- **Auto-categorization**: ML-based suggestion of categories based on description patterns
- **Multi-currency budgets**: Handle budgets in multiple currencies
- **Rollover budgets**: Track unused budget from previous periods
- **Recurring transaction detection**: Auto-categorize based on learned patterns
- **Split transaction categorization**: Assign different categories to split lines

---

## Summary

This design:
1. **Leverages existing infrastructure**: Uses current category/subcategory fields
2. **Follows project conventions**: Local-only, dry-run defaults, consistent CLI patterns
3. **Provides practical workflows**: From basic categorization to budget reporting
4. **Maintains safety**: Validation, confirmations, clear dry-run previews
5. **Scales gracefully**: Start simple (manual categorization) → advanced (budget reports)

The phased implementation allows incremental development and testing, with each phase delivering standalone value.