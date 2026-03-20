"""
cleaner.py
----------
Takes the raw DataFrame from parser.py and returns a clean, typed DataFrame
ready for analysis and categorisation.
"""

import logging
import pandas as pd
from fastapi import HTTPException

logger = logging.getLogger(__name__)

COLUMN_MAP = {
    "receipt no": "receipt_no", "receipt number": "receipt_no", "transaction id": "receipt_no",
    "completion time": "date",  "transaction date": "date", "date": "date", "time": "date",
    "details": "details",       "description": "details", "transaction details": "details", "narration": "details",
    "transaction status": "status", "status": "status",
    "paid in": "paid_in",       "money in": "paid_in",  "credit": "paid_in",  "amount credited": "paid_in",
    "withdrawn": "withdrawn",   "money out": "withdrawn", "debit": "withdrawn", "amount debited": "withdrawn",
    "balance": "balance",       "running balance": "balance",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: COLUMN_MAP[col.strip().lower()]
               for col in df.columns if col.strip().lower() in COLUMN_MAP}
    df = df.rename(columns=renamed)

    missing = {"receipt_no", "date", "details", "paid_in", "withdrawn", "balance"} - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Statement is missing expected columns: {sorted(missing)}. "
                   "Make sure this is a valid M-Pesa statement."
        )
    return df


def _clean_money(series: pd.Series) -> pd.Series:
    try:
        return (
            series.fillna("0")
            .astype(str)
            .str.replace(r"[KSh,\s]", "", regex=True)
            .str.replace(r"[^\d.]", "", regex=True)
            .replace("", "0")
            .astype(float)
            .fillna(0.0)
        )
    except Exception as e:
        logger.error(f"Failed to clean money column: {e}")
        # Return zeros rather than crashing — cleaner will still produce a usable DataFrame
        return pd.Series([0.0] * len(series), index=series.index)


def clean_statement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main entry point.
    Takes the raw DataFrame from parser.py and returns a clean DataFrame.
    """
    if df is None or df.empty:
        raise HTTPException(status_code=422, detail="Statement has no rows to process.")

    try:
        df = df.copy()
        df = _normalise_columns(df)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Column normalisation failed: {e}")
        raise HTTPException(status_code=422, detail="Could not read the statement columns.")

    try:
        df.dropna(how="all", inplace=True)
        df.drop_duplicates(subset=["receipt_no"], keep="first", inplace=True)

        for col in ["receipt_no", "details", "status"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
    except Exception as e:
        logger.error(f"Row cleaning failed: {e}")
        raise HTTPException(status_code=422, detail="Failed to clean statement rows.")

    try:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        bad_dates  = df["date"].isna().sum()
        if bad_dates > 0:
            logger.warning(f"Dropped {bad_dates} rows with unparseable dates")
        df.dropna(subset=["date"], inplace=True)

        if df.empty:
            raise HTTPException(
                status_code=422,
                detail="No valid dates found in the statement. "
                       "Check that the file is a real M-Pesa statement."
            )

        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Date parsing failed: {e}")
        raise HTTPException(status_code=422, detail="Failed to parse transaction dates.")

    try:
        df["paid_in"]   = _clean_money(df["paid_in"])
        df["withdrawn"] = _clean_money(df["withdrawn"])
        df["balance"]   = _clean_money(df["balance"])
    except Exception as e:
        logger.error(f"Money column cleaning failed: {e}")
        raise HTTPException(status_code=422, detail="Failed to parse transaction amounts.")

    try:
        df["transaction_type"] = df.apply(
            lambda row: "CREDIT" if row["paid_in"] > 0 else "DEBIT", axis=1
        )
        df["month"]       = df["date"].dt.to_period("M").astype(str)
        df["day_of_week"] = df["date"].dt.day_name()
        df["hour"]        = df["date"].dt.hour
    except Exception as e:
        logger.error(f"Derived column creation failed: {e}")
        raise HTTPException(status_code=422, detail="Failed to compute derived fields.")

    return df