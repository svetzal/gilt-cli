# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.6.0] - 2026-05-29

### Added
- `gilt show` — full transaction inspection by transaction ID prefix
- `gilt history` — vendor categorization lookup by description pattern
- `gilt status` — per-account freshness and ledger health dashboard
- `gilt receipts` — receipt attachment coverage reporting by subcategory or account
- `gilt diagnose-duplicates` — duplicate metadata diagnostics and orphan detection
- `gilt summary` — category/subcategory spending aggregation command with `--category`, `--year`, `--fy`, `--account`, and `--include-uncategorized` flags
- Shared CLI presentation helpers and test fixture builders for cleaner command tests

### Changed
- `gilt uncategorized` now defaults to all accounts and supports fiscal-year filtering
- `gilt categorize` now supports file-batch mode with `--txid-file` and `--from-stdin`
- `gilt recategorize` now supports transaction filtering and selection-mode flags
- `gilt category --add` now auto-creates the parent category when needed
- Decomposed the transaction GUI view into focused controllers, workers, and widgets
- Extracted ingestion orchestration, duplicate diagnostics, receipts reporting, and summary services
- Standardized helper naming across CLI, services, GUI, transfer, and storage modules
- Updated dependencies to latest compatible versions

### Fixed
- Prevent orphaned duplicate metadata and add diagnostics to find existing issues
- Improve CLI reliability and user experience across categorization, duplicate handling, reingest, receipts, and status workflows

### Tests
- Expanded command, service, projection, transfer, GUI controller, and widget coverage for the new CLI and refactoring work

### Documentation
- Audit packaged skill (`src/gilt/skills/gilt/`) against batch `gilt-improvement-20260528`: updated `SKILL.md` and `references/command-reference.md` to cover new commands (`show`, `history`, `status`, `receipts`, `diagnose-duplicates`, `summary`, `reingest`, `ingest-receipts`, `infer-rules`), changed behaviour for `uncategorized` (all-accounts default, `--fy` flag), `categorize` (`--txid-file`/`--from-stdin` file-batch mode), `recategorize` (selection-mode flags), and `category --add` (auto-creates parent category if absent)

## [0.5.3] - 2026-04-20

### Added
- `--json` flag for `skill-init` command with corrected exit codes

### Changed
- Extract ledger I/O to `LedgerRepository` gateway (functional core isolation)
- Extract canonical rule-match → update conversion to pure function
- Extract batch receipt matching to service layer
- Consolidate `DEFAULT_VENDOR_PATTERNS` to service layer
- Eliminate duplicated budget proration and spending aggregation
- Refactor date range logic into testable pure function
- Fix Qt deprecation warnings in GUI views

### Dependencies
- Upgrade rich from 14.3.4 to 15.0.0
- Update mojentic, openai, anthropic, PySide6, scipy, and transitive dependencies

## [0.5.2] - 2026-04-12

### Fixed
- Fix `gilt skill-init` failing when installed via `uv tool install` — skill source files are now packaged inside the wheel instead of relying on a repo-relative path

## [0.5.1] - 2026-04-11

### Changed
- Extract file I/O from EventMigrationService, isolating pure business logic from filesystem dependencies
- Extract budget reporting logic to dedicated BudgetReportingService with dataclass models
- Remove category logic duplication in GUI service layer by delegating to CategoryManagementService
- Link CHARTER.md in AGENTS.md for agent clarity on project purpose and constraints

### Tests
- Add ~190 comprehensive tests across transfer linking, GUI services, ledger I/O, budget, duplicate detection, and event sourcing modules

### Dependencies
- Update ruff, openai, anthropic, PySide6, anyio, mkdocs-material, and transitive dependencies to latest patches

## [0.5.0] - 2026-03-17

### Added
- Skill distribution infrastructure (`gilt skill-init` command)
- Rule-inference engine for automatic transaction categorization
- Receipt matching and disambiguation in GUI
- Interactive disambiguation for receipt ingestion
- Progress indicator for background intelligence scan
- `reingest` command, detail panel enhancements, and selection stability
- `amount_sign` import hint to support reversed debit/credit

### Changed
- Switch GUI transaction loading to projections database
- Sync projections DB after categorization so view reflects changes
- Centralize default Ollama model to `DEFAULT_OLLAMA_MODEL` constant
- Improve detail panel layout and preserve sort order across reloads
- Expand ruff lint rules with Bugbear, McCabe, isort, Simplify, and pyupgrade
- Reduce McCabe complexity (C901) across 19 functions and enforce max-complexity 12

### Fixed
- GUI crash bugs: sync projections after mutations and clean up worker threads

### Dependencies
- Numerous dependency updates (mojentic, ruff, openai, anthropic, scipy, typer, rich, and others)

## [0.3.5] and earlier

See git history for previous changes.
