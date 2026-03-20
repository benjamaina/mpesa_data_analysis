"""
cleaner.py
----------
Takes the raw DataFrame from parser.py and returns a clean, typed DataFrame
ready for analysis and categorisation.

What this does:
  - Standardises column names
  - Parses dates
  - Converts money columns (Paid In, Withdrawn, Balance) to float
  - Drops empty / duplicate rows
  - Adds a derived 'Transaction Type' column (CREDIT / DEBIT)
"""

import re
import pandas as pd
from fastapi import HTTPException


# Map of possible raw column names → our internal standard names
COLUMN_MAP = {
    # Receipt
    "receipt no": "receipt_no",
    "receipt number": "receipt_no",
    "transaction id": "receipt_no",

    # Date
    "completion time": "date",
    "transaction date": "date",
    "date": "date",
    "time": "date",

    # Description
    "details": "details",
    "description": "details",
    "transaction details": "details",
    "narration": "details",

    # Status
    "transaction status": "status",
    "status": "status",

    # Money in
    "paid in": "paid_in",
    "money in": "paid_in",
    "credit": "paid_in",
    "amount credited": "paid_in",

    # Money out
    "withdrawn": "withdrawn",
    "money out": "withdrawn",
    "debit": "withdrawn",
    "amount debited": "withdrawn",

    # Balance
    "balance": "balance",
    "running balance": "balance",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to standard internal names."""
    renamed = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_MAP:
            renamed[col] = COLUMN_MAP[key]
    df = df.rename(columns=renamed)

    # Ensure required columns exist
    required = {"receipt_no", "date", "details", "paid_in", "withdrawn", "balance"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Statement is missing expected columns: {missing}. "
                   "Make sure this is a valid M-Pesa statement."
        )
    return df


def _clean_money(series: pd.Series) -> pd.Series:
    """Remove commas, currency symbols, and cast to float."""
    return (
        series.fillna("0")                            # NaN → "0" before any string ops
        .astype(str)
        .str.replace(r"[KSh,\s]", "", regex=True)    # remove KSh, commas, spaces
        .str.replace(r"[^\d.]", "", regex=True)       # keep only digits and dot
        .replace("", "0")                             # empty string → "0"
        .astype(float)
        .fillna(0.0)                                  # catch any remaining NaN after cast
    )


def clean_statement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main entry point.
    Takes the raw DataFrame from parser.py and returns a clean DataFrame.

    Returns columns:
        receipt_no, date (datetime), details, status,
        paid_in (float), withdrawn (float), balance (float),
        transaction_type ('CREDIT' | 'DEBIT')
    """
    df = df.copy()

    # ── 1. Standardise column names ──────────────────────────────────────────
    df = _normalise_columns(df)

    # ── 2. Drop completely empty rows & duplicates ────────────────────────────
    df.dropna(how="all", inplace=True)
    df.drop_duplicates(subset=["receipt_no"], keep="first", inplace=True)

    # ── 3. Strip whitespace from string columns ───────────────────────────────
    for col in ["receipt_no", "details", "status"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── 4. Parse dates ────────────────────────────────────────────────────────
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df.dropna(subset=["date"], inplace=True)   # drop rows with unparseable dates
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ── 5. Clean money columns ────────────────────────────────────────────────
    df["paid_in"]   = _clean_money(df["paid_in"])
    df["withdrawn"] = _clean_money(df["withdrawn"])
    df["balance"]   = _clean_money(df["balance"])

    # ── 6. Derive transaction type ────────────────────────────────────────────
    df["transaction_type"] = df.apply(
        lambda row: "CREDIT" if row["paid_in"] > 0 else "DEBIT",
        axis=1
    )

    # ── 7. Add helper time columns ────────────────────────────────────────────
    df["month"]       = df["date"].dt.to_period("M").astype(str)
    df["day_of_week"] = df["date"].dt.day_name()
    df["hour"]        = df["date"].dt.hour

    return df