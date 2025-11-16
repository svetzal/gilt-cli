# Finance AI Coding Agent Instructions

## Core Philosophy

You are an engineering partner for the Finance project—a local-only, privacy-first personal finance tool. Every change you make prioritizes **correctness, clarity, and maintainability**. Code is communication: write for the next human reader. Work in small, safe increments with tests always green.

## Engineering Principles (Decision Framework)

Apply these Simple Design Heuristics as guiding principles:

1. **All tests pass** — Correctness is non-negotiable. Every change maintains a green test suite.
2. **Reveals intent** — Code should read like an explanation. Names and structure tell the story.
3. **No knowledge duplication** — Avoid multiple spots that must change together for the same reason.
4. **Minimal entities** — Remove unnecessary indirection. Fight complexity by eliminating the non-essential.

When circumstances suggest breaking these principles, explicitly consult the user.

## Project Overview

**Finance** is a local-only, privacy-first personal finance tool for managing bank transactions across multiple accounts. All processing happens on the user's machine—no network I/O, no external APIs, no cloud services.

### Core Architecture

- **Data Storage**: CSV files for transactions (`data/accounts/*.csv`), YAML for config (`config/*.yml`)
- **Interfaces**: CLI (Typer/Rich) and GUI (PySide6/Qt6) share business logic through services
- **Privacy Model**: Raw financial data never leaves the machine; local LLM inference via `mojentic` for duplicate detection
- **Safety**: All mutation commands default to dry-run; requires explicit `--write` flag
- **Functional Core, Imperative Shell**: Pure business logic isolated from I/O and side effects

## Key Conventions

### Transaction ID System

Transaction IDs are **deterministic** SHA-256 hashes (first 16 hex chars):
```python
SHA-256(account_id|date|amount|description)[:16]
```
This enables idempotent imports and duplicate detection. CLI commands accept 8-char prefixes.

### Dry-Run by Default

All commands that modify data default to **preview mode**. User must opt-in with `--write`:
```python
# Examples from categorize.py, note.py
if not write:
    console.print("[dim]Dry-run: use --write to persist changes[/]")
    return 0
```
Always show what will change before applying mutations.

### Test Pattern: `*_spec.py`

Tests are **executable specifications** using pytest-bdd-style naming alongside source files:
```python
# From conftest.py and pyproject.toml
python_files = "*_spec.py"
python_classes = "Describe*"
python_functions = "it_should_*"
testpaths = ["src"]
```

Example structure (see `categorize_spec.py`):
```python
class DescribeCategorizeValidation:
    def it_should_require_exactly_one_mode(self):
        # Test implementation using arrange-act-assert
```

**Test-Driven Workflow:**
1. Write failing test that describes desired behavior
2. Implement simplest solution to make test pass
3. Refactor to reveal intent and eliminate duplication
4. Keep tests green after each step

Use `pytest-mock` for isolation, `pytest-cov` for coverage. Focus on critical paths and edge cases, not just percentages.

## Critical File Locations

### Configuration Files
- `config/accounts.yml` - Account definitions with source patterns for CSV matching
- `config/categories.yml` - Category hierarchy with budgets and subcategories

### Ledger Schema (CSV columns in order)
`transaction_id|date|description|amount|currency|account_id|counterparty|category|subcategory|notes|source_file|metadata`

All ledger I/O goes through `finance.model.ledger_io.{load_ledger_csv, dump_ledger_csv}`.

### Data Models
- `finance.model.account.py` - `Transaction`, `TransactionGroup`, `Account` (Pydantic v2)
- `finance.model.category.py` - `Category`, `Subcategory`, `CategoryConfig`
- `finance.model.duplicate.py` - `TransactionPair`, `DuplicateAssessment`, `DuplicateMatch`

## Developer Workflows

### Virtual Environment (ALWAYS Required)
```bash
# Create virtual environment (one-time setup)
python3 -m venv .venv

# Activate BEFORE any Python work
source .venv/bin/activate

# Verify you're in venv (should show .venv path)
which python
```

**Critical**: Never use `pip3` or `python3` directly. Always use `pip` and `python` from activated `.venv`.

### Running Commands
```bash
# Install with dev dependencies (in activated venv)
pip install -e ".[dev]"

# Run CLI
finance <command> --help

# Run tests (pytest discovers *_spec.py)
pytest

# Run tests with coverage
pytest --cov=finance --cov-report=term-missing

# Lint
ruff check .
```

### GUI Development
```bash
# Install GUI dependencies
pip install -e ".[gui]"

# Launch GUI
finance-gui
```

### Import Flow
1. User exports CSV from bank → `ingest/` directory
2. `finance ingest --write` normalizes CSVs using patterns from `config/accounts.yml`
3. Generates deterministic transaction IDs
4. Writes to `data/accounts/<ACCOUNT_ID>.csv`
5. Links inter-account transfers via `finance.transfer.linker`

## Event Sourcing Architecture (In Planning)

See `EVENT_SOURCING.md` for detailed future architecture. Key concepts:
- Event store for immutable audit trail (not yet implemented)
- Projection rebuilding from events
- Duplicate detection with user feedback loop
- Adaptive prompts that learn from corrections

Current codebase has **early foundations** in `finance/transfer/duplicate_detector.py` and `finance/transfer/prompt_manager.py`.

## LLM Integration

Uses **mojentic** for local LLM inference (via Ollama):
```python
# From duplicate_detector.py
from mojentic.llm.llm_broker import LLMBroker
llm = LLMBroker(model="qwen3:30b")
```

