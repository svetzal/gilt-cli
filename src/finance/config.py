"""
Central configuration for Finance application.

Path resolution has been moved to finance.workspace.Workspace, which provides
a single workspace root with computed path properties for all data locations.

See finance.workspace for details on how paths are resolved:
  1. Explicit --data-dir CLI option
  2. FINANCE_DATA environment variable
  3. Current working directory
"""
