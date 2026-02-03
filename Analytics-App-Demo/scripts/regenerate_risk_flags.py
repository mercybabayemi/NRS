# scripts/regenerate_risk_flags.py
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
OUT_PATH = DATA_DIR / "risk_flags_dataset.csv"

PEOPLE_FILE = DATA_DIR / "nigeria_people_dataset.csv"
MONTHLY_FILE = DATA_DIR / "spend_metrics_monthly_dataset.csv"

ASSESSMENT_YEAR = 2025  # change if you want


def safe_div(a, b):
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    return np.where((b <= 0) | pd.isna(b) | pd.isna(a), np.nan, a / b)


def clip01(x):
    return np.clip(x, 0.0, 1.0)


def score_peer_ratio(r):
    """
    Convert peer ratio (e.g., 1.0, 2.5, 4.0) into a 0-100 score.
    log2 scaling: 1x->low, 2x->mid, 4x->high, 8x->very high.
    """
    r = np.array(r, dtype=float)
    out = np.full_like(r, 30.0, dtype=float)

    valid = np.isfinite(r) & (r > 0)
    rv = r[valid]

    log2 = np.log2(rv)
    s = 10 + (clip01(log2 / 3.0) * 85)  # 1x->10, 8x->95 approx
    out[valid] = s
    return out


def score_spending_ratio(sr):
    """
    Spending ratio = outflows/inflows.
    Underweighted relative to peer deviation.
    """
    sr = np.array(sr, dtype=float)
    out = np.full_like(sr, 25.0, dtype=float)

    valid = np.isfinite(sr) & (sr >= 0)
    v = sr[valid]

    s = np.where(
        v <= 0.9, 15,
        np.where(
            v <= 1.2, 15 + (v - 0.9) / (1.2 - 0.9) * 25,     # 15..40
            np.where(
                v <= 2.0, 40 + (v - 1.2) / (2.0 - 1.2) * 45, # 40..85
                95
            )
        )
    )
    out[valid] = s
    return out


def score_persistence(months_high, months_total):
    """
    Persistence = fraction of months where person is very high vs peers.
    """
    months_high = np.array(months_high, dtype=float)
    months_total = np.array(months_total, dtype=float)

    frac = np.where(months_total <= 0, np.nan, months_high / months_total)
    s = 10 + clip01(frac) * 85  # 0%->10, 100%->95
    s = np.where(np.isfinite(s), s, 30.0)
    return s


def status_from_score(s):
    if pd.isna(s):
        return "Unknown"
    if s >= 65:
        return "Flagged"
    if s >= 40:
        return "Review"
    return "Compliant"


