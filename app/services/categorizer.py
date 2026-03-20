"""
categorizer.py
--------------
Assigns a human-readable category to every transaction based on
the 'details' text (the description column from the statement).

Categories (you can extend these freely):
  - Send Money
  - Receive Money
  - Buy Goods (Till)
  - Pay Bill
  - Withdraw (Agent)
  - Deposit (Agent)
  - Airtime
  - Fuliza / Loans
  - Bank Transfer
  - Reversal
  - Other
"""

import re
import pandas as pd


# ── Category rules ────────────────────────────────────────────────────────────
# Each rule is (category_name, list_of_regex_patterns).
# Patterns are matched against the lowercased 'details' string.
# Order matters — first match wins.

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Airtime", [
        r"airtime",
        r"top.?up",
        r"bundle",
        r"data bundle",
    ]),
    ("Fuliza / Loans", [
        r"fuliza",
        r"m-shwari",
        r"mshwari",
        r"kcb m-pesa",
        r"loan",
        r"okoa",
        r"stawi",
    ]),
    ("Pay Bill", [
        r"paybill",
        r"pay bill",
        r"business payment",
        r"utility",
        r"kplc",
        r"nairobi water",
        r"safaricom home",
        r"dstv",
        r"gotv",
        r"zuku",
        r"nhif",
        r"nssf",
        r"kra",
    ]),
    ("Buy Goods (Till)", [
        r"buy goods",
        r"merchant payment",
        r"till",
        r"lipa na m.?pesa",
    ]),
    ("Withdraw (Agent)", [
        r"withdraw",
        r"withdrawal",
        r"agent",
        r"cash out",
    ]),
    ("Deposit (Agent)", [
        r"deposit",
        r"cash in",
        r"agent deposit",
    ]),
    ("Bank Transfer", [
        r"bank",
        r"equity",
        r"kcb",
        r"cooperative",
        r"co.op",
        r"stanchart",
        r"absa",
        r"i&m",
        r"ncba",
        r"dtb",
        r"transfer to",
        r"transfer from",
    ]),
    ("Reversal", [
        r"reversal",
        r"reversed",
        r"refund",
    ]),
    ("Send Money", [
        r"sent to",
        r"send money",
        r"transfer",
        r"give",
    ]),
    ("Receive Money", [
        r"received from",
        r"receive",
        r"from .+",       # "from John Doe"
        r"payment received",
    ]),
]


def _match_category(details: str) -> str:
    """Return the first matching category for a transaction details string."""
    text = details.lower()
    for category, patterns in CATEGORY_RULES:
        for pattern in patterns:
            if re.search(pattern, text):
                return category
    return "Other"


def categorize_statement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main entry point.
    Adds a 'category' column to the cleaned DataFrame.

    Args:
        df: Clean DataFrame from cleaner.py

    Returns:
        Same DataFrame with a new 'category' column.
    """
    df = df.copy()
    df["category"] = df["details"].apply(_match_category)
    return df


def get_category_summary(df: pd.DataFrame) -> dict:
    """
    Returns a summary dict of spending/income by category.
    Useful for the /analyze endpoint.
    """
    summary = {}

    for category, group in df.groupby("category"):
        summary[category] = {
            "total_paid_in":   round(group["paid_in"].sum(), 2),
            "total_withdrawn": round(group["withdrawn"].sum(), 2),
            "transaction_count": len(group),
        }

    return summary