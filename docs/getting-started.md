# Getting Started

This guide will help you set up Gilt and import your first transactions.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.13 or higher** installed
- Access to your bank's online banking (to export CSV files)
- Basic familiarity with the command line (for CLI) or comfort with desktop applications (for GUI)

## Installation

### 1. Set Up Python Environment

```bash
# Navigate to the Gilt directory
cd /path/to/gilt

# Create a virtual environment
python3.13 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate     # On Windows
```

### 2. Install Gilt

For CLI only:
```bash
pip install -e .
```

For CLI + GUI:
```bash
pip install -e .[gui]
```

For development (includes testing tools):
```bash
pip install -e .[dev]
```

### 3. Verify Installation

CLI:
```bash
gilt --help
```

GUI:
```bash
gilt-gui
```

## Initial Configuration

### 1. Create Accounts Configuration

Create `config/accounts.yml` to define your bank accounts:

```yaml
accounts:
  - account_id: MY_CHECKING
    description: "My Bank Checking Account"
    source_patterns:
      - "*checking*.csv"
      - "*chequing*.csv"

  - account_id: MY_CREDIT
    description: "My Credit Card"
    source_patterns:
      - "*creditcard*.csv"
      - "*visa*.csv"
```

!!! tip "Account IDs"
    Choose short, memorable IDs like `MYBANK_CHQ` or `VISA_1234`. These will be used in commands and file names.

### 2. Create Categories Configuration (Optional)

Create `config/categories.yml` to set up spending categories:

```yaml
categories:
  - name: "Housing"
    description: "Housing expenses"
    budget:
      amount: 2000.00
      period: monthly
    subcategories:
      - name: "Rent"
      - name: "Utilities"
      - name: "Maintenance"

  - name: "Transportation"
    description: "Vehicle and transit"
    budget:
      amount: 500.00
      period: monthly
    subcategories:
      - name: "Fuel"
      - name: "Transit"

  - name: "Dining Out"
    description: "Restaurants and takeout"
    budget:
      amount: 400.00
      period: monthly
```

You can also create categories through the CLI or GUI later.

## First Import

### 1. Export Your Bank Data

Log in to your bank's website and export your transactions as CSV files. Most banks offer this feature in the transaction history section.

!!! tip "Export Tips"
    - Export 3-6 months of data initially
    - Use descriptive filenames like `2025-11-16-checking.csv`
    - Keep the original CSV files safe

### 2. Place CSV Files

Put your exported CSV files in the `ingest/` directory:

```
gilt/
├── ingest/
│   ├── 2025-11-16-checking.csv
│   ├── 2025-11-16-credit.csv
│   └── ...
```

### 3. Import Using CLI

Preview the import (dry-run):
```bash
gilt ingest
```

Review the output, then import for real:
```bash
gilt ingest --write
```

### 4. Import Using GUI

1. Launch the GUI: `gilt-gui`
2. Click "Import" in the navigation or press `Ctrl+I`
3. Follow the wizard:
   - Select your CSV files
   - Verify account detection
   - Preview the data
   - Execute the import

## Verify Your Data

### CLI

List your accounts:
```bash
gilt accounts
```

View recent transactions:
```bash
gilt ytd --account MY_CHECKING --limit 20
```

### GUI

1. Open the Dashboard to see summary metrics
2. Click "Transactions" to browse all imported data
3. Use filters to narrow down the view

## Next Steps

Now that you have data imported, you can:

1. **[Categorize Transactions](user/workflows/budget-tracking.md)** - Organize spending into categories
2. **[Set Up Budgets](user/cli/budgeting.md)** - Track spending against budgets
3. **[Add Notes](user/cli/viewing.md#adding-notes)** - Annotate transactions with context
4. **[Generate Reports](user/cli/viewing.md#reports)** - Analyze your spending patterns

## Getting Help

- **CLI Reference**: See the [CLI Guide](user/cli/index.md) for all commands
- **GUI Guide**: See the [GUI Guide](user/gui/index.md) for visual interface help
- **Troubleshooting**: Check the user guide for common issues
- **Issues**: Report bugs on [GitHub](https://github.com/svetzal/gilt/issues)

## What's Next?

- Learn about [Monthly Budget Review workflow](user/workflows/monthly-review.md)
- Explore the [Transaction Management features](user/cli/viewing.md)
- Understand the [Architecture](developer/architecture/system-design.md) (for developers)
