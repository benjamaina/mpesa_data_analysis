"""
analyzer.py
-----------
Computes summary statistics and insights from the categorised DataFrame.
All functions return plain Python dicts/lists — JSON-serialisable.
"""

import logging
import pandas as pd
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def get_overview(df: pd.DataFrame) -> dict:
    try:
        return {
            "total_transactions": len(df),
            "date_range": {
                "from": str(df["date"].min().date()),
                "to":   str(df["date"].max().date()),
            },
            "total_money_in":  round(df["paid_in"].sum(), 2),
            "total_money_out": round(df["withdrawn"].sum(), 2),
            "net_flow":        round(df["paid_in"].sum() - df["withdrawn"].sum(), 2),
            "closing_balance": round(df["balance"].iloc[-1], 2),
            "opening_balance": round(df["balance"].iloc[0], 2),
        }
    except Exception as e:
        logger.error(f"get_overview failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute overview statistics.")


def get_monthly_summary(df: pd.DataFrame) -> list[dict]:
    try:
        monthly = (
            df.groupby("month")
            .agg(total_in=("paid_in","sum"), total_out=("withdrawn","sum"), transactions=("receipt_no","count"))
            .reset_index()
        )
        monthly["net"] = monthly["total_in"] - monthly["total_out"]
        return monthly.round(2).to_dict(orient="records")
    except Exception as e:
        logger.error(f"get_monthly_summary failed: {e}")
        return []   # non-fatal — return empty rather than crashing the whole response


def get_top_transactions(df: pd.DataFrame, n: int = 10) -> dict:
    try:
        top_in = (
            df[df["paid_in"] > 0]
            .nlargest(n, "paid_in")[["date", "details", "paid_in", "category"]]
            .assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d %H:%M"))
            .to_dict(orient="records")
        )
        top_out = (
            df[df["withdrawn"] > 0]
            .nlargest(n, "withdrawn")[["date", "details", "withdrawn", "category"]]
            .assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d %H:%M"))
            .to_dict(orient="records")
        )
        return {"top_credits": top_in, "top_debits": top_out}
    except Exception as e:
        logger.error(f"get_top_transactions failed: {e}")
        return {"top_credits": [], "top_debits": []}


def get_spending_by_category(df: pd.DataFrame) -> list[dict]:
    try:
        result = (
            df[df["withdrawn"] > 0]
            .groupby("category")["withdrawn"]
            .sum()
            .reset_index()
            .rename(columns={"withdrawn": "total_spent"})
            .sort_values("total_spent", ascending=False)
            .round(2)
        )
        return result.to_dict(orient="records")
    except Exception as e:
        logger.error(f"get_spending_by_category failed: {e}")
        return []


def get_spending_by_day_of_week(df: pd.DataFrame) -> list[dict]:
    try:
        order  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        result = (
            df[df["withdrawn"] > 0]
            .groupby("day_of_week")["withdrawn"]
            .agg(["sum","mean","count"])
            .reindex(order)
            .reset_index()
            .rename(columns={"sum":"total","mean":"average","count":"transactions"})
            .round(2)
            .fillna(0)
        )
        return result.to_dict(orient="records")
    except Exception as e:
        logger.error(f"get_spending_by_day_of_week failed: {e}")
        return []


def get_balance_trend(df: pd.DataFrame) -> list[dict]:
    try:
        trend = (
            df.groupby(df["date"].dt.date)["balance"]
            .last()
            .reset_index()
            .rename(columns={"date":"date","balance":"closing_balance"})
        )
        trend["date"]            = trend["date"].astype(str)
        trend["closing_balance"] = trend["closing_balance"].round(2)
        return trend.to_dict(orient="records")
    except Exception as e:
        logger.error(f"get_balance_trend failed: {e}")
        return []


def run_full_analysis(df: pd.DataFrame) -> dict:
    """
    Master function. Individual sections fail gracefully — a bad chart
    won't crash the whole response.
    """
    if df is None or df.empty:
        raise HTTPException(status_code=422, detail="No data to analyse.")

    return {
        "overview":             get_overview(df),          # fatal if this fails
        "monthly_summary":      get_monthly_summary(df),   # returns [] on error
        "top_transactions":     get_top_transactions(df),
        "spending_by_category": get_spending_by_category(df),
        "spending_by_day":      get_spending_by_day_of_week(df),
        "balance_trend":        get_balance_trend(df),
    }