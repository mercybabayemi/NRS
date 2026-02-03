# scripts/enrich_transactions_monthly.py
# Creates a richer, Nigeria-realistic transaction history so each individual has many spending categories.
#
# Input:
#   data/transactions_dataset_upgraded.csv   (from your category upgrade step)
#   data/spend_metrics_monthly_dataset.csv   (your monthly inflow/outflow metrics per BVN-month)
#   data/accounts_dataset.csv                (to attach account_id for each transaction)
#
# Output:
#   data/transactions_dataset_enriched.csv
#
# Notes:
# - Keeps your existing transactions and ADDS synthetic ones.
# - Adds rich categories like Airtime, Data, Fueling, Eating Out, Betting, Travel, etc.
# - Uses monthly outflow totals to scale the synthetic amounts so it looks consistent per month.
# - Ensures each month has multiple categories (not just 2–3).

from __future__ import annotations

import math
import random
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

DATA_DIR = Path("data")

IN_TXN = DATA_DIR / "transactions_dataset_upgraded.csv"
IN_MONTHLY = DATA_DIR / "spend_metrics_monthly_dataset.csv"
IN_ACCOUNTS = DATA_DIR / "accounts_dataset.csv"

OUT_TXN = DATA_DIR / "transactions_dataset_enriched.csv"

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# How aggressive enrichment should be
MIN_TXNS_PER_MONTH = 18
MAX_TXNS_PER_MONTH = 45

# Category set (Nigeria-realistic)
# We'll mostly add OUTflows. We can add some inflows too, but focus is spending richness.
CATEGORIES = [
    "Food & Groceries",
    "Eating Out / Restaurants",
    "Airtime",
    "Internet / Data",
    "Transportation",
    "Fueling",
    "Electricity",
    "Water",
    "Cable TV",
    "Healthcare",
    "Education",
    "Shopping / E-commerce",
    "Clothing & Fashion",
    "Entertainment",
    "Betting & Gaming",
    "Travel",
    "Hotels & Lodging",
    "Bank Fees & Charges",
    "Outgoing Transfer",
    "POS Withdrawal",
    "ATM Withdrawal",
]

# Per-category typical amount ranges (₦)
# (min, max) for a single transaction
AMOUNT_RANGES = {
    "Food & Groceries": (800, 15000),
    "Eating Out / Restaurants": (1500, 20000),
    "Airtime": (200, 3000),
    "Internet / Data": (500, 10000),
    "Transportation": (300, 12000),
    "Fueling": (2000, 40000),
    "Electricity": (1000, 25000),
    "Water": (300, 7000),
    "Cable TV": (1500, 18000),
    "Healthcare": (800, 30000),
    "Education": (2000, 80000),
    "Shopping / E-commerce": (1500, 60000),
    "Clothing & Fashion": (2000, 70000),
    "Entertainment": (500, 20000),
    "Betting & Gaming": (200, 25000),
    "Travel": (10000, 250000),
    "Hotels & Lodging": (8000, 180000),
    "Bank Fees & Charges": (50, 2500),
    "Outgoing Transfer": (2000, 120000),
    "POS Withdrawal": (1000, 60000),
    "ATM Withdrawal": (1000, 50000),
}

# Merchants/narrations for realism (very lightweight)
MERCHANTS = {
    "Airtime": ["MTN VTU", "Airtel VTU", "Glo VTU", "9mobile VTU"],
    "Internet / Data": ["MTN Data", "Airtel Data", "Glo Data", "9mobile Data", "Smile", "Spectranet", "Starlink"],
    "Food & Groceries": ["Shoprite", "SPAR", "Local Market", "Justrite", "Everyday Supermarket"],
    "Eating Out / Restaurants": ["KFC", "Chicken Republic", "Dominos", "Mr Biggs", "Local Bukka", "Cafe Neo"],
    "Transportation": ["Uber", "Bolt", "Bus Fare", "Okada Fare", "Fuel Station POS", "Toll Gate"],
    "Fueling": ["NNPC Station", "TotalEnergies", "Oando", "Mobil", "AP Station"],
    "Electricity": ["IKEDC", "EKEDC", "JEDC", "BEDC", "AEDC"],
    "Water": ["Water Vendor", "Water Board"],
    "Cable TV": ["DSTV", "GOtv", "StarTimes"],
    "Healthcare": ["Pharmacy", "Clinic", "Hospital"],
    "Education": ["School Fees", "Course Payment", "Exam Fees"],
    "Shopping / E-commerce": ["Jumia", "Konga", "Mall Purchase", "Online Store"],
    "Clothing & Fashion": ["Boutique", "Tailor", "Shoe Store"],
    "Entertainment": ["Cinema", "Game Center", "Concert Tickets"],
    "Betting & Gaming": ["Bet9ja", "SportyBet", "1xBet", "BetKing"],
    "Travel": ["Air Peace", "Arik Air", "Travel Booking"],
    "Hotels & Lodging": ["Hotel Booking", "Shortlet", "Airbnb"],
    "Bank Fees & Charges": ["SMS Alert", "Maintenance Fee", "Stamp Duty", "Transfer Charge"],
    "Outgoing Transfer": ["Transfer to Family", "Transfer to Vendor", "Transfer to Savings"],
    "POS Withdrawal": ["POS Cash Agent", "POS Withdrawal"],
    "ATM Withdrawal": ["ATM Withdrawal", "Cash Withdrawal"],
}

