"""
seed_database.py - Database Seeder
====================================
Creates and populates the sample SQLite business database with realistic data.

Tables created:
  - products:   Product catalogue with categories and pricing
  - customers:  Customer base with segments and regions
  - sales:      Transaction history (12 months, with intentional March dip)
  - inventory:  Stock levels with low-stock scenarios for demo questions

Run once before starting the app:
    python seed_database.py

Interview note:
    SQLite is used for simplicity and portability (zero config, single file).
    In production, swap sqlite:/// for postgresql:// in SQLAlchemy — same models.
"""

import sqlite3
import os
import random
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "sample_business.db")


def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Drop & recreate tables for clean re-seeding ───────────────────────────
    c.executescript("""
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE products (
            product_id   INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            category     TEXT NOT NULL,
            unit_price   REAL NOT NULL,
            cost_price   REAL NOT NULL
        );

        CREATE TABLE customers (
            customer_id  INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            segment      TEXT NOT NULL,   -- Enterprise, SMB, Consumer
            region       TEXT NOT NULL,   -- North, South, East, West
            joined_date  TEXT NOT NULL
        );

        CREATE TABLE sales (
            sale_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id   INTEGER REFERENCES products(product_id),
            customer_id  INTEGER REFERENCES customers(customer_id),
            sale_date    TEXT NOT NULL,
            quantity     INTEGER NOT NULL,
            revenue      REAL NOT NULL,
            discount_pct REAL NOT NULL DEFAULT 0.0
        );

        CREATE TABLE inventory (
            inventory_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id         INTEGER REFERENCES products(product_id),
            as_of_date         TEXT NOT NULL,
            units_in_stock     INTEGER NOT NULL,
            units_on_order     INTEGER NOT NULL,
            reorder_threshold  INTEGER NOT NULL,
            avg_daily_demand   REAL NOT NULL
        );
    """)

    # ── Products ──────────────────────────────────────────────────────────────
    products = [
        (1, "Nexus CRM Suite",       "Software",   1200.0,  300.0),
        (2, "DataVault Pro",          "Software",    850.0,  200.0),
        (3, "SecureShield Antivirus", "Security",    350.0,   80.0),
        (4, "CloudSync Storage",      "Cloud",       600.0,  150.0),
        (5, "AnalyticsPulse",         "Analytics",   950.0,  220.0),
        (6, "WorkFlow Automation",    "Software",    780.0,  180.0),
        (7, "DevOps Pipeline Kit",    "DevTools",    450.0,  100.0),
        (8, "AI Insights Engine",     "Analytics",  2200.0,  500.0),
    ]
    c.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)

    # ── Customers ─────────────────────────────────────────────────────────────
    segments = ["Enterprise", "SMB", "Consumer"]
    regions  = ["North", "South", "East", "West"]
    customers = []
    random.seed(42)
    for i in range(1, 101):
        joined = date(2022, 1, 1) + timedelta(days=random.randint(0, 365))
        customers.append((
            i,
            f"Customer_{i:03d}",
            random.choice(segments),
            random.choice(regions),
            str(joined),
        ))
    c.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    # ── Sales (12 months: 2025-01 to 2025-12) ────────────────────────────────
    # Intentional March dip for Product 1 & 2 (for demo question)
    # Q4 higher for Analytics products (seasonal)
    sales = []
    for month in range(1, 13):
        for product_id in range(1, 9):
            base_qty = random.randint(8, 25)

            # March sales dip for CRM Suite (product 1) — demo scenario
            if month == 3 and product_id == 1:
                base_qty = random.randint(2, 5)

            # Q4 boost for Analytics (products 5 & 8)
            if month in (10, 11, 12) and product_id in (5, 8):
                base_qty = int(base_qty * 1.6)

            for _ in range(base_qty):
                sale_date   = date(2025, month, random.randint(1, 28))
                customer_id = random.randint(1, 100)
                unit_price  = next(p[3] for p in products if p[0] == product_id)
                quantity    = random.randint(1, 5)
                discount    = random.choice([0.0, 0.05, 0.1, 0.15])
                revenue     = round(quantity * unit_price * (1 - discount), 2)
                sales.append((product_id, customer_id, str(sale_date), quantity, revenue, discount))

    c.executemany(
        "INSERT INTO sales (product_id,customer_id,sale_date,quantity,revenue,discount_pct) VALUES (?,?,?,?,?,?)",
        sales,
    )

    # ── Inventory (as of 2025-12-01) ──────────────────────────────────────────
    # Products 3 & 7 are near stockout for demo question
    inventory_data = [
        (1, "2025-12-01", 145, 50, 100, 4.5),
        (2, "2025-12-01",  98, 30,  80, 3.2),
        (3, "2025-12-01",  12,  0,  40, 2.8),  # ← LOW STOCK (SecureShield)
        (4, "2025-12-01", 210, 80, 120, 6.1),
        (5, "2025-12-01", 175, 60, 100, 5.8),
        (6, "2025-12-01",  88, 20,  70, 3.0),
        (7, "2025-12-01",   8,  0,  30, 1.5),  # ← LOW STOCK (DevOps Kit)
        (8, "2025-12-01", 320, 100, 150, 8.2),
    ]
    c.executemany(
        "INSERT INTO inventory (product_id,as_of_date,units_in_stock,units_on_order,reorder_threshold,avg_daily_demand) VALUES (?,?,?,?,?,?)",
        inventory_data,
    )

    conn.commit()
    conn.close()

    # Count for confirmation
    conn = sqlite3.connect(DB_PATH)
    row_counts = {
        tbl: conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        for tbl in ["products", "customers", "sales", "inventory"]
    }
    conn.close()

    print("[OK] Database seeded successfully!")
    for tbl, cnt in row_counts.items():
        print(f"   - {tbl}: {cnt} rows")
    print(f"\nLocation: {DB_PATH}")


if __name__ == "__main__":
    seed()
