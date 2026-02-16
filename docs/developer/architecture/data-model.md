# Data Model

This document describes the data structures and schemas used in Gilt.

## Overview

Gilt uses three main data storage formats:

- **CSV files**: Transaction ledgers (one per account)
- **YAML files**: Configuration (accounts, categories)
- **In-memory models**: Pydantic models for validation

## Ledger Schema

Each account has a CSV file in `data/accounts/<ACCOUNT_ID>.csv` with this schema:

### Columns

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `transaction_id` | string | Unique deterministic hash (16 chars) | Yes |
| `date` | date | Transaction date (YYYY-MM-DD) | Yes |
| `description` | string | Bank's transaction description | Yes |
| `amount` | float | Signed amount (negative=debit, positive=credit) | Yes |
| `currency` | string | Currency code (e.g., CAD, USD) | Yes |
| `account_id` | string | Account identifier | Yes |
| `counterparty` | string | Initially same as description | Yes |
| `category` | string | Transaction category | No |
| `subcategory` | string | Transaction subcategory | No |
| `notes` | string | User-added notes | No |
| `source_file` | string | Original CSV filename | Yes |
| `metadata` | json | Additional metadata (e.g., transfers) | No |

### Example Row

```csv
transaction_id,date,description,amount,currency,account_id,counterparty,category,subcategory,notes,source_file,metadata
a1b2c3d4e5f60789,2025-11-16,"GROCERY STORE",-45.67,CAD,MYBANK_CHQ,"GROCERY STORE",Food,Groceries,"Weekly shopping",2025-11-16-mybank-chq.csv,{}
```

### Transaction ID Generation

Transaction IDs are deterministic hashes:

```python
def generate_transaction_id(
    account_id: str,
    date: str,
    amount: float,
    description: str
) -> str:
    """Generate unique, deterministic ID."""
    content = f"{account_id}|{date}|{amount}|{description}"
    hash_bytes = hashlib.sha256(content.encode('utf-8')).digest()
    return hash_bytes.hex()[:16]  # First 16 hex chars
```

**Properties**:
- Same transaction → same ID
- 16 characters (8 bytes)
- Collision-resistant (SHA-256)
- Used for duplicate detection

## Configuration Schemas

### accounts.yml

Account configuration:

```yaml
accounts:
  - account_id: string          # Unique account ID (required)
    description: string          # Human-readable name (required)
    source_patterns:            # Glob patterns for file matching
      - string                  # e.g., "*mybank*chq*.csv"
    import_hints:               # Optional import hints
      header_row: int           # Header row index (default: 0)
      date_format: string       # Date format (default: auto-detect)
```

**Example**:

```yaml
accounts:
  - account_id: MYBANK_CHQ
    description: "MyBank Chequing Account"
    source_patterns:
      - "*mybank*chequing*.csv"
      - "*mybank*chq*.csv"
    import_hints:
      header_row: 0
      date_format: "%m/%d/%Y"

  - account_id: MYBANK_CC
    description: "MyBank Credit Card"
    source_patterns:
      - "*mybank*cc*.csv"
      - "*mybank*creditcard*.csv"
```

### categories.yml

Category hierarchy and budgets:

```yaml
categories:
  - name: string              # Category name (required, unique)
    description: string       # Description (optional)
    budget:                   # Budget configuration (optional)
      amount: float          # Budget amount
      period: monthly|yearly # Budget period
    tax_deductible: boolean  # Tax flag (optional)
    subcategories:           # Subcategory list (optional)
      - name: string         # Subcategory name (required)
        description: string  # Description (optional)
```

**Example**:

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
        description: "Electric, gas, water"
      - name: "Maintenance"

  - name: "Transportation"
    description: "Vehicle and transit"
    budget:
      amount: 800.00
      period: monthly
    subcategories:
      - name: "Fuel"
      - name: "Transit"
      - name: "Insurance"

  - name: "Business:Meals"
    description: "Business meal expenses"
    tax_deductible: true
```

## Pydantic Models

### Account Model

```python
from pydantic import BaseModel
from typing import Optional, List

class ImportHints(BaseModel):
    """Optional import hints for parsing."""
    header_row: int = 0
    date_format: Optional[str] = None