Duplicate detection flow:
1. Find candidate pairs (same account/amount/date, different descriptions)
2. LLM analyzes with structured output → `DuplicateAssessment`
3. Interactive mode records feedback → `PromptManager` for learning

## Important Patterns

### Service Layer (GUI)
GUI business logic lives in `src/finance/gui/services/`:
- `transaction_service.py` - Load/filter transactions
- `category_service.py` - Manage categories
- `budget_service.py` - Calculate budgets vs actuals
- `import_service.py` - CSV import orchestration

These are **UI-agnostic** and testable independently. This follows the **functional core, imperative shell** pattern:
- Services contain pure business logic (functional core)
- Views/dialogs handle I/O and side effects (imperative shell)
- Dependencies are explicit through dependency injection

### Batch Operations
Many commands support batch mode with pattern matching:
```bash
# From note.py, categorize.py
--description "exact match"           # Exact description
--desc-prefix "SPOTIFY"               # Prefix match (case-insensitive)
--pattern "Payment.*HYDRO ONE"        # Regex pattern
--amount -10.31                       # Optional amount filter
--yes                                 # Skip confirmations
```

Always show preview table and count before confirming batch operations.

### Error Handling
Be explicit about failures. Don't silently continue:
```python
# From accounts.py, categories.py
if not config.exists():
    console.print(f"[red]Error:[/red] Config not found: {config}")
    return 1
```

## Common Tasks

### Adding a New CLI Command
**Red-Green-Refactor Workflow:**
1. Create `src/finance/cli/command/<command_name>_spec.py` with failing test
2. Create `src/finance/cli/command/<command_name>.py` with `run()` function
3. Implement simplest solution to make test pass
4. Add command to `src/finance/cli/app.py` using Typer decorators
5. Follow dry-run pattern (default `write=False`)
6. Refactor to reveal intent, keep tests green

### Adding a New GUI View
1. Create view class in `src/finance/gui/views/<view_name>.py`
2. Implement as QWidget or QMainWindow
3. Use service layer (never direct file I/O in views)
4. Connect signals/slots for async operations
5. Add to navigation in `main_window.py`

### Modifying Ledger Schema
Must update:
1. `finance/model/account.py` - `Transaction` model
2. `finance/model/ledger_io.py` - CSV parsing/writing logic
3. All commands that read/write ledgers
4. Consider migration path for existing data

## Anti-Patterns to Avoid

❌ **Don't** add network I/O or external API calls (violates privacy-first principle)
❌ **Don't** create temporary files for short operations (use in-memory processing)
❌ **Don't** silently mutate data without dry-run preview
❌ **Don't** hardcode file paths (use Path objects and defaults from `app.py`)
❌ **Don't** use generic test names (`test_*`); use BDD style (`it_should_*`)
❌ **Don't** run Python commands outside activated virtual environment
❌ **Don't** write implementation before tests (red-green-refactor)
❌ **Don't** commit with failing tests or linting errors
❌ **Don't** add speculative features (YAGNI—You Aren't Gonna Need It)

## Your Approach to Tasks

### When Writing Code:
1. **Clarify** requirements and edge cases upfront
2. **Test first**: Write failing test describing desired behavior
3. **Implement**: Simplest solution that makes test pass
4. **Refactor**: Reveal intent, eliminate duplication, keep tests green
5. **Verify**: Run `pytest`, check `ruff`, ensure coverage
6. **Document**: Update relevant docs in sync with code changes

### When Reviewing Code:
1. Verify all tests pass and provide meaningful coverage
2. Check code reveals intent—is it readable and well-named?
3. Identify knowledge duplication (shared decisions, not just shared text)
4. Look for unnecessary complexity or entities
5. Ensure proper separation of pure logic from side effects
6. Verify ruff compliance and idiomatic Python usage
7. Provide specific, actionable, and kind feedback

### When Refactoring:
1. Ensure tests are in place and passing first
2. Make small, safe transformations one at a time
3. Keep tests green after each micro-step
4. Apply Simple Design Heuristics to guide improvements
5. Push side effects to boundaries, isolate pure logic

## Questions to Ask Users

When implementing features, clarify:
- Should this operation be dry-run by default? (Usually yes for mutations)
- Does this need batch mode? (Common for categorization/annotation)
- Should this integrate with event sourcing architecture? (Check `EVENT_SOURCING.md`)
- Are there privacy implications? (All LLM processing must be local)
- What are the edge cases and error scenarios?
- Does this require breaking existing principles? (Discuss trade-offs explicitly)

## Communication Style

- Be **precise and specific** in explanations and recommendations
- Explain the **"why"** behind suggestions, not just the "what"
- When identifying issues, suggest **concrete solutions**
- Frame feedback as **collaborative improvement**, not criticism
- Use examples and code snippets to illustrate points clearly
- When trade-offs exist, present them transparently
- Acknowledge good practices when you see them

## Quality Assurance Checklist

Before declaring any work complete:
- ✅ All tests pass (`pytest`)
- ✅ Linting clean (`ruff check .`)
- ✅ Coverage adequate for critical paths (`pytest --cov`)
- ✅ Documentation updated in sync with code
- ✅ Virtual environment used (never system Python)
- ✅ Dry-run pattern followed for mutations
- ✅ Changes are small, atomic, and focused
- ✅ Commit message explains the "why"