def main():
    people = pd.read_csv(PEOPLE_FILE, dtype={"bvn": str})
    monthly = pd.read_csv(MONTHLY_FILE, dtype={"bvn": str})

    # Validate required columns
    required_people = {"bvn", "state_of_residence", "local_government_area"}
    required_monthly = {"bvn", "year_month", "total_inflows", "total_outflows", "spending_ratio"}

    missing_people = required_people - set(people.columns)
    missing_monthly = required_monthly - set(monthly.columns)

    if missing_people:
        raise ValueError(f"People file missing columns: {missing_people}")
    if missing_monthly:
        raise ValueError(f"Monthly file missing columns: {missing_monthly}")

    # Ensure numeric in monthly
    for c in ["total_inflows", "total_outflows", "spending_ratio"]:
        monthly[c] = pd.to_numeric(monthly[c], errors="coerce")

    # IMPORTANT: monthly already has state_of_residence, so avoid collisions
    monthly_geo = monthly.merge(
        people[["bvn", "state_of_residence", "local_government_area"]].rename(
            columns={"state_of_residence": "res_state", "local_government_area": "res_lga"}
        ),
        on="bvn",
        how="left",
    )

    # Normalize geography text
    monthly_geo["res_state"] = monthly_geo["res_state"].astype(str).str.strip()
    monthly_geo["res_lga"] = monthly_geo["res_lga"].astype(str).str.strip()

    # --- Per-month peer baselines (median is robust) ---
    lga_month_base = (
        monthly_geo.groupby(["year_month", "res_state", "res_lga"], as_index=False)["total_outflows"]
        .median()
        .rename(columns={"total_outflows": "lga_month_median_outflows"})
    )

    state_month_base = (
        monthly_geo.groupby(["year_month", "res_state"], as_index=False)["total_outflows"]
        .median()
        .rename(columns={"total_outflows": "state_month_median_outflows"})
    )

    monthly_geo = monthly_geo.merge(lga_month_base, on=["year_month", "res_state", "res_lga"], how="left")
    monthly_geo = monthly_geo.merge(state_month_base, on=["year_month", "res_state"], how="left")

    # --- Person totals over all their months ---
    person_totals = (
        monthly_geo.groupby("bvn", as_index=False)
        .agg(
            months_total=("year_month", "nunique"),
            inflows_sum=("total_inflows", "sum"),
            outflows_sum=("total_outflows", "sum"),
            spending_ratio_avg=("spending_ratio", "mean"),
            state_of_residence=("res_state", "first"),
            local_government_area=("res_lga", "first"),
        )
    )

    # --- Person baselines (median of monthly medians over their months) ---
    person_baselines = (
        monthly_geo.groupby("bvn", as_index=False)
        .agg(
            lga_baseline_outflows=("lga_month_median_outflows", "median"),
            state_baseline_outflows=("state_month_median_outflows", "median"),
        )
    )

    df = person_totals.merge(person_baselines, on="bvn", how="left")

    # Peer ratios
    df["peer_ratio_lga"] = safe_div(df["outflows_sum"], df["lga_baseline_outflows"])
    df["peer_ratio_state"] = safe_div(df["outflows_sum"], df["state_baseline_outflows"])

    # Persistence: months where outflows > 2.5x LGA monthly median
    monthly_geo["is_high_vs_lga"] = monthly_geo["total_outflows"] > (2.5 * monthly_geo["lga_month_median_outflows"])
    pers = monthly_geo.groupby("bvn", as_index=False).agg(months_high=("is_high_vs_lga", "sum"))
    df = df.merge(pers, on="bvn", how="left")
    df["months_high"] = df["months_high"].fillna(0).astype(int)

    # --- Scores ---
    df["peer_ratio_max"] = np.nanmax(
        np.vstack([df["peer_ratio_lga"].values, df["peer_ratio_state"].values]),
        axis=0
    )

    df["S_peer"] = score_peer_ratio(df["peer_ratio_max"].values)
    df["S_ratio"] = score_spending_ratio(df["spending_ratio_avg"].values)
    df["S_persist"] = score_persistence(df["months_high"].values, df["months_total"].values)

    # Weighted: peer deviation dominates
    df["risk_score"] = (
        0.55 * df["S_peer"] +
        0.25 * df["S_ratio"] +
        0.20 * df["S_persist"]
    )

    df["status"] = df["risk_score"].apply(status_from_score)

    # Human-readable reason
    def reason(row):
        parts = []
        pr_lga = row.get("peer_ratio_lga", np.nan)
        pr_state = row.get("peer_ratio_state", np.nan)
        sr = row.get("spending_ratio_avg", np.nan)
        mh = int(row.get("months_high", 0))
        mt = int(row.get("months_total", 0))

        if np.isfinite(pr_lga) and pr_lga >= 2.5:
            parts.append(f"Outflows are {pr_lga:.1f}× higher than LGA typical.")
        elif np.isfinite(pr_state) and pr_state >= 2.5:
            parts.append(f"Outflows are {pr_state:.1f}× higher than State typical.")

        if np.isfinite(sr) and sr >= 1.2:
            parts.append(f"Spending ratio is high ({sr:.2f}).")

        if mt > 0 and mh >= max(2, int(0.4 * mt)):
            parts.append(f"Pattern repeats in {mh}/{mt} months.")

        if not parts:
            parts.append("Behaviour is within typical ranges for peers.")

        return " ".join(parts)

    df["flag_reason"] = df.apply(reason, axis=1)

    out = df[[
        "bvn",
        "state_of_residence",
        "local_government_area",
        "months_total",
        "months_high",
        "inflows_sum",
        "outflows_sum",
        "spending_ratio_avg",
        "lga_baseline_outflows",
        "state_baseline_outflows",
        "peer_ratio_lga",
        "peer_ratio_state",
        "risk_score",
        "status",
        "flag_reason",
    ]].copy()

    out.insert(1, "assessment_year", ASSESSMENT_YEAR)

    # Round display columns
    for c in ["inflows_sum", "outflows_sum", "lga_baseline_outflows", "state_baseline_outflows"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").round(2)
    for c in ["spending_ratio_avg", "peer_ratio_lga", "peer_ratio_state", "risk_score"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").round(3)

    out.to_csv(OUT_PATH, index=False)
    print(f"✅ Saved: {OUT_PATH} ({len(out):,} rows)")


if __name__ == "__main__":
    main()
