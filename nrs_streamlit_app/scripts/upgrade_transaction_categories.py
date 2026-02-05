# scripts/upgrade_transaction_categories.py
import re
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
IN_PATH = DATA_DIR / "transactions_dataset.csv"
OUT_PATH = DATA_DIR / "transactions_dataset_upgraded.csv"

# If True, overwrite `category` with the new categories.
# If False, keep old `category` and write `category_v2` only.
REPLACE_CATEGORY = False


def norm_text(x: str) -> str:
    x = "" if pd.isna(x) else str(x)
    x = x.lower().strip()
    x = re.sub(r"\s+", " ", x)
    return x


# Ordered rules: first match wins.
# We use merchant_name + narration + channel to categorize.
RULES = [
    # -------------------------
    # INFLOWS (Income signals)
    # -------------------------
    ("Salary", [
        r"\bsalary\b", r"\bwages?\b", r"\bpayroll\b", r"\bpay day\b", r"\bmonthly pay\b",
        r"\bpay\s?ment\b.*\bsalary\b"
    ]),

    ("Business Revenue", [
        r"\bsales\b", r"\binvoice\b", r"\bpos settlement\b", r"\bmerchant settlement\b",
        r"\bpayment received\b", r"\bcustomer\b.*\bpay\b"
    ]),

    ("Freelance / Gig Income", [
        r"\bfreelance\b", r"\bcontract\b", r"\bgig\b", r"\bupwork\b", r"\bfiverr\b"
    ]),

    ("Investment Income", [
        r"\bdividend\b", r"\binterest\b", r"\btreasury\b", r"\bbond\b", r"\bstocks?\b"
    ]),

    ("Incoming Transfer", [
        r"\btransfer from\b", r"\bcredit\b", r"\binward\b", r"\breceived\b"
    ]),

    # -------------------------
    # CASH & WITHDRAWALS
    # -------------------------
    ("ATM Withdrawal", [
        r"\batm\b", r"\bcash withdrawal\b", r"\bdispense\b"
    ]),

    ("POS Withdrawal", [
        r"\bpos cash\b", r"\bpos withdrawal\b", r"\bpos wdl\b", r"\bagent\b.*\bpos\b"
    ]),

    # -------------------------
    # TELECOMS / DATA
    # -------------------------
    ("Airtime", [
        r"\bairtime\b", r"\btop\s?up\b", r"\brecharge\b", r"\bvtu\b",
        r"\bmtn\b.*\bairtime\b", r"\bairtel\b.*\bairtime\b", r"\bglo\b.*\bairtime\b", r"\b9mobile\b.*\bairtime\b",
        r"\bafricell\b.*\bairtime\b"
    ]),

    ("Internet / Data", [
        r"\bdata\b", r"\binternet\b", r"\bbundle\b",
        r"\bmtn\b.*\bdata\b", r"\bairtel\b.*\bdata\b", r"\bglo\b.*\bdata\b", r"\b9mobile\b.*\bdata\b",
        r"\bdstv\b.*\bdata\b"  # just in case
    ]),

    # -------------------------
    # UTILITIES / BILLS
    # -------------------------
    ("Electricity", [
        r"\bphcn\b", r"\bnepa\b", r"\bikedc\b", r"\bekedc\b", r"\bjedc\b", r"\bbedc\b",
        r"\bkaedco\b", r"\biedc\b", r"\bdisco\b", r"\belectric\b", r"\bpower\b"
    ]),

    ("Water", [
        r"\bwater\b", r"\bwater board\b"
    ]),

    ("Cable TV", [
        r"\bdstv\b", r"\bgotv\b", r"\bstartimes\b", r"\bcable\b"
    ]),

    ("Rent / Housing", [
        r"\brent\b", r"\blease\b", r"\bhouse\b.*\brent\b", r"\bagency\b.*\bfee\b"
    ]),

    ("Internet Subscription", [
        r"\bspectranet\b", r"\bsmile\b", r"\bstarlink\b", r"\bmifi\b", r"\brouter\b", r"\bbroadband\b"
    ]),

    # -------------------------
    # TRANSPORT / FUEL
    # -------------------------
    ("Fueling", [
        r"\bfuel\b", r"\bpms\b", r"\bpetrol\b", r"\bdiesel\b", r"\bfill station\b",
        r"\btotal\b", r"\bounje\b",  # sometimes weird narrations; keep minimal
        r"\bnnpc\b", r"\boando\b", r"\bmobil\b", r"\bap\b\s*station\b"
    ]),

    ("Transportation", [
        r"\buber\b", r"\bbolt\b", r"\blagos ride\b", r"\bin-drive\b", r"\bindrive\b",
        r"\btransport\b", r"\bbus\b", r"\btaxi\b", r"\btricycle\b", r"\bokada\b",
        r"\bfare\b", r"\btoll\b"
    ]),

    # -------------------------
    # FOOD
    # -------------------------
    ("Food & Groceries", [
        r"\bsupermarket\b", r"\bgrocery\b", r"\bmarket\b", r"\bshoprite\b", r"\bspar\b",
        r"\bjustrite\b", r"\bchicken republic\b", r"\bpricepointe?\b", r"\bstore\b"
    ]),

    ("Eating Out / Restaurants", [
        r"\brestaurant\b", r"\bcafe\b", r"\bfast ?food\b", r"\bkfc\b", r"\bdominos\b",
        r"\bcold stone\b", r"\bchop\b", r"\beatery\b", r"\bbuka\b"
    ]),

    # -------------------------
    # HEALTH / EDUCATION
    # -------------------------
    ("Healthcare", [
        r"\bhospital\b", r"\bclinic\b", r"\bpharmacy\b", r"\bdrug\b", r"\bmedic\b",
        r"\bheal(th)?\b"
    ]),

    ("Education", [
        r"\bschool\b", r"\btuition\b", r"\bfees?\b.*\bschool\b", r"\buniversity\b",
        r"\bpolytechnic\b", r"\bcollege\b"
    ]),

    # -------------------------
    # BETTING / GAMING
    # -------------------------
    ("Betting & Gaming", [
        r"\bbet9ja\b", r"\bbetking\b", r"\bsportybet\b", r"\bnairabet\b", r"\b1xbet\b",
        r"\bbet\b", r"\bbetting\b", r"\bcasino\b"
    ]),

    # -------------------------
    # TRAVEL / HOTELS
    # -------------------------
    ("Travel", [
        r"\bflight\b", r"\bairline\b", r"\barik\b", r"\bair peace\b", r"\baero\b",
        r"\btravels?\b", r"\bbooking\b", r"\btrip\b"
    ]),

    ("Hotels & Lodging", [
        r"\bhotel\b", r"\blogde\b", r"\bshortlet\b", r"\bairbnb\b"
    ]),

    # -------------------------
    # SHOPPING / ECOMMERCE
    # -------------------------
    ("Shopping / E-commerce", [
        r"\bjumia\b", r"\bkonga\b", r"\btemu\b", r"\baliexpress\b",
        r"\bshopping\b", r"\bmall\b"
    ]),

    ("Clothing & Fashion", [
        r"\bfashion\b", r"\boutfit\b", r"\bclothing\b", r"\bshoe\b", r"\bsneaker\b",
        r"\btailor\b"
    ]),

    # -------------------------
    # FEES / CHARGES
    # -------------------------
    ("Bank Fees & Charges", [
        r"\bcharges?\b", r"\bcommission\b", r"\bstamp duty\b", r"\bfee\b.*\bbank\b",
        r"\bsms alert\b", r"\bmaintenance\b"
    ]),

    # -------------------------
    # TRANSFERS (Outflow)
    # -------------------------
    ("Outgoing Transfer", [
        r"\btransfer to\b", r"\boutward\b", r"\bsent\b", r"\btrf to\b"
    ]),
]


