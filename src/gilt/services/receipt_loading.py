from __future__ import annotations

"""
Receipt loading — I/O boundary for reading receipt JSON files from disk.

This is the shell side of the receipt core/shell split:
  receipt_loading.py         — ReceiptData model + I/O boundary (this file)
  receipt_ingestion_service.py — pure matching logic + re-exports

I/O boundary functions:
  load_receipt_file  — read and parse a single mailctl.receipt.v1 JSON file
  find_receipt_files — recursively discover JSON files in a directory

Privacy: All processing is local-only. No network I/O.
"""

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass
class ReceiptData:
    """Parsed receipt from a mailctl.receipt.v1 JSON sidecar file."""

    vendor: str
    service: str | None
    amount: Decimal
    currency: str
    tax_amount: Decimal | None
    tax_type: str | None
    receipt_date: date
    invoice_number: str | None
    source_email: str | None
    receipt_file: str | None
    source_path: Path  # path to the JSON file itself

    @classmethod
    def from_dict(cls, data: dict, source_path: Path) -> ReceiptData:
        """Parse a mailctl.receipt.v1 dict into a ReceiptData.

        Raises:
            ValueError: If schema is not mailctl.receipt.v1 or required fields are missing.
        """
        schema = data.get("schema")
        if schema != "mailctl.receipt.v1":
            raise ValueError(f"Unsupported schema: {schema}")

        if "vendor" not in data or "amount" not in data or "date" not in data:
            raise ValueError("Missing required fields: vendor, amount, date")

        tax = data.get("tax")
        tax_amount = None
        tax_type = None
        if isinstance(tax, dict):
            tax_amount = Decimal(str(tax["amount"])) if "amount" in tax else None
            tax_type = tax.get("type")

        return cls(
            vendor=data["vendor"],
            service=data.get("service"),
            amount=Decimal(str(data["amount"])) if data.get("amount") is not None else None,
            currency=data.get("currency", "CAD"),
            tax_amount=tax_amount,
            tax_type=tax_type,
            receipt_date=date.fromisoformat(data["date"]),
            invoice_number=data.get("invoice_number"),
            source_email=data.get("source_email"),
            receipt_file=data.get("receipt_file"),
            source_path=source_path,
        )


def load_receipt_file(path: Path) -> ReceiptData:
    """Read and parse a mailctl.receipt.v1 JSON file. I/O boundary function.

    Raises:
        ValueError: If schema is not mailctl.receipt.v1 or required fields are missing.
        json.JSONDecodeError: If file is not valid JSON.
        OSError: If file cannot be read.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReceiptData.from_dict(data, path)


def find_receipt_files(source_dir: Path) -> list[Path]:
    """Recursively find all JSON files in source_dir. I/O boundary function.

    Args:
        source_dir: Root directory to search.

    Returns:
        Sorted list of JSON file paths.
    """
    if not source_dir.is_dir():
        return []
    return sorted(source_dir.rglob("*.json"))


__all__ = ["ReceiptData", "find_receipt_files", "load_receipt_file"]
