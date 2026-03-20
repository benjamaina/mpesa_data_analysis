"""
dummy_data.py
-------------
Generates a realistic fake M-Pesa statement and saves it as:
  - dummy_statement.csv
  - dummy_statement.xlsx

The data mimics the exact column structure of a real Safaricom
M-Pesa statement:
  Receipt No | Completion Time | Details | Transaction Status | Paid In | Withdrawn | Balance

Usage:
    python dummy_data.py

Output files will be saved in the same directory as this script.
"""

import random
import string
import pandas as pd
from datetime import datetime, timedelta


# ── Realistic transaction templates ──────────────────────────────────────────

SEND_MONEY_NAMES = [
    "John Kamau", "Mary Wanjiku", "Peter Otieno", "Grace Akinyi",
    "James Mwangi", "Alice Wambui", "David Kipchoge", "Faith Njeri",
    "Samuel Odhiambo", "Ruth Muthoni", "Brian Kimani", "Carol Nyambura",
    "Kevin Ochieng", "Diana Waithera", "Paul Njenga", "Esther Waweru",
]

BUSINESSES = [
    ("Kenya Power", "KPLC"),
    ("Nairobi Water", "NAIROBI WATER"),
    ("Safaricom Home Fibre", "SAFARICOM HOME"),
    ("DSTV Kenya", "DSTV"),
    ("Zuku Broadband", "ZUKU"),
    ("NHIF", "NHIF NAIROBI"),
    ("KRA iTax", "KRA"),
    ("Java House", "JAVA HOUSE TILL 123456"),
    ("Naivas Supermarket", "NAIVAS TILL 654321"),
    ("Carrefour Kenya", "CARREFOUR TILL 789012"),
    ("Quickmart", "QUICKMART TILL 345678"),
    ("Equity Bank", "EQUITY BANK"),
    ("KCB Bank", "KCB BANK"),
    ("Cooperative Bank", "CO-OP BANK"),
    ("Mama Pima Kiosk", "MAMA PIMA TILL 111222"),
    ("Shell Petrol Station", "SHELL TILL 999888"),
    ("Uber Kenya", "UBER PAYMENTS"),
    ("Bolt Rides", "BOLT PAYMENTS"),
]

AGENTS = [
    "Agent John Gitonga (0722001122)",
    "Agent Mary Achieng (0711223344)",
    "Agent Samwel Wekesa (0733445566)",
    "Agent Purity Njoroge (0700112233)",
    "Agent Hassan Omar (0722334455)",
]

AIRTIME_NUMBERS = [
    "0712345678", "0722987654", "0733111222",
    "0700556677", "0711998877",
]


# ── Receipt number generator ──────────────────────────────────────────────────

def _receipt_no() -> str:
    """Generate a realistic M-Pesa receipt number e.g. QGH3X1Y2Z0"""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=10))


# ── Transaction builders ──────────────────────────────────────────────────────

def _send_money(balance: float) -> dict:
    amount = round(random.uniform(100, 5000), 0)
    name   = random.choice(SEND_MONEY_NAMES)
    number = f"07{random.randint(10,99)}{random.randint(100000,999999)}"
    return {
        "details":   f"Sent to {name} {number}",
        "paid_in":   0.0,
        "withdrawn": amount,
        "balance":   max(0, balance - amount),
    }


def _receive_money(balance: float) -> dict:
    amount = round(random.uniform(200, 20000), 0)
    name   = random.choice(SEND_MONEY_NAMES)
    number = f"07{random.randint(10,99)}{random.randint(100000,999999)}"
    return {
        "details":   f"Received from {name} {number}",
        "paid_in":   amount,
        "withdrawn": 0.0,
        "balance":   balance + amount,
    }


def _paybill(balance: float) -> dict:
    biz_name, biz_ref = random.choice(BUSINESSES[:10])  # first 10 are bills
    amount = round(random.uniform(500, 8000), 0)
    account = f"ACC{random.randint(1000000, 9999999)}"
    return {
        "details":   f"Pay Bill to {biz_ref} Account {account}",
        "paid_in":   0.0,
        "withdrawn": amount,
        "balance":   max(0, balance - amount),
    }


def _buy_goods(balance: float) -> dict:
    _, till_ref = random.choice(BUSINESSES[10:])
    amount = round(random.uniform(50, 3000), 0)
    return {
        "details":   f"Buy Goods {till_ref}",
        "paid_in":   0.0,
        "withdrawn": amount,
        "balance":   max(0, balance - amount),
    }


def _withdraw(balance: float) -> dict:
    amount = round(random.choice([500, 1000, 1500, 2000, 2500, 3000, 5000, 10000]), 0)
    agent  = random.choice(AGENTS)
    return {
        "details":   f"Withdraw Cash from {agent}",
        "paid_in":   0.0,
        "withdrawn": amount,
        "balance":   max(0, balance - amount),
    }