def classify_row(direction, merchant_name, narration, channel, old_category):
    text = " ".join([
        norm_text(direction),
        norm_text(merchant_name),
        norm_text(narration),
        norm_text(channel),
        norm_text(old_category),
    ])

    # First-match rule
    for label, patterns in RULES:
        for pat in patterns:
            if re.search(pat, text):
                return label

    # Fallbacks
    # If inflow but unknown -> Income/Transfer
    if norm_text(direction) == "inflow":
        return "Incoming Transfer"
    # If outflow but unknown -> Transfers/Other spending
    if norm_text(direction) == "outflow":
        return "Other Spending"

    return "Unknown"


def main():
    if not IN_PATH.exists():
        raise FileNotFoundError(f"Missing {IN_PATH}. Put your transactions file in data/")

    df = pd.read_csv(IN_PATH, dtype={"bvn": str, "account_id": str, "transaction_id": str})

    # Ensure expected columns exist
    for c in ["direction", "amount"]:
        if c not in df.columns:
            raise ValueError(f"transactions_dataset.csv missing required column: {c}")

    # Make sure text columns exist (create empty if absent)
    for c in ["merchant_name", "narration", "channel", "category"]:
        if c not in df.columns:
            df[c] = ""

    # Apply classification
    df["category_v2"] = df.apply(
        lambda r: classify_row(
            r.get("direction", ""),
            r.get("merchant_name", ""),
            r.get("narration", ""),
            r.get("channel", ""),
            r.get("category", ""),
        ),
        axis=1,
    )

    # Optionally replace old category
    if REPLACE_CATEGORY:
        df["category_old"] = df.get("category", "")
        df["category"] = df["category_v2"]

    df.to_csv(OUT_PATH, index=False)

    # Quick summary for you
    counts = df["category_v2"].value_counts().head(20)
    print(f"✅ Saved: {OUT_PATH}")
    print("\nTop categories (category_v2):")
    print(counts.to_string())


if __name__ == "__main__":
    main()
