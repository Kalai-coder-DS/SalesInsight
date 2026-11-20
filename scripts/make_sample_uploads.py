"""Create the example files used to try the upload feature (Phase 14).

They are synthetic (randomly generated, fixed seed) and use different column
names, formats and problems on purpose:

1. indian_retail_sales.csv  - ₹ amounts with commas, day/month/year dates, "10%" discounts,
                              a few empty rows, bad dates and a duplicate line
2. online_store_orders.xlsx - Excel dates, cost instead of profit, US states
3. cafe_daily_sales.csv     - only date, item, price and quantity (no sales column), ';' separator
4. not_sales_data.csv       - an HR list, to show the "not sales data" message

Run:  python scripts/make_sample_uploads.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "samples"
rng = np.random.default_rng(14)


def indian_retail(n: int = 1200) -> pd.DataFrame:
    items = {"Electronics": [("Mobile Phone", 15000), ("Earphones", 1200), ("Power Bank", 1800)],
             "Home": [("Pressure Cooker", 2400), ("Mixer Grinder", 3500), ("Bedsheet Set", 1500)],
             "Fashion": [("Kurta", 900), ("Saree", 2800), ("Sports Shoes", 3200)]}
    zones = {"North": ["Delhi", "Punjab", "Uttar Pradesh"], "South": ["Tamil Nadu", "Karnataka", "Kerala"],
             "West": ["Maharashtra", "Gujarat"], "East": ["West Bengal", "Odisha"]}
    customers = [f"Customer {i:03d}" for i in range(1, 181)]
    rows = []
    start = pd.Timestamp("2023-01-01")
    for i in range(n):
        cat = rng.choice(list(items))
        name, price = items[cat][rng.integers(len(items[cat]))]
        qty = int(rng.integers(1, 5))
        disc = rng.choice([0, 0, 0, 5, 10, 15, 25, 40])
        amount = price * qty * (1 - disc / 100) * rng.uniform(0.95, 1.05)
        zone = rng.choice(list(zones))
        date = start + pd.Timedelta(days=int(rng.integers(0, 730)))
        rows.append({"Invoice No": f"INV-{10000 + i // 2}", "Bill Date": date.strftime("%d/%m/%Y"),
                     "Customer": rng.choice(customers), "Item": name, "Category": cat, "Qty": qty,
                     "Rate": f"₹{price:,}", "Discount %": f"{disc}%", "Amount (₹)": f"₹{amount:,.2f}",
                     "Zone": zone, "State": rng.choice(zones[zone])})
    df = pd.DataFrame(rows)
    df.loc[[5, 77], "Bill Date"] = ["31/02/2023", "not known"]      # impossible / missing dates
    df.loc[[12], "Amount (₹)"] = [""]                                  # missing amount
    df = pd.concat([df, df.iloc[[20]]], ignore_index=True)             # one duplicate line
    empty = pd.DataFrame([{c: "" for c in df.columns}] * 2)
    return pd.concat([df, empty], ignore_index=True)


def online_store(n: int = 2000) -> pd.DataFrame:
    products = [("Desk Lamp", "Lighting", 39), ("Office Chair", "Furniture", 189), ("Notebook Pack", "Stationery", 12),
                ("Monitor Arm", "Accessories", 79), ("Standing Desk", "Furniture", 420), ("Pen Set", "Stationery", 9)]
    states = ["California", "Texas", "New York", "Florida", "Washington", "Illinois", "Ohio"]
    rows = []
    for i in range(n):
        name, cat, price = products[rng.integers(len(products))]
        units = int(rng.integers(1, 6))
        total = round(price * units * rng.uniform(0.9, 1.0), 2)
        cost = round(total * rng.uniform(0.55, 1.1), 2)
        rows.append({"Order Number": f"#{50000 + i}", "Order Created": pd.Timestamp("2024-01-01")
                     + pd.Timedelta(hours=int(rng.integers(0, 24 * 365))),
                     "Buyer Email": f"buyer{rng.integers(1, 400)}@example.com", "Product Title": name,
                     "SKU": f"SKU-{products.index((name, cat, price)) + 100}", "Product Type": cat,
                     "Units": units, "Total Price": total, "Total Cost": cost,
                     "Sales Channel": rng.choice(["Website", "Marketplace", "Instagram"]),
                     "Country": "United States", "State": rng.choice(states)})
    return pd.DataFrame(rows)


def cafe(n: int = 900) -> pd.DataFrame:
    menu = [("Cappuccino", 3.5), ("Latte", 3.8), ("Croissant", 2.5), ("Sandwich", 6.0), ("Cheesecake", 4.5)]
    rows = []
    for _ in range(n):
        item, price = menu[rng.integers(len(menu))]
        rows.append({"Date": (pd.Timestamp("2025-03-01") + pd.Timedelta(days=int(rng.integers(0, 120)))).date().isoformat(),
                     "Menu Item": item, "Price": f"{price:.2f}", "Qty": int(rng.integers(1, 4))})
    return pd.DataFrame(rows)


def not_sales() -> pd.DataFrame:
    return pd.DataFrame({"Employee": [f"Person {i}" for i in range(1, 21)],
                         "Department": rng.choice(["HR", "IT", "Finance"], 20),
                         "Rating": rng.choice(["Good", "Very good", "Excellent"], 20)})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    indian_retail().to_csv(OUT / "indian_retail_sales.csv", index=False, encoding="utf-8-sig")
    online_store().to_excel(OUT / "online_store_orders.xlsx", index=False, sheet_name="Orders")
    cafe().to_csv(OUT / "cafe_daily_sales.csv", index=False, sep=";")
    not_sales().to_csv(OUT / "not_sales_data.csv", index=False)
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:28s} {f.stat().st_size / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