def _deposit(balance: float) -> dict:
    amount = round(random.choice([1000, 2000, 3000, 5000, 10000, 20000]), 0)
    agent  = random.choice(AGENTS)
    return {
        "details":   f"Deposit from {agent}",
        "paid_in":   amount,
        "withdrawn": 0.0,
        "balance":   balance + amount,
    }


def _airtime(balance: float) -> dict:
    amount = random.choice([10, 20, 50, 100, 200])
    number = random.choice(AIRTIME_NUMBERS)
    return {
        "details":   f"Buy Airtime for {number}",
        "paid_in":   0.0,
        "withdrawn": float(amount),
        "balance":   max(0, balance - amount),
    }


def _bank_transfer(balance: float) -> dict:
    _, bank_ref = random.choice(BUSINESSES[-5:])  # last few are banks
    amount = round(random.uniform(1000, 30000), 0)
    # 40% chance it's incoming (salary / transfer in)
    if random.random() < 0.4:
        return {
            "details":   f"Received from {bank_ref} Transfer",
            "paid_in":   amount,
            "withdrawn": 0.0,
            "balance":   balance + amount,
        }
    return {
        "details":   f"Transfer to {bank_ref}",
        "paid_in":   0.0,
        "withdrawn": amount,
        "balance":   max(0, balance - amount),
    }


def _fuliza(balance: float) -> dict:
    amount = round(random.uniform(50, 1000), 0)
    # 50/50 borrow vs repay
    if random.random() < 0.5:
        return {
            "details":   "Fuliza M-PESA Loan Disbursement",
            "paid_in":   amount,
            "withdrawn": 0.0,
            "balance":   balance + amount,
        }
    return {
        "details":   "Fuliza M-PESA Repayment",
        "paid_in":   0.0,
        "withdrawn": amount,
        "balance":   max(0, balance - amount),
    }


# ── Weighted transaction picker ───────────────────────────────────────────────

TRANSACTION_TYPES = [
    (_send_money,    25),   # most common
    (_buy_goods,     20),
    (_airtime,       15),
    (_receive_money, 12),
    (_withdraw,      10),
    (_paybill,        8),
    (_bank_transfer,  5),
    (_deposit,        3),
    (_fuliza,         2),
]

# Expand into a flat weighted list
_WEIGHTED_POOL = [fn for fn, weight in TRANSACTION_TYPES for _ in range(weight)]


# ── Main generator ────────────────────────────────────────────────────────────

def generate_statement(
    num_transactions: int = 200,
    start_date: datetime = datetime(2024, 7, 1),
    end_date:   datetime = datetime(2025, 3, 31),
    opening_balance: float = 12_500.00,
) -> pd.DataFrame:
    """
    Generate a fake M-Pesa statement DataFrame.

    Args:
        num_transactions: How many transactions to generate.
        start_date:       Start of the statement period.
        end_date:         End of the statement period.
        opening_balance:  Starting M-Pesa balance in KSh.

    Returns:
        DataFrame with M-Pesa statement columns.
    """
    total_seconds = int((end_date - start_date).total_seconds())
    timestamps    = sorted([
        start_date + timedelta(seconds=random.randint(0, total_seconds))
        for _ in range(num_transactions)
    ])

    rows    = []
    balance = opening_balance

    for ts in timestamps:
        # Low balance → bias towards receive/deposit
        if balance < 500:
            fn = random.choice([_receive_money, _deposit, _bank_transfer])
        else:
            fn = random.choice(_WEIGHTED_POOL)

        tx = fn(balance)
        balance = tx["balance"]

        rows.append({
            "Receipt No":           _receipt_no(),
            "Completion Time":      ts.strftime("%d/%m/%Y %H:%M:%S"),
            "Details":              tx["details"],
            "Transaction Status":   "Completed",
            "Paid In":              f"{tx['paid_in']:,.2f}" if tx["paid_in"]   > 0 else "",
            "Withdrawn":            f"{tx['withdrawn']:,.2f}" if tx["withdrawn"] > 0 else "",
            "Balance":              f"{tx['balance']:,.2f}",
        })

    return pd.DataFrame(rows)


# ── Save to files ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔄 Generating fake M-Pesa statement...")

    df = generate_statement(
        num_transactions=250,
        start_date=datetime(2024, 7, 1),
        end_date=datetime(2025, 3, 31),
        opening_balance=12_500.00,
    )

    # Save as CSV
    csv_path = "dummy_statement.csv"
    df.to_csv(csv_path, index=False)
    print(f"✅ CSV saved  → {csv_path}  ({len(df)} transactions)")

    # Save as Excel
    xlsx_path = "dummy_statement.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"✅ Excel saved → {xlsx_path}  ({len(df)} transactions)")

    print("\nFirst 5 rows preview:")
    print(df.head().to_string(index=False))