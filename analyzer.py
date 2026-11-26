import calendar
import os
import tempfile
from datetime import datetime

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from database import get_all_expenses, get_categories

REPORTS_DIR = "reports"


def get_dataframe(month_filter=None):
    rows = get_all_expenses(month_filter=month_filter)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["amount"] = df["amount"].astype(float)
    df["date_dt"] = pd.to_datetime(df["date"])
    df["month"] = df["date_dt"].dt.strftime("%Y-%m")
    df["day"] = df["date_dt"].dt.day
    return df


def generate_spending_summary(month_filter=None):
    """
    Step 4: Generate overall or filtered spending summaries using Pandas.
    Returns a dictionary with key metrics and category/payment breakdowns.
    """
    df = get_dataframe(month_filter=month_filter)
    if df.empty:
        return None

    total_spent = df["amount"].sum()
    tx_count = len(df)
    avg_tx = df["amount"].mean()
    median_tx = df["amount"].median()

    daily_totals = df.groupby("date")["amount"].sum()
    avg_daily = daily_totals.mean()
    highest_day = daily_totals.idxmax()
    highest_day_val = daily_totals.max()

    # Category summary
    cat_group = (
        df.groupby("category")["amount"]
        .agg(total="sum", count="count", mean="mean")
        .sort_values(by="total", ascending=False)
        .reset_index()
    )
    cat_group["percentage"] = (cat_group["total"] / total_spent) * 100

    # Payment method summary
    pay_group = (
        df.groupby("payment_method")["amount"]
        .agg(total="sum", count="count")
        .sort_values(by="total", ascending=False)
        .reset_index()
    )
    pay_group["percentage"] = (pay_group["total"] / total_spent) * 100

    return {
        "scope": month_filter if month_filter else "All Time",
        "total_spent": round(total_spent, 2),
        "transaction_count": int(tx_count),
        "avg_per_transaction": round(avg_tx, 2),
        "median_transaction": round(median_tx, 2),
        "active_days": int(len(daily_totals)),
        "avg_daily_spend": round(avg_daily, 2),
        "highest_spending_date": highest_day,
        "highest_spending_day_total": round(highest_day_val, 2),
        "by_category": cat_group.to_dict(orient="records"),
        "by_payment": pay_group.to_dict(orient="records"),
    }


def detect_anomalies(df, z_threshold=1.5):
    """
    Flags unusually high expenses within each category using Z-score
    computed against historical category baselines.
    """
    full_df = get_dataframe()
    if full_df.empty:
        full_df = df

    cat_stats = {}
    for cat, grp in full_df.groupby("category"):
        if len(grp) >= 3:
            cat_stats[cat] = (grp["amount"].mean(), grp["amount"].std(ddof=0))

    anomalies = []
    for _, row in df.iterrows():
        cat = row["category"]
        if cat not in cat_stats:
            continue
        mean_val, std_val = cat_stats[cat]
        if std_val == 0:
            continue
        z = (row["amount"] - mean_val) / std_val
        if z >= z_threshold and row["amount"] > 1000:
            anomalies.append({
                "id": int(row["id"]),
                "date": row["date"],
                "category": cat,
                "amount": round(float(row["amount"]), 2),
                "description": row["description"],
                "z_score": round(float(z), 2),
                "category_avg": round(float(mean_val), 2),
            })
    return sorted(anomalies, key=lambda x: x["z_score"], reverse=True)


def forecast_monthly_spend(df, year_month):
    """
    Uses simple linear regression (y = m*x + c) on cumulative daily spending
    to estimate total spending by the end of the given month.
    """
    year, month = map(int, year_month.split("-"))
    days_in_month = calendar.monthrange(year, month)[1]

    daily = df.groupby("day")["amount"].sum().reindex(range(1, days_in_month + 1), fill_value=0.0)
    last_recorded_day = int(df["day"].max())

    observed_days = np.arange(1, last_recorded_day + 1)
    cumulative_spend = daily.iloc[:last_recorded_day].cumsum().values

    if len(observed_days) < 2:
        return round(float(df["amount"].sum()), 2), round(float(df["amount"].sum()), 2)

    # Fit first-degree polynomial (linear trend)
    slope, intercept = np.polyfit(observed_days, cumulative_spend, 1)
    projected_total = slope * days_in_month + intercept
    current_total = float(df["amount"].sum())

    # Projected total cannot be less than what is already spent
    projected_total = max(projected_total, current_total)
    return round(projected_total, 2), round(float(slope), 2)


