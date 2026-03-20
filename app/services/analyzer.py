"""
analyzer.py
-----------
Computes summary statistics and insights from the categorised DataFrame.
All functions return plain Python dicts/lists — JSON-serialisable — so
main.py can return them directly from API endpoints.
"""

import pandas as pd


def get_overview(df: pd.DataFrame) -> dict:
    """High-level summary of the entire statement period."""
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


def get_monthly_summary(df: pd.DataFrame) -> list[dict]:
    """
    Returns money in / out / net per calendar month.
    Useful for a bar chart in the frontend.
    """
    monthly = (
        df.groupby("month")
        .agg(
            total_in=("paid_in", "sum"),
            total_out=("withdrawn", "sum"),
            transactions=("receipt_no", "count"),
        )
        .reset_index()
    )
    monthly["net"] = monthly["total_in"] - monthly["total_out"]
    monthly = monthly.round(2)
    return monthly.to_dict(orient="records")


def get_top_transactions(df: pd.DataFrame, n: int = 10) -> dict:
    """Largest individual credits and debits."""
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


def get_spending_by_category(df: pd.DataFrame) -> list[dict]:
    """Total withdrawn per category — for a pie/donut chart."""
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


def get_spending_by_day_of_week(df: pd.DataFrame) -> list[dict]:
    """Average spending per day of the week — useful for behaviour insights."""
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    result = (
        df[df["withdrawn"] > 0]
        .groupby("day_of_week")["withdrawn"]
        .agg(["sum", "mean", "count"])
        .reindex(order)
        .reset_index()
        .rename(columns={"sum": "total", "mean": "average", "count": "transactions"})
        .round(2)
        .fillna(0)
    )
    return result.to_dict(orient="records")


def get_balance_trend(df: pd.DataFrame) -> list[dict]:
    """Daily closing balance — for a line chart."""
    trend = (
        df.groupby(df["date"].dt.date)["balance"]
        .last()
        .reset_index()
        .rename(columns={"date": "date", "balance": "closing_balance"})
    )
    trend["date"] = trend["date"].astype(str)
    trend["closing_balance"] = trend["closing_balance"].round(2)
    return trend.to_dict(orient="records")


def run_full_analysis(df: pd.DataFrame) -> dict:
    """
    Master function that runs all analyses and returns a single dict.
    Called by the /analyze endpoint in main.py.
    """
    return {
        "overview":             get_overview(df),
        "monthly_summary":      get_monthly_summary(df),
        "top_transactions":     get_top_transactions(df),
        "spending_by_category": get_spending_by_category(df),
        "spending_by_day":      get_spending_by_day_of_week(df),
        "balance_trend":        get_balance_trend(df),
    }