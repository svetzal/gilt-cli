"""
Central configuration for Finance application.

Path resolution has been moved to gilt.workspace.Workspace, which provides
a single workspace root with computed path properties for all data locations.

See gilt.workspace for details on how paths are resolved:
  1. Explicit --data-dir CLI option
  2. GILT_DATA environment variable
  3. Current working directory
"""

DEFAULT_OLLAMA_MODEL = "qwen3.5:27b"