def generate_monthly_report(year_month):
    """
    Step 5: Build a detailed monthly report including budget comparison,
    month-over-month trend, anomaly detection, and linear spend forecast.
    """
    df = get_dataframe(month_filter=year_month)
    if df.empty:
        return None

    summary = generate_spending_summary(month_filter=year_month)
    budgets = {c["name"]: float(c["monthly_budget"]) for c in get_categories()}

    budget_table = []
    total_budget = sum(budgets.values())

    spent_by_cat = {item["category"]: item["total"] for item in summary["by_category"]}
    all_cats = list(dict.fromkeys(list(budgets.keys()) + list(spent_by_cat.keys())))

    for cat in all_cats:
        spent = round(spent_by_cat.get(cat, 0.0), 2)
        b_limit = round(budgets.get(cat, 0.0), 2)
        if b_limit == 0 and spent == 0:
            continue
        diff = round(b_limit - spent, 2)
        pct_used = round((spent / b_limit) * 100, 1) if b_limit > 0 else 0.0

        if b_limit == 0:
            status = "No Limit"
        elif spent > b_limit:
            status = "OVER BUDGET"
        elif pct_used >= 85.0:
            status = "Near Limit"
        else:
            status = "On Track"

        budget_table.append({
            "category": cat,
            "budget": b_limit,
            "spent": spent,
            "remaining": diff,
            "pct_used": pct_used,
            "status": status,
        })

    # Previous month comparison
    dt = datetime.strptime(year_month, "%Y-%m")
    prev_year = dt.year if dt.month > 1 else dt.year - 1
    prev_month = dt.month - 1 if dt.month > 1 else 12
    prev_ym = f"{prev_year:04d}-{prev_month:02d}"

    prev_df = get_dataframe(month_filter=prev_ym)
    prev_total = round(float(prev_df["amount"].sum()), 2) if not prev_df.empty else None
    mom_change_pct = None
    if prev_total and prev_total > 0:
        mom_change_pct = round(((summary["total_spent"] - prev_total) / prev_total) * 100, 1)

    projected_total, daily_trend_rate = forecast_monthly_spend(df, year_month)
    anomalies = detect_anomalies(df)

    return {
        "year_month": year_month,
        "summary": summary,
        "total_budget": round(total_budget, 2),
        "budget_table": budget_table,
        "previous_month": prev_ym,
        "previous_month_total": prev_total,
        "mom_change_pct": mom_change_pct,
        "projected_end_of_month": projected_total,
        "daily_burn_rate": daily_trend_rate,
        "anomalies": anomalies,
    }


def get_monthly_comparison_table():
    df = get_dataframe()
    if df.empty:
        return []

    monthly = (
        df.groupby("month")
        .agg(
            total=("amount", "sum"),
            count=("id", "count"),
            avg_tx=("amount", "mean"),
        )
        .sort_index()
        .reset_index()
    )

    # Top category per month
    top_cats = (
        df.groupby(["month", "category"])["amount"]
        .sum()
        .reset_index()
        .sort_values(["month", "amount"], ascending=[True, False])
        .drop_duplicates(subset=["month"])
        .set_index("month")["category"]
        .to_dict()
    )

    results = []
    prev_val = None
    for _, row in monthly.iterrows():
        m = row["month"]
        tot = round(float(row["total"]), 2)
        change_str = "-"
        if prev_val is not None and prev_val > 0:
            pct = ((tot - prev_val) / prev_val) * 100
            sign = "+" if pct >= 0 else ""
            change_str = f"{sign}{pct:.1f}%"
        prev_val = tot

        results.append({
            "month": m,
            "total": tot,
            "transactions": int(row["count"]),
            "avg_tx": round(float(row["avg_tx"]), 2),
            "top_category": top_cats.get(m, "N/A"),
            "mom_change": change_str,
        })

    return results