class Account(BaseModel):
    """Account configuration."""
    account_id: str
    description: str
    source_patterns: List[str]
    import_hints: Optional[ImportHints] = None
```

### Category Model

```python
from enum import Enum

class BudgetPeriod(str, Enum):
    """Budget period enum."""
    MONTHLY = "monthly"
    YEARLY = "yearly"

class Budget(BaseModel):
    """Budget configuration."""
    amount: float
    period: BudgetPeriod

class Subcategory(BaseModel):
    """Subcategory definition."""
    name: str
    description: Optional[str] = None

class Category(BaseModel):
    """Category with optional budget."""
    name: str
    description: Optional[str] = None
    budget: Optional[Budget] = None
    tax_deductible: bool = False
    subcategories: List[Subcategory] = []
```

### Transaction Model

```python
from datetime import date

class Transaction(BaseModel):
    """Single transaction."""
    transaction_id: str
    date: date
    description: str
    amount: float
    currency: str
    account_id: str
    counterparty: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    notes: Optional[str] = None
    source_file: str
    metadata: dict = {}
```

### TransactionGroup Model

```python
class TransactionGroup(BaseModel):
    """Group of transactions for an account."""
    account_id: str
    transactions: List[Transaction]

    def filter_by_date(self, year: int, month: Optional[int] = None):
        """Filter transactions by date."""
        pass

    def filter_by_category(self, category: str):
        """Filter transactions by category."""
        pass
```

## Metadata Schema

The `metadata` field in transactions stores additional information as JSON.

### Transfer Metadata

When transactions are linked as transfers:

```json
{
  "transfer": {
    "linked_transaction_id": "abc123...",
    "linked_account_id": "BANK2_BIZ",
    "match_type": "direct|interac",
    "confidence": 1.0
  }
}
```

**Fields**:
- `linked_transaction_id`: ID of the other side of transfer
- `linked_account_id`: Account ID of the other side
- `match_type`: How transfer was detected
  - `direct`: Direct account-to-account transfer
  - `interac`: Interac e-Transfer
- `confidence`: Match confidence (0.0 to 1.0)

### Future Metadata

Extensible for future features:

```json
{
  "split": {
    "original_amount": -100.00,
    "splits": [
      {"category": "Food:Groceries", "amount": -60.00},
      {"category": "Household", "amount": -40.00}
    ]
  },
  "recurring": {
    "frequency": "monthly",
    "expected_amount": -45.00
  }
}
```

## Data Flow

### Import Flow

```
Bank CSV → Parse → Normalize → Generate IDs → Write Ledger CSV
                                              ↓
                                       Detect Transfers
                                              ↓
                                       Update Metadata
```

### Categorization Flow

```
User Input → Validate Category → Load Ledger → Update Rows → Save Ledger
```

### Budget Calculation Flow

```
Categories + Ledgers → Filter by Date → Aggregate by Category → Prorate → Report
```

## Data Validation

### Pydantic Validation

All models use Pydantic for validation:

```python
try:
    account = Account(**data)
except ValidationError as e:
    print(f"Invalid account: {e}")
```

### CSV Validation

Ledger CSVs are validated on load:

- Required columns present
- Date format valid (YYYY-MM-DD)
- Amount is numeric
- Currency code valid
- Transaction ID format correct

### Category Validation

Categories validated when loaded:

- Name is non-empty and unique
- Budget amount is positive (if set)
- Period is valid enum
- No duplicate subcategory names
- Hierarchical references valid

## Performance Considerations

### CSV Size

Typical ledger sizes:

- 1 year: ~500-2,000 transactions
- 5 years: ~2,500-10,000 transactions
- File size: ~500 KB - 2 MB per account

### Load Time

- Small ledger (< 1,000 rows): < 100ms
- Medium ledger (1,000-5,000 rows): < 500ms
- Large ledger (5,000-20,000 rows): 1-2 seconds

### Memory Usage

- Transaction: ~500 bytes in memory
- 10,000 transactions: ~5 MB
- Full application: ~50 MB typical

## Related Documents

- [System Design](system-design.md) - Architecture overview
- [Project Structure](project-structure.md) - File organization
- [Budgeting System](../technical/budgeting-system.md) - Category and budget details
