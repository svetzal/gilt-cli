from __future__ import annotations

"""
Category configuration I/O (YAML loading and saving).

Functions for reading and writing config/categories.yml. Follows the same
patterns as account config loading in gilt.ingest.

Privacy
- All operations are local file I/O only
- No network access
"""

from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from gilt.model.category import Category, CategoryConfig


def load_categories_config(path: Path) -> CategoryConfig:
    """Load categories config from YAML locally (safe loader).

    Returns a CategoryConfig with list of Category models. If YAML is unavailable
    or file missing, returns an empty CategoryConfig. No network access is performed.
    
    Args:
        path: Path to categories.yml file
        
    Returns:
        CategoryConfig instance (empty if file missing or invalid)
    """
    if yaml is None:
        # Proceed without config (return empty)
        return CategoryConfig(categories=[])
    
    if not path.exists():
        return CategoryConfig(categories=[])
    
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # Validate the entire config structure
        return CategoryConfig.model_validate(data)
    except Exception:  # pragma: no cover
        # Swallow errors and return empty config for resilience
        return CategoryConfig(categories=[])


def save_categories_config(path: Path, config: CategoryConfig) -> None:
    """Save categories config to YAML file.
    
    Writes the CategoryConfig to disk as YAML. Creates parent directories if needed.
    
    Args:
        path: Path to categories.yml file
        config: CategoryConfig instance to save
        
    Raises:
        Exception: If YAML library unavailable or write fails
    """
    if yaml is None:
        raise RuntimeError("YAML library not available; cannot save categories config")
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict using Pydantic's model_dump
    # Use mode="json" to serialize enums as their values (strings) for YAML compatibility
    data = config.model_dump(exclude_none=True, mode="json")
    
    # Write YAML with nice formatting
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )


def parse_category_path(category_path: str) -> tuple[str, Optional[str]]:
    """Parse a category path string into category and optional subcategory.
    
    Supports both formats:
    - "Category" -> ("Category", None)
    - "Category:Subcategory" -> ("Category", "Subcategory")
    
    Args:
        category_path: Category path string (e.g., "Housing" or "Housing:Utilities")
        
    Returns:
        Tuple of (category_name, subcategory_name or None)
    """
    if ":" in category_path:
        parts = category_path.split(":", 1)
        return parts[0].strip(), parts[1].strip()
    return category_path.strip(), None


__all__ = [
    "load_categories_config",
    "save_categories_config",
    "parse_category_path",
]
