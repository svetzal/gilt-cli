# Installation

This guide covers installing Gilt on your system.

## System Requirements

- **Operating System**: macOS, Linux, or Windows
- **Python**: Version 3.13 or higher
- **Disk Space**: ~100 MB for software, variable for data
- **RAM**: 256 MB minimum (more for large datasets)

## Installation Steps

### 1. Get the Code

Clone or download the Gilt repository:

```bash
git clone https://github.com/svetzal/gilt-cli.git
cd gilt
```

Or download and extract a ZIP file of the repository.

### 2. Create Virtual Environment

It's strongly recommended to use a Python virtual environment:

```bash
# Create virtual environment
python3.13 -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

!!! tip "Virtual Environment Benefits"
    Virtual environments isolate Gilt's dependencies from your system Python, preventing conflicts and making it easy to clean up later.

### 3. Install Gilt

Choose your installation type:

#### CLI Only

For command-line use only:

```bash
pip install -e .
```

#### CLI + GUI

For both command-line and graphical interface:

```bash
pip install -e .[gui]
```

This installs PySide6 and all GUI dependencies (~100 MB download).

#### Development

For contributing to Gilt (includes testing tools):

```bash
pip install -e .[dev]
```

This includes pytest, ruff, and other development tools.

### 4. Verify Installation

Test CLI installation:

```bash
gilt --help
```

You should see a list of available commands.

Test GUI installation (if installed):

```bash
gilt-gui
```

A window should open showing the Gilt application.

## Directory Setup

Create the required directory structure:

```bash
# From the gilt directory
mkdir -p config
mkdir -p ingest
mkdir -p data/accounts
mkdir -p reports
```

Your structure should look like:

```
gilt/
├── config/           # Account and category configurations
├── ingest/          # Raw bank CSV files (input)
├── data/
│   └── accounts/    # Normalized ledger files (output)
├── reports/         # Generated reports (optional)
└── ...
```

## Configuration Files

### Create accounts.yml

Create `config/accounts.yml` with your account information:

```yaml
accounts:
  - account_id: MY_CHECKING
    description: "My Checking Account"
    source_patterns:
      - "*checking*.csv"
      - "*chequing*.csv"

  - account_id: MY_CREDIT
    description: "My Credit Card"
    source_patterns:
      - "*credit*.csv"
```

### Create categories.yml (Optional)

Create `config/categories.yml` for budget categories:

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

  - name: "Transportation"
    description: "Vehicle and transit"
    budget:
      amount: 500.00
      period: monthly
```

You can also create categories later through CLI or GUI.

## Platform-Specific Notes

### macOS

Gilt works out of the box on macOS. If you encounter SSL certificate issues:

```bash
# May be needed for older macOS versions
/Applications/Python\ 3.13/Install\ Certificates.command
```

### Linux

Most distributions work without issues. If you encounter GTK/Qt issues with the GUI:

```bash
# Ubuntu/Debian
sudo apt-get install libxcb-xinerama0 libxcb-cursor0

# Fedora
sudo dnf install xcb-util-cursor
```

### Windows

On Windows, you may need to:

1. Use PowerShell instead of CMD
2. Enable long path support if you encounter path length errors
3. Install Visual C++ Redistributable for some dependencies

## Updating Gilt

To update to the latest version:

```bash
# Activate virtual environment
source .venv/bin/activate

# Pull latest code
git pull

# Reinstall (updates dependencies if needed)
pip install -e .[gui]
```

## Troubleshooting

### Command not found: `gilt`

**Problem**: After installation, `gilt` command isn't recognized.

**Solution**:
1. Ensure virtual environment is activated: `source .venv/bin/activate`
2. Reinstall: `pip install -e .`
3. Check installation: `pip list | grep gilt`

### ModuleNotFoundError: No module named 'PySide6'

**Problem**: GUI won't start, missing PySide6.

**Solution**: Install GUI dependencies:
```bash
pip install -e .[gui]
```

### Permission denied when creating directories

**Problem**: Can't create `config/` or `data/` directories.

**Solution**: Check directory permissions:
```bash
ls -la
chmod 755 .  # If needed
```

### Python version too old

**Problem**: `python3.13 not found`.

**Solution**: Install Python 3.13 from [python.org](https://www.python.org/downloads/) or use your package manager:

```bash
# macOS with Homebrew
brew install python@3.13

# Ubuntu/Debian
sudo apt-get install python3.13

# Fedora
sudo dnf install python3.13
```

## Uninstallation

To remove Gilt:

```bash
# Deactivate virtual environment
deactivate

# Remove the entire directory
rm -rf /path/to/gilt
```

Your data files in `ingest/` and `data/` will be deleted too, so back them up first if needed.

## Next Steps

After installation:

1. [Configure your accounts](../getting-started.md#initial-configuration)
2. [Import your first transactions](../getting-started.md#first-import)
3. Explore the [CLI Guide](cli/index.md) or [GUI Guide](gui/index.md)
