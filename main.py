import sys
from datetime import datetime
from analyzer import (
    export_monthly_report_files,
    generate_monthly_report,
    generate_spending_summary,
    get_monthly_comparison_table,
)
from categorizer import SmartCategorizer
from database import (
    add_expense,
    add_or_update_category,
    delete_expense,
    export_to_csv,
    get_all_expenses,
    get_categories,
    import_from_csv,
    init_db,
)
from seed_data import seed_if_empty


def print_line(char="-", width=72):
    print(char * width)


def prompt_add_expense(categorizer):
    print("\n--- STEP 1 & 2: ADD & CATEGORIZE EXPENSE ---")
    today = datetime.now().strftime("%Y-%m-%d")
    date_in = input(f"Date (YYYY-MM-DD) [default: {today}]: ").strip()
    if not date_in:
        date_in = today
    else:
        try:
            datetime.strptime(date_in, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return

    amt_in = input("Amount (Rs.): ").strip()
    try:
        amount = float(amt_in)
        if amount <= 0:
            print("Amount must be greater than zero.")
            return
    except ValueError:
        print("Invalid amount entered.")
        return

    description = input("Description (e.g., 'Canteen lunch', 'Bus fare'): ").strip()

    # Use Naive Bayes categorizer to suggest a category from description
    predicted_cat, confidence = categorizer.predict(description)
    categories = get_categories()

    print("\nAvailable Categories:")
    for idx, c in enumerate(categories, start=1):
        marker = " <-- Suggested" if c["name"] == predicted_cat and confidence > 0 else ""
        print(f"  {idx}. {c['name']} (Budget: Rs. {c['monthly_budget']:,.0f}){marker}")

    if confidence > 0:
        cat_prompt = f"Select category number or press Enter for '{predicted_cat}' ({confidence}% match): "
    else:
        cat_prompt = "Select category number (or type a new category name): "

    cat_choice = input(cat_prompt).strip()
    if not cat_choice:
        chosen_cat = predicted_cat
    elif cat_choice.isdigit() and 1 <= int(cat_choice) <= len(categories):
        chosen_cat = categories[int(cat_choice) - 1]["name"]
    else:
        chosen_cat = cat_choice
        add_or_update_category(chosen_cat, 0.0)

    pay_in = input("Payment Method (1: Cash, 2: Card, 3: Bank Transfer) [default: 1]: ").strip()
    pay_map = {"1": "Cash", "2": "Card", "3": "Bank Transfer"}
    payment_method = pay_map.get(pay_in, "Cash")

    exp_id = add_expense(date_in, amount, chosen_cat, description, payment_method)
    categorizer.train()  # Update model with the newly added record
    print(f"\n[Saved] Expense #{exp_id} recorded under '{chosen_cat}' (Rs. {amount:,.2f}).")


def prompt_manage_categories(categorizer):
    print("\n--- STEP 2: CATEGORY & BUDGET MANAGEMENT ---")
    categories = get_categories()
    print_line()
    print(f"{'ID':<4} {'Category Name':<24} {'Monthly Budget (Rs.)':>20}")
    print_line()
    for c in categories:
        print(f"{c['id']:<4} {c['name']:<24} {c['monthly_budget']:>20,.2f}")
    print_line()

    print("\nOptions:")
    print("  1. Add a new category or update monthly budget")
    print("  2. Test auto-categorizer with a sample description")
    print("  3. Back to main menu")

    sub = input("Choose an option: ").strip()
    if sub == "1":
        name = input("Category name: ").strip()
        if not name:
            return
        b_str = input("Monthly budget limit in Rs. (0 for none): ").strip()
        try:
            budget = float(b_str) if b_str else 0.0
            add_or_update_category(name, budget)
            print(f"Category '{name}' updated with monthly budget Rs. {budget:,.2f}.")
        except ValueError:
            print("Invalid budget amount.")
    elif sub == "2":
        sample_desc = input("Enter a sample expense description: ").strip()
        cat, conf = categorizer.predict(sample_desc)
        print(f"Predicted Category: {cat} (Confidence score: {conf}%)")


def prompt_storage_and_records(categorizer):
    print("\n--- STEP 3: VIEW RECORDS & CSV / SQLITE STORAGE ---")
    print("  1. View recent expenses (all or filtered by month)")
    print("  2. Export records to CSV file")
    print("  3. Import records from CSV file")
    print("  4. Delete an expense by ID")
    print("  5. Back to main menu")

    choice = input("Select an option: ").strip()
    if choice == "1":
        m_filter = input("Filter by month (YYYY-MM) or press Enter for all: ").strip() or None
        rows = get_all_expenses(month_filter=m_filter)
        if not rows:
            print("No matching expense records found.")
            return
        print()
        print_line("=", 82)
        print(f"{'ID':<4} {'Date':<11} {'Category':<19} {'Amount (Rs)':>12} {'Method':<14} {'Description'}")
        print_line("-", 82)
        for r in rows[:30]:
            print(
                f"{r['id']:<4} {r['date']:<11} {r['category']:<19} "
                f"{r['amount']:>12,.2f} {r['payment_method']:<14} {r['description']}"
            )
        print_line("=", 82)
        if len(rows) > 30:
            print(f"Showing latest 30 of {len(rows)} records.")
    elif choice == "2":
        path_in = input("CSV output path [default: data/expenses_export.csv]: ").strip()
        if not path_in:
            path_in = "data/expenses_export.csv"
        count, out_path = export_to_csv(path_in)
        print(f"Exported {count} records to '{out_path}'.")
    elif choice == "3":
        path_in = input("Enter CSV file path to import: ").strip()
        try:
            count = import_from_csv(path_in)
            categorizer.train()
            print(f"Successfully imported {count} records into SQLite database.")
        except FileNotFoundError as e:
            print(e)
    elif choice == "4":
        id_in = input("Enter Expense ID to delete: ").strip()
        if id_in.isdigit():
            if delete_expense(int(id_in)):
                categorizer.train()
                print(f"Expense #{id_in} deleted.")
            else:
                print(f"No expense found with ID {id_in}.")


def display_spending_summary(month_filter=None):
    summary = generate_spending_summary(month_filter=month_filter)
    if not summary:
        print("No expense data available for the selected period.")
        return

    print()
    print_line("=", 72)
    print(f"SPENDING SUMMARY ({summary['scope']})")
    print_line("=", 72)
    print(f"  Total Spending       : Rs. {summary['total_spent']:,.2f}")
    print(f"  Total Transactions   : {summary['transaction_count']} across {summary['active_days']} active days")
    print(f"  Average per Expense  : Rs. {summary['avg_per_transaction']:,.2f} (Median: Rs. {summary['median_transaction']:,.2f})")
    print(f"  Daily Spending Avg   : Rs. {summary['avg_daily_spend']:,.2f}")
    print(f"  Highest Spending Day : {summary['highest_spending_date']} (Rs. {summary['highest_spending_day_total']:,.2f})")

    print("\nCategory Breakdown:")
    print_line("-", 72)
    print(f"{'Category':<20} {'Txns':>5} {'Total (Rs.)':>14} {'Share':>8}  {'Distribution'}")
    print_line("-", 72)
    for item in summary["by_category"]:
        bar_len = int(round(item["percentage"] / 5))
        bar = "#" * bar_len
        print(
            f"{item['category']:<20} {item['count']:>5} "
            f"{item['total']:>14,.2f} {item['percentage']:>7.1f}%  {bar}"
        )
    print_line("-", 72)

    print("\nPayment Method Split:")
    for p in summary["by_payment"]:
        print(f"  - {p['payment_method']:<15}: Rs. {p['total']:>10,.2f} ({p['percentage']:.1f}% | {p['count']} txns)")
    print_line("=", 72)


def display_monthly_reports(target_month=None):
    comp = get_monthly_comparison_table()
    if not comp:
        print("No data available to build monthly reports.")
        return

    print("\n--- STEP 5: MONTHLY OVERVIEW & COMPARISON ---")
    print_line("=", 76)
    print(f"{'Month':<10} {'Total (Rs.)':>14} {'Txns':>6} {'Avg Tx (Rs.)':>14} {'MoM Change':>12}  {'Top Category'}")
    print_line("-", 76)
    for row in comp:
        print(
            f"{row['month']:<10} {row['total']:>14,.2f} {row['transactions']:>6} "
            f"{row['avg_tx']:>14,.2f} {row['mom_change']:>12}  {row['top_category']}"
        )
    print_line("=", 76)

    if not target_month:
        latest_month = comp[-1]["month"]
        target_month = input(f"\nEnter month for detailed report (YYYY-MM) [default: {latest_month}]: ").strip()
        if not target_month:
            target_month = latest_month

    report = generate_monthly_report(target_month)
    if not report:
        print(f"No records found for month '{target_month}'.")
        return

    s = report["summary"]
    print()
    print_line("=", 76)
    print(f"DETAILED MONTHLY REPORT: {target_month}")
    print_line("=", 76)
    print(f"  Total Spent          : Rs. {s['total_spent']:,.2f}  (Monthly Budget: Rs. {report['total_budget']:,.2f})")
    if report["mom_change_pct"] is not None:
        sign = "+" if report["mom_change_pct"] >= 0 else ""
        print(
            f"  Month-over-Month     : {sign}{report['mom_change_pct']}% compared to {report['previous_month']} "
            f"(Rs. {report['previous_month_total']:,.2f})"
        )
    print(
        f"  End-of-Month Forecast: Rs. {report['projected_end_of_month']:,.2f} "
        f"(Linear trend rate: ~Rs. {report['daily_burn_rate']:,.2f}/day)"
    )

    print("\nBudget vs. Actual by Category:")
    print_line("-", 76)
    print(f"{'Category':<20} {'Budget (Rs)':>13} {'Spent (Rs)':>13} {'Remaining':>13} {'Used %':>8}  {'Status'}")
    print_line("-", 76)
    for b in report["budget_table"]:
        print(
            f"{b['category']:<20} {b['budget']:>13,.2f} {b['spent']:>13,.2f} "
            f"{b['remaining']:>13,.2f} {b['pct_used']:>7.1f}%  {b['status']}"
        )
    print_line("-", 76)

    if report["anomalies"]:
        print("\nUnusual Spending Alerts (Statistical Z-Score Outlier Detection):")
        for a in report["anomalies"]:
            print(
                f"  [!] {a['date']} | {a['category']} - Rs. {a['amount']:,.2f} ({a['description']}) "
                f"[Cat avg: Rs. {a['category_avg']:,.2f}, Z={a['z_score']}]"
            )

    txt_path, img_path = export_monthly_report_files(target_month)
    print(f"\nReport files saved to:")
    print(f"  - Text Summary : {txt_path}")
    print(f"  - Visual Chart : {img_path}")
    print_line("=", 76)


def run_demo():
    """
    Runs a complete non-interactive demonstration of all 5 task workflow steps
    and exports the CSV and monthly report files.
    """
    init_db()
    seeded = seed_if_empty()
    categorizer = SmartCategorizer()

    print("========================================================================")
    print("  EXPENSE TRACKER SYSTEM - WORKFLOW DEMONSTRATION")
    print("========================================================================")
    if seeded:
        print(f"Initialized SQLite database with {seeded} sample records.")

    # Step 2 demo: Smart auto-categorization check
    sample_inputs = [
        "Canteen chicken kottu and iced coffee",
        "PickMe tuk ride to university",
        "Dialog 4G anytime data reload",
        "Photocopy and binding for AI project report",
    ]
    print("\n--- Auto-Categorizer Predictions (Naive Bayes Model) ---")
    for text in sample_inputs:
        cat, conf = categorizer.predict(text)
        print(f"  '{text}' -> {cat} ({conf}%)")

    # Step 3 demo: Export to CSV
    count, csv_path = export_to_csv("data/expenses_export.csv")
    print(f"\n--- Storage Sync ---")
    print(f"  SQLite DB : data/expenses.db ({count} records)")
    print(f"  CSV Export: {csv_path} ({count} records)")

    # Step 4 demo: Spending summary
    display_spending_summary(month_filter=None)

    # Step 5 demo: Monthly reports for all seeded months
    for m in ["2026-08", "2026-09"]:
        export_monthly_report_files(m)
    display_monthly_reports(target_month="2026-10")


def main():
    if "--demo" in sys.argv:
        run_demo()
        return

    init_db()
    seeded = seed_if_empty()
    categorizer = SmartCategorizer()

    print("\n========================================================")
    print("             PERSONAL EXPENSE TRACKER SYSTEM            ")
    print("========================================================")
    if seeded > 0:
        print(f"[Info] Loaded {seeded} sample expense records into data/expenses.db.")

    while True:
        print("\nMain Menu:")
        print("  1. Add New Expense (Step 1 & 2)")
        print("  2. Manage Categories & Budgets (Step 2)")
        print("  3. View Records / CSV Export & Import (Step 3)")
        print("  4. Generate Spending Summary (Step 4)")
        print("  5. Display Monthly Reports & Charts (Step 5)")
        print("  0. Exit")

        choice = input("\nEnter your choice (0-5): ").strip()

        if choice == "1":
            prompt_add_expense(categorizer)
        elif choice == "2":
            prompt_manage_categories(categorizer)
        elif choice == "3":
            prompt_storage_and_records(categorizer)
        elif choice == "4":
            m_in = input("Enter month (YYYY-MM) or press Enter for All-Time summary: ").strip() or None
            display_spending_summary(month_filter=m_in)
        elif choice == "5":
            display_monthly_reports()
        elif choice == "0":
            print("Exiting Expense Tracker. Goodbye!")
            break
        else:
            print("Invalid option. Please choose between 0 and 5.")


if __name__ == "__main__":
    main()