def export_monthly_report_files(year_month):
    """
    Saves a formatted text report and a 2-panel Matplotlib chart PNG
    to the reports/ directory.
    """
    report = generate_monthly_report(year_month)
    if not report:
        return None, None

    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)

    df = get_dataframe(month_filter=year_month)
    txt_path = os.path.join(REPORTS_DIR, f"monthly_report_{year_month}.txt")
    img_path = os.path.join(REPORTS_DIR, f"monthly_report_{year_month}.png")

    # 1. Write text report
    s = report["summary"]
    lines = [
        f"EXPENSE TRACKER - MONTHLY REPORT ({year_month})",
        "=" * 64,
        f"Generated on       : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Total Spent        : Rs. {s['total_spent']:,.2f}",
        f"Monthly Budget     : Rs. {report['total_budget']:,.2f}",
        f"Transactions       : {s['transaction_count']} across {s['active_days']} active days",
        f"Daily Average      : Rs. {s['avg_daily_spend']:,.2f}",
        f"Peak Spending Day  : {s['highest_spending_date']} (Rs. {s['highest_spending_day_total']:,.2f})",
        f"Projected Month End: Rs. {report['projected_end_of_month']:,.2f} (Trend: ~Rs. {report['daily_burn_rate']:,.2f}/day)",
    ]
    if report["mom_change_pct"] is not None:
        sign = "+" if report["mom_change_pct"] >= 0 else ""
        lines.append(
            f"Vs Previous Month  : {sign}{report['mom_change_pct']}% (Prev: Rs. {report['previous_month_total']:,.2f})"
        )

    lines.append("\nCATEGORY BREAKDOWN & BUDGET STATUS")
    lines.append("-" * 64)
    lines.append(f"{'Category':<20} {'Budget (Rs)':>12} {'Spent (Rs)':>12} {'Used %':>8} {'Status':>12}")
    lines.append("-" * 64)
    for b in report["budget_table"]:
        lines.append(
            f"{b['category']:<20} {b['budget']:>12,.2f} {b['spent']:>12,.2f} {b['pct_used']:>7.1f}% {b['status']:>12}"
        )

    if report["anomalies"]:
        lines.append("\nUNUSUAL / HIGH EXPENSE ALERTS (Z-Score Anomaly Check)")
        lines.append("-" * 64)
        for a in report["anomalies"]:
            lines.append(
                f"- [{a['date']}] {a['category']}: Rs. {a['amount']:,.2f} ({a['description']}) "
                f"| Cat Avg: Rs. {a['category_avg']:,.2f} (Z={a['z_score']})"
            )

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # 2. Create visual charts using Matplotlib
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2))
    fig.suptitle(f"Monthly Expense Analysis - {year_month}", fontsize=14, fontweight="bold")

    # Left subplot: Category Spend vs Budget horizontal bar chart
    cats = [b["category"] for b in report["budget_table"]][::-1]
    spent_vals = [b["spent"] for b in report["budget_table"]][::-1]
    budget_vals = [b["budget"] for b in report["budget_table"]][::-1]

    y_pos = np.arange(len(cats))
    bar_height = 0.38

    ax1.barh(y_pos - bar_height / 2, spent_vals, height=bar_height, label="Actual Spent", color="#2b5c8f")
    ax1.barh(y_pos + bar_height / 2, budget_vals, height=bar_height, label="Monthly Budget", color="#b0c4de", alpha=0.85)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(cats, fontsize=9)
    ax1.set_xlabel("Amount (Rs.)")
    ax1.set_title("Category Spending vs. Budget")
    ax1.legend(loc="lower right", frameon=True)
    ax1.grid(axis="x", linestyle="--", alpha=0.4)

    # Right subplot: Cumulative Daily Spending & Linear Trend Line
    year, month = map(int, year_month.split("-"))
    days_in_month = calendar.monthrange(year, month)[1]
    last_day = int(df["day"].max())

    daily_series = df.groupby("day")["amount"].sum().reindex(range(1, last_day + 1), fill_value=0.0)
    cum_series = daily_series.cumsum()

    days_x = np.arange(1, last_day + 1)
    ax2.plot(days_x, cum_series.values, marker="o", markersize=4, linewidth=2, color="#1f77b4", label="Cumulative Spend")

    if len(days_x) >= 2:
        slope, intercept = np.polyfit(days_x, cum_series.values, 1)
        full_days = np.arange(1, days_in_month + 1)
        trend_y = slope * full_days + intercept
        ax2.plot(full_days, trend_y, linestyle="--", color="#d95f02", label="Linear Forecast")

    if report["total_budget"] > 0:
        ax2.axhline(report["total_budget"], color="#d62728", linestyle=":", linewidth=1.5, label="Total Budget Cap")

    ax2.set_xlim(1, days_in_month)
    ax2.set_xlabel("Day of Month")
    ax2.set_ylabel("Cumulative Spend (Rs.)")
    ax2.set_title("Cumulative Spending Trajectory & Forecast")
    ax2.legend(loc="upper left", frameon=True)
    ax2.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()
    plt.savefig(img_path, dpi=150)
    plt.close(fig)

    return txt_path, img_path
