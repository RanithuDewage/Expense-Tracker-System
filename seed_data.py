from database import add_expense, export_to_csv, get_all_expenses, init_db

SAMPLE_EXPENSES = [
    # August 2026
    ("2026-08-02", 450.0, "Food & Dining", "University canteen rice and curry", "Cash"),
    ("2026-08-03", 1200.0, "Transport", "Weekly bus fare to campus", "Cash"),
    ("2026-08-05", 1950.0, "Utilities & Data", "Dialog monthly student data package", "Card"),
    ("2026-08-07", 850.0, "Education & Books", "Linear algebra tutorial printouts and binding", "Cash"),
    ("2026-08-10", 3400.0, "Food & Dining", "Keells weekly groceries and milk powder", "Card"),
    ("2026-08-12", 680.0, "Transport", "PickMe tuk ride for morning lab session", "Cash"),
    ("2026-08-15", 1500.0, "Entertainment", "Movie ticket and snacks with batchmates", "Cash"),
    ("2026-08-18", 2800.0, "Education & Books", "Used Python machine learning reference book", "Bank Transfer"),
    ("2026-08-21", 2100.0, "Food & Dining", "Dinner kottu and drinks after project group meet", "Cash"),
    ("2026-08-24", 1450.0, "Transport", "Train and bus tickets home for weekend", "Cash"),
    ("2026-08-27", 950.0, "Health & Personal", "Pharmacy vitamin C and panadol", "Cash"),
    ("2026-08-29", 3900.0, "Food & Dining", "Cargills grocery restock", "Card"),

    # September 2026
    ("2026-09-01", 520.0, "Food & Dining", "Breakfast hoppers and tea near faculty", "Cash"),
    ("2026-09-03", 1950.0, "Utilities & Data", "Dialog monthly internet reload", "Card"),
    ("2026-09-05", 1300.0, "Transport", "Bus commute to lectures", "Cash"),
    ("2026-09-08", 4200.0, "Food & Dining", "Keells supermarket groceries", "Card"),
    ("2026-09-11", 3200.0, "Education & Books", "Coursera Deep Learning specialization co-pay", "Card"),
    ("2026-09-14", 750.0, "Transport", "Uber ride back from late coding session", "Card"),
    ("2026-09-16", 600.0, "Food & Dining", "Canteen lunch and iced coffee", "Cash"),
    ("2026-09-19", 2400.0, "Utilities & Data", "Boarding room electricity bill share", "Bank Transfer"),
    ("2026-09-22", 1800.0, "Entertainment", "Spotify duo + weekend badminton court booking", "Card"),
    ("2026-09-25", 1100.0, "Health & Personal", "Haircut and personal care items", "Cash"),
    ("2026-09-28", 3650.0, "Food & Dining", "End of month grocery shopping", "Card"),

    # October 2026
    ("2026-10-02", 480.0, "Food & Dining", "Canteen rice and curry lunch", "Cash"),
    ("2026-10-04", 1950.0, "Utilities & Data", "Dialog data package renewal", "Card"),
    ("2026-10-06", 1400.0, "Transport", "Bus fare and highway ticket", "Cash"),
    ("2026-10-08", 4100.0, "Food & Dining", "Keells groceries and snacks", "Card"),
    ("2026-10-10", 650.0, "Education & Books", "Lab report color printing and stationery", "Cash"),
    ("2026-10-12", 820.0, "Transport", "PickMe ride to hackathon venue", "Card"),
    ("2026-10-15", 1250.0, "Food & Dining", "Bakery lunch and evening tea", "Cash"),
    ("2026-10-18", 4800.0, "Education & Books", "External SSD drive for datasets (shared purchase)", "Bank Transfer"),
    ("2026-10-20", 2550.0, "Utilities & Data", "Monthly electricity and water bill share", "Bank Transfer"),
    ("2026-10-22", 900.0, "Health & Personal", "Pharmacy eye drops and basic meds", "Cash"),
    ("2026-10-25", 2200.0, "Entertainment", "Batch trip contribution", "Cash"),
    ("2026-10-28", 8900.0, "Food & Dining", "Birthday treat dinner for friends at restaurant", "Card"),
]


def seed_if_empty():
    init_db()
    existing = get_all_expenses()
    if len(existing) == 0:
        for date_str, amount, category, desc, payment in SAMPLE_EXPENSES:
            add_expense(date_str, amount, category, desc, payment)
        export_to_csv("data/expenses_export.csv")
        return len(SAMPLE_EXPENSES)
    return 0


if __name__ == "__main__":
    added = seed_if_empty()
    if added > 0:
        print(f"Seeded {added} sample expense records into data/expenses.db and exported CSV.")
    else:
        print("Database already contains records. Skipping seed.")
