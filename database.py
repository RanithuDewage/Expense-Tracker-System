import csv
import os
import sqlite3
from datetime import datetime

DB_FOLDER = "data"
DB_PATH = os.path.join(DB_FOLDER, "expenses.db")

DEFAULT_CATEGORIES = [
    ("Food & Dining", 18000.0),
    ("Transport", 8000.0),
    ("Education & Books", 6000.0),
    ("Utilities & Data", 5000.0),
    ("Entertainment", 4000.0),
    ("Health & Personal", 3500.0),
    ("Other", 3000.0),
]


def get_connection():
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table for expense categories and monthly budget limits
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            monthly_budget REAL DEFAULT 0.0
        )
    """)

    # Main expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            payment_method TEXT DEFAULT 'Cash',
            created_at TEXT NOT NULL
        )
    """)

    # Insert default categories if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    if cursor.fetchone()["count"] == 0:
        cursor.executemany(
            "INSERT INTO categories (name, monthly_budget) VALUES (?, ?)",
            DEFAULT_CATEGORIES
        )

    conn.commit()
    conn.close()


def add_expense(date_str, amount, category, description="", payment_method="Cash"):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO expenses (date, amount, category, description, payment_method, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (date_str, float(amount), category, description.strip(), payment_method, now))

    expense_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return expense_id


def get_all_expenses(month_filter=None, category_filter=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM expenses WHERE 1=1"
    params = []

    if month_filter:
        # month_filter format: YYYY-MM
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(month_filter)

    if category_filter:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category_filter)

    query += " ORDER BY date DESC, id DESC"
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def delete_expense(expense_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, monthly_budget FROM categories ORDER BY id")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def add_or_update_category(name, monthly_budget=0.0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO categories (name, monthly_budget)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET monthly_budget = excluded.monthly_budget
    """, (name.strip(), float(monthly_budget)))
    conn.commit()
    conn.close()


def export_to_csv(filepath="data/expenses_export.csv", month_filter=None):
    records = get_all_expenses(month_filter=month_filter)
    if not records:
        return 0, filepath

    folder = os.path.dirname(filepath)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)

    fieldnames = ["id", "date", "amount", "category", "description", "payment_method"]
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r[k] for k in fieldnames})

    return len(records), filepath


def import_from_csv(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    imported_count = 0
    existing_cats = {c["name"].lower(): c["name"] for c in get_categories()}

    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                date_str = row.get("date", "").strip()
                datetime.strptime(date_str, "%Y-%m-%d")
                amount = float(row.get("amount", 0))
                if amount <= 0:
                    continue

                raw_cat = row.get("category", "Other").strip() or "Other"
                if raw_cat.lower() not in existing_cats:
                    add_or_update_category(raw_cat, 0.0)
                    existing_cats[raw_cat.lower()] = raw_cat
                category = existing_cats[raw_cat.lower()]

                desc = row.get("description", "").strip()
                payment = row.get("payment_method", "Cash").strip() or "Cash"

                add_expense(date_str, amount, category, desc, payment)
                imported_count += 1
            except (ValueError, KeyError):
                continue

    return imported_count
