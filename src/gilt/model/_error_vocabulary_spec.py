"""
Static guard: exception-handling vocabulary must not be re-derived at call sites.

gilt.model.errors defines DATA_IO_ERRORS, CONFIG_IO_ERRORS, and LEDGER_IO_ERRORS as the
canonical tuples for "recoverable data read/parse failure". Hand-rolling an equivalent
tuple inline at a catch site duplicates that knowledge and drifts out of sync as the
vocabulary evolves.

Rules enforced, by walking every non-spec *.py under src/gilt with ast:
  1. An except clause must not name a tuple containing two or more of OSError, ValueError,
     UnicodeDecodeError, FileNotFoundError, YAMLError as literal names — it should import
     and use DATA_IO_ERRORS / CONFIG_IO_ERRORS / LEDGER_IO_ERRORS instead.
  2. An except clause must not catch bare Exception (or a tuple containing Exception) with
     a body that is only `pass` or `continue` — a blanket swallow that also hides
     programming errors (AttributeError, TypeError, etc).

_ALLOWLIST is empty by design and must stay empty. Add entries only as temporary
scaffolding for active migrations, and remove them as soon as the module is brought
into compliance.

Documented exemption (not an allowlist entry): gilt.gui.services.import_service raw-CSV
loading catches (FileNotFoundError, UnicodeDecodeError, pd.errors.ParserError[, KeyError])
around pandas.read_csv. pd.errors.ParserError is a pandas-specific boundary concern, not
part of the shared DATA_IO_ERRORS vocabulary, so these two call sites are excluded from
rule 1 by name (module + line) rather than broadening the vocabulary to fit pandas.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).parent.parent

_FLAGGED_NAMES = {"OSError", "ValueError", "UnicodeDecodeError", "FileNotFoundError", "YAMLError"}

_VOCABULARY_NAMES = {"DATA_IO_ERRORS", "CONFIG_IO_ERRORS", "LEDGER_IO_ERRORS"}

# Empty by design — all non-exempt call sites comply. Add entries only for active migrations.
# Format: "relative/path/from/src/gilt.py:lineno"
_ALLOWLIST: set[str] = set()

# Pandas-specific boundary, not the shared I/O vocabulary — see module docstring.
_PANDAS_BOUNDARY_EXEMPTIONS = {
    "gui/services/import_service.py:187",
    "gui/services/import_service.py:260",
}


def _iter_source_modules() -> list[Path]:
    modules = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path.stem.endswith("_spec") or path.stem.startswith("_"):
            continue
        modules.append(path)
    return modules


def _handler_type_names(handler: ast.ExceptHandler) -> list[str]:
    node = handler.type
    if node is None:
        return []
    if isinstance(node, ast.Tuple):
        return [elt.id for elt in node.elts if isinstance(elt, ast.Name)]
    if isinstance(node, ast.Name):
        return [node.id]
    return []


def _is_blanket_swallow(handler: ast.ExceptHandler) -> bool:
    names = _handler_type_names(handler)
    if "Exception" not in names:
        return False
    return all(isinstance(stmt, (ast.Pass, ast.Continue)) for stmt in handler.body)


def _find_violations() -> list[str]:
    violations = []
    for path in _iter_source_modules():
        rel = path.relative_to(SRC_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            key = f"{rel}:{node.lineno}"
            if key in _ALLOWLIST:
                continue

            names = set(_handler_type_names(node))
            if len(names & _FLAGGED_NAMES) >= 2 and key not in _PANDAS_BOUNDARY_EXEMPTIONS:
                violations.append(
                    f"{key}: hand-rolled tuple {sorted(names)} — use one of "
                    f"{sorted(_VOCABULARY_NAMES)} from gilt.model.errors instead"
                )
                continue

            if _is_blanket_swallow(node):
                violations.append(
                    f"{key}: bare `except Exception` with a pass/continue body swallows "
                    "programming errors — catch a specific, named exception set instead"
                )

    return violations


class DescribeErrorVocabularyGuard:
    def it_should_have_no_hand_rolled_tuples_or_blanket_swallows(self):
        violations = _find_violations()
        assert not violations, "Error-vocabulary violations found:\n" + "\n".join(violations)
