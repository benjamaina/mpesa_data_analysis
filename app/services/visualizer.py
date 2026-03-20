"""
visualizer.py
-------------
Generates charts and returns raw PNG bytes.
Each chart function returns bytes directly — main.py
serves them via StreamingResponse with media_type="image/png".

Charts:
  1. monthly_flow       — Money In vs Out per month (bar)
  2. spending_category  — Share of spending per category (donut)
  3. balance_trend      — Closing balance over time (line)
  4. spending_day       — Average spending by day of week (horizontal bar)
"""

import io
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

MPESA_GREEN = "#00A650"
MPESA_RED   = "#E4002B"
NEUTRAL     = "#4A90D9"
BG_COLOR    = "#F8F9FA"


def _to_png(fig: plt.Figure) -> bytes:
    """Render a matplotlib figure to raw PNG bytes and close the figure."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=130, facecolor=BG_COLOR)
    buf.seek(0)
    data = buf.read()
    plt.close(fig)
    return data


def _fmt_ksh(value, _):
    return f"KSh {value:,.0f}"


# ── Individual chart functions ────────────────────────────────────────────────

def chart_monthly_flow(monthly_summary: list[dict]) -> bytes:
    """Grouped bar: Money In vs Money Out per month."""
    df    = pd.DataFrame(monthly_summary)
    months = df["month"].tolist()
    x     = range(len(months))
    w     = 0.35

    fig, ax = plt.subplots(figsize=(11, 5), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.bar([i - w/2 for i in x], df["total_in"],  w, label="Money In",  color=MPESA_GREEN, alpha=0.85)
    ax.bar([i + w/2 for i in x], df["total_out"], w, label="Money Out", color=MPESA_RED,   alpha=0.85)
    ax.set_title("Monthly Cash Flow", fontsize=14, fontweight="bold", pad=12)
    ax.set_xticks(list(x))
    ax.set_xticklabels(months, rotation=45, ha="right", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_ksh))
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return _to_png(fig)


def chart_spending_category(spending_by_category: list[dict]) -> bytes:
    """Donut: share of total spending per category."""
    df = pd.DataFrame(spending_by_category)
    if df.empty:
        # Return a tiny placeholder PNG
        fig, ax = plt.subplots(figsize=(4, 2), facecolor=BG_COLOR)
        ax.text(0.5, 0.5, "No spending data", ha="center", va="center")
        ax.axis("off")
        return _to_png(fig)

    fig, ax = plt.subplots(figsize=(8, 8), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    wedges, texts, autotexts = ax.pie(
        df["total_spent"],
        labels=df["category"],
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.82,
        wedgeprops=dict(width=0.5),
    )
    for t in autotexts:
        t.set_fontsize(8)
    ax.set_title("Spending by Category", fontsize=14, fontweight="bold", pad=16)
    return _to_png(fig)


def chart_balance_trend(balance_trend: list[dict]) -> bytes:
    """Line: closing balance over time."""
    df = pd.DataFrame(balance_trend)
    df["date"] = pd.to_datetime(df["date"])

    fig, ax = plt.subplots(figsize=(11, 4), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.plot(df["date"], df["closing_balance"], color=MPESA_GREEN, linewidth=2)
    ax.fill_between(df["date"], df["closing_balance"], alpha=0.15, color=MPESA_GREEN)
    ax.set_title("Balance Over Time", fontsize=14, fontweight="bold", pad=12)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_ksh))
    ax.grid(linestyle="--", alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    return _to_png(fig)


def chart_spending_day(spending_by_day: list[dict]) -> bytes:
    """Horizontal bar: average spending by day of week."""
    df = pd.DataFrame(spending_by_day)

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.barh(df["day_of_week"], df["average"], color=NEUTRAL, alpha=0.85)
    ax.set_xlabel("Average Spending (KSh)")
    ax.set_title("Average Spending by Day of Week", fontsize=14, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_ksh))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.invert_yaxis()
    fig.tight_layout()
    return _to_png(fig)


# ── Chart registry ────────────────────────────────────────────────────────────

# Maps URL-safe chart name → (generator_function, analysis_key)
CHART_REGISTRY: dict[str, tuple] = {
    "monthly_flow":      (chart_monthly_flow,      "monthly_summary"),
    "spending_category": (chart_spending_category,  "spending_by_category"),
    "balance_trend":     (chart_balance_trend,      "balance_trend"),
    "spending_day":      (chart_spending_day,        "spending_by_day"),
}


def render_chart(chart_name: str, analysis: dict) -> bytes:
    """
    Look up chart_name in the registry and render it to PNG bytes.
    Raises KeyError if chart_name is unknown.
    """
    if chart_name not in CHART_REGISTRY:
        raise KeyError(f"Unknown chart '{chart_name}'. "
                       f"Available: {list(CHART_REGISTRY.keys())}")
    fn, data_key = CHART_REGISTRY[chart_name]
    return fn(analysis[data_key])