CHANNELS = ["POS", "USSD", "Mobile App", "Bank Transfer", "ATM", "Card", "Web"]
OUTFLOW_LIKE = {
    "Outgoing Transfer": "transfer",
    "POS Withdrawal": "withdrawal",
    "ATM Withdrawal": "withdrawal",
    "Bank Fees & Charges": "fees",
}

def require_file(p: Path) -> Path:
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}. Put the file in your data/ folder.")
    return p

def parse_year_month(ym: str) -> tuple[int, int]:
    # expects "YYYY-MM"
    y, m = ym.split("-")
    return int(y), int(m)

def random_datetime_in_month(year: int, month: int) -> pd.Timestamp:
    # pick a random day/time in given month
    start = pd.Timestamp(year=year, month=month, day=1)
    # end = first day of next month
    if month == 12:
        end = pd.Timestamp(year=year + 1, month=1, day=1)
    else:
        end = pd.Timestamp(year=year, month=month + 1, day=1)
    delta_seconds = int((end - start).total_seconds())
    r = random.randint(0, max(0, delta_seconds - 1))
    return start + pd.Timedelta(seconds=r)

def choose_account_id(accounts_df: pd.DataFrame, bvn: str) -> str:
    # pick a stable account per bvn (first one), fallback to a synthetic id
    rows = accounts_df[accounts_df["bvn"] == bvn]
    if not rows.empty and "account_id" in rows.columns:
        return str(rows.iloc[0]["account_id"])
    return f"ACC_{bvn}"

def dirichlet_weights(k: int, alpha: float = 0.6) -> np.ndarray:
    # smaller alpha => more uneven; we want variety but still realistic
    return np.random.dirichlet([alpha] * k)

def sample_categories_for_person_month(activity_level: float) -> list[str]:
    """
    Choose a subset of categories to appear in a month.
    activity_level ~ 0..1 influences how many categories we include.
    """
    # baseline categories nearly everyone has
    baseline = ["Food & Groceries", "Transportation", "Airtime", "Internet / Data"]
    extra_pool = [c for c in CATEGORIES if c not in baseline]

    # number of extra categories for the month
    # low activity: 3-6 categories total, high activity: 8-12 categories total
    extra_min = 2 if activity_level < 0.4 else 4
    extra_max = 6 if activity_level < 0.4 else 10
    n_extra = random.randint(extra_min, extra_max)

    extras = random.sample(extra_pool, k=min(n_extra, len(extra_pool)))

    # betting/travel are rarer; sometimes remove them for realism
    if "Travel" in extras and random.random() < 0.65:
        extras.remove("Travel")
    if "Hotels & Lodging" in extras and random.random() < 0.70:
        extras.remove("Hotels & Lodging")
    if "Betting & Gaming" in extras and random.random() < 0.50:
        extras.remove("Betting & Gaming")

    cats = list(dict.fromkeys(baseline + extras))  # preserve order, unique
    return cats

def txn_amount(category: str) -> float:
    lo, hi = AMOUNT_RANGES.get(category, (200, 20000))
    # log-uniform-ish amounts feel more realistic than uniform
    lo = max(1, lo)
    hi = max(lo + 1, hi)
    val = math.exp(random.uniform(math.log(lo), math.log(hi)))
    return float(round(val, 2))

def pick_merchant(category: str) -> str:
    opts = MERCHANTS.get(category)
    if not opts:
        return category
    return random.choice(opts)

def build_narration(category: str, merchant: str, direction: str) -> str:
    base = {
        "Food & Groceries": f"Purchase - {merchant}",
        "Eating Out / Restaurants": f"Restaurant - {merchant}",
        "Airtime": f"Airtime Topup - {merchant}",
        "Internet / Data": f"Data Subscription - {merchant}",
        "Transportation": f"Transport - {merchant}",
        "Fueling": f"Fuel Purchase - {merchant}",
        "Electricity": f"Electricity Payment - {merchant}",
        "Water": f"Water Payment - {merchant}",
        "Cable TV": f"Cable Subscription - {merchant}",
        "Healthcare": f"Medical - {merchant}",
        "Education": f"Education - {merchant}",
        "Shopping / E-commerce": f"Online Purchase - {merchant}",
        "Clothing & Fashion": f"Fashion - {merchant}",
        "Entertainment": f"Entertainment - {merchant}",
        "Betting & Gaming": f"Betting - {merchant}",
        "Travel": f"Travel Booking - {merchant}",
        "Hotels & Lodging": f"Hotel - {merchant}",
        "Bank Fees & Charges": f"Bank Charge - {merchant}",
        "Outgoing Transfer": f"Transfer to - {merchant}",
        "POS Withdrawal": f"POS Cash Withdrawal - {merchant}",
        "ATM Withdrawal": f"ATM Cash Withdrawal - {merchant}",
    }.get(category, f"{category} - {merchant}")

    if direction == "inflow":
        return f"Credit - {base}"
    return base

def infer_activity_level(month_outflows: float, month_inflows: float) -> float:
    # normalize roughly; this is demo logic
    base = (month_outflows + 0.5 * month_inflows) / 500_000.0
    return float(np.clip(base, 0.05, 1.0))

def main():
    require_file(IN_TXN)
    require_file(IN_MONTHLY)
    require_file(IN_ACCOUNTS)

    txns = pd.read_csv(IN_TXN, dtype={"bvn": str, "account_id": str, "transaction_id": str})
    monthly = pd.read_csv(IN_MONTHLY, dtype={"bvn": str})

    accounts = pd.read_csv(IN_ACCOUNTS, dtype={"bvn": str, "account_id": str})

    # Ensure required columns exist
    if "year_month" not in monthly.columns:
        raise ValueError("spend_metrics_monthly_dataset.csv missing 'year_month'")
    for col in ["total_inflows", "total_outflows"]:
        if col not in monthly.columns:
            raise ValueError(f"spend_metrics_monthly_dataset.csv missing '{col}'")

    # Parse/clean numeric
    monthly["total_inflows"] = pd.to_numeric(monthly["total_inflows"], errors="coerce").fillna(0.0)
    monthly["total_outflows"] = pd.to_numeric(monthly["total_outflows"], errors="coerce").fillna(0.0)

    # Ensure datetime column exists in txns
    if "txn_datetime" not in txns.columns:
        # if absent, create something random (fallback)
        txns["txn_datetime"] = pd.Timestamp("2025-01-01")
    else:
        txns["txn_datetime"] = pd.to_datetime(txns["txn_datetime"], errors="coerce")

    # Ensure category column available
    if "category_v2" not in txns.columns:
        # fallback to existing category if upgrade not present
        txns["category_v2"] = txns.get("category", "Other Spending")

    # Determine a starting numeric suffix for new transaction IDs
    # We'll generate unique transaction_id like SYN_<bvn>_<ym>_<n>
    existing_ids = set(txns["transaction_id"].dropna().astype(str).tolist()) if "transaction_id" in txns.columns else set()

    new_rows = []

    # For each BVN-month, create additional outflow txns spread across multiple categories
    for row in monthly.itertuples(index=False):
        bvn = str(getattr(row, "bvn"))
        ym = str(getattr(row, "year_month"))

        try:
            year, month = parse_year_month(ym)
        except Exception:
            # Skip malformed year_month
            continue

        month_inflows = float(getattr(row, "total_inflows"))
        month_outflows = float(getattr(row, "total_outflows"))

        # Choose activity level based on monthly totals
        activity_level = infer_activity_level(month_outflows, month_inflows)

        # Decide how many synthetic txns to generate this month
        n_txn = int(
            np.clip(
                round(MIN_TXNS_PER_MONTH + activity_level * (MAX_TXNS_PER_MONTH - MIN_TXNS_PER_MONTH)),
                MIN_TXNS_PER_MONTH,
                MAX_TXNS_PER_MONTH,
            )
        )

        # Select categories for the month and assign weights
        cats = sample_categories_for_person_month(activity_level)

        # Force at least 6 categories for richness (your goal)
        if len(cats) < 6:
            extra_candidates = [c for c in CATEGORIES if c not in cats]
            random.shuffle(extra_candidates)
            cats += extra_candidates[: (6 - len(cats))]

        w = dirichlet_weights(len(cats), alpha=0.65)

        # Build raw amounts per txn then scale to match monthly_outflows (approximately)
        raw_amounts = []
        raw_cats = []

        for i in range(n_txn):
            # Choose a category by weights
            cat = np.random.choice(cats, p=w)
            amt = txn_amount(cat)
            raw_cats.append(cat)
            raw_amounts.append(amt)

        raw_sum = float(np.sum(raw_amounts)) if raw_amounts else 0.0

        # Scale factor to align synthetic sum to a portion of monthly outflows
        # We don't want to exactly equal monthly_outflows because you may already have existing txns.
        # We'll target an additional 60% of monthly_outflows if there are existing txns; otherwise 95%.
        existing_month_mask = (
            (txns["bvn"].astype(str) == bvn)
            & (txns["txn_datetime"].dt.year == year)
            & (txns["txn_datetime"].dt.month == month)
            & (txns.get("direction", "").astype(str).str.lower() == "outflow")
        )
        existing_month_outflow = 0.0
        if "amount" in txns.columns:
            existing_month_outflow = pd.to_numeric(txns.loc[existing_month_mask, "amount"], errors="coerce").fillna(0).sum()

        if month_outflows <= 0:
            # if monthly totals are empty, synthesize a reasonable outflow budget from inflow
            month_outflows = max(30_000.0, month_inflows * random.uniform(0.4, 1.0))

        target_extra = month_outflows * (0.60 if existing_month_outflow > 0 else 0.95)

        scale = 1.0
        if raw_sum > 0:
            scale = target_extra / raw_sum

        # Cap scaling so we don't create crazy spikes
        scale = float(np.clip(scale, 0.35, 4.0))

        account_id = choose_account_id(accounts, bvn)

        # Create rows
        for i, (cat, amt) in enumerate(zip(raw_cats, raw_amounts), start=1):
            amt2 = float(round(amt * scale, 2))
            merchant = pick_merchant(cat)
            channel = random.choice(CHANNELS)

            # Choose "direction" based on category type (mostly outflow)
            direction = "outflow"

            # Some categories are "cash actions" but still outflow
            if cat in ["ATM Withdrawal", "POS Withdrawal"]:
                channel = "ATM" if cat == "ATM Withdrawal" else "POS"

            # Build datetime
            dt = random_datetime_in_month(year, month)

            # Unique synthetic transaction id
            tid = f"SYN_{bvn}_{ym}_{i:03d}"
            # ensure uniqueness if collision
            while tid in existing_ids:
                tid = f"SYN_{bvn}_{ym}_{i:03d}_{random.randint(10,99)}"
            existing_ids.add(tid)

            narration = build_narration(cat, merchant, direction)

            new_rows.append(
                {
                    "transaction_id": tid,
                    "bvn": bvn,
                    "account_id": account_id,
                    "txn_datetime": dt,
                    "direction": direction,
                    "amount": amt2,
                    "category_v2": cat,
                    # keep existing naming if present
                    "category": txns["category"].iloc[0] if "category" in txns.columns else cat,
                    "channel": channel,
                    "merchant_name": merchant,
                    "narration": narration,
                    # optional marker so you can filter synthetic vs original in UI
                    "is_synthetic": True,
                }
            )

    enriched = pd.concat(
        [
            txns.assign(is_synthetic=False),
            pd.DataFrame(new_rows),
        ],
        ignore_index=True,
    )

    # Ensure types
    enriched["txn_datetime"] = pd.to_datetime(enriched["txn_datetime"], errors="coerce")
    enriched["amount"] = pd.to_numeric(enriched["amount"], errors="coerce")

    # If your app expects `category` to be meaningful, set it to category_v2 for enriched dataset
    enriched["category"] = enriched["category_v2"]

    # Sort for nice browsing
    enriched = enriched.sort_values(["bvn", "txn_datetime"], ascending=[True, True])

    enriched.to_csv(OUT_TXN, index=False)
    print(f"✅ Saved: {OUT_TXN}  | rows: {len(enriched):,}  (added {len(new_rows):,} synthetic txns)")


if __name__ == "__main__":
    main()
