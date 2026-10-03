"""Scoring engine for the 2026 MLB Pressure Pitch & Trend Engine.

All scoring flows through `score_frame`, so the tier, the pressure score,
pERA, and the percentile always agree with each other and with the sidebar
toggles.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- config ---
MASTER_CSV = "all_mlb_rosters_2026.csv"
SECONDARY_CSV = "fangraphs_2026.csv"  # optional: a REAL second source

RECENT_WEIGHT = 0.30  # weight on Prior-10 form when the lean toggle is on
PERA_PRESSURE_WEIGHT = 0.30  # share of pERA driven by pressure vulnerability
PRIMARY_WEIGHT = 0.60  # blend weight for the primary source if a 2nd exists
POSTSEASON_MULT = {"Starter": 1.05, "Reliever": 1.10}

# (label, badge color, text color), best to worst. Cutoffs are calibrated
# automatically from the data, see calibrate().
TIER_DEFS = [
    ("ELITE", "#FFD700", "#594500"),
    ("GREAT", "#2ecc71", "#ffffff"),
    ("SHAKY", "#f1c40f", "#594500"),
    ("BAD", "#e74c3c", "#ffffff"),
]
TIER_STYLE = {label: (bg, fg) for label, bg, fg in TIER_DEFS}
CUT_PCTS = (0.10, 0.40, 0.75)  # share of qualified pitchers at/below each cutoff
CALIB_MIN_PA = 30  # RISP PA needed to count toward calibration

REQUIRED_COLS = [
    "Pitcher", "Team", "Role", "PA_RISP", "H_RISP", "BB_RISP", "R_RISP",
    "Standard_ERA", "Adjusted_Pressure_Pitch", "Prior_10_PP", "Trend_Delta",
]
BLENDABLE = ["Standard_ERA", "Adjusted_Pressure_Pitch"]


# --------------------------------------------------------------- loading ---
def load_master(path=MASTER_CSV, secondary_path=SECONDARY_CSV):
    """Load the master CSV; blend in a real second source if the file exists.

    The secondary CSV needs a `Pitcher` column plus any of `Standard_ERA` /
    `Adjusted_Pressure_Pitch`. Pitchers missing from it keep primary values.
    Returns (dataframe, source_description).
    """
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")

    df["_key"] = df["Pitcher"].str.strip().str.lower()
    source = "Baseball-Reference master feed"

    if secondary_path and Path(secondary_path).exists():
        sec = pd.read_csv(secondary_path)
        sec["_key"] = sec["Pitcher"].str.strip().str.lower()
        sec = sec.drop_duplicates("_key").set_index("_key")
        used = [c for c in BLENDABLE if c in sec.columns]
        for col in used:
            other = df["_key"].map(sec[col])
            blended = df[col] * PRIMARY_WEIGHT + other * (1 - PRIMARY_WEIGHT)
            df[col] = blended.where(other.notna(), df[col])
        if used:
            source = "Baseball-Reference + FanGraphs consensus"
    return df, source


# --------------------------------------------------------------- scoring ---
def calibrate(df):
    """League-average pressure pitch and tier cutoffs, derived from the data."""
    pp = df["Adjusted_Pressure_Pitch"].astype(float)
    pa = df["PA_RISP"].astype(float)
    qual = pa >= CALIB_MIN_PA
    if qual.sum() < 20:  # tiny sample: fall back to everyone
        qual = pa >= 0
    league = float(np.average(pp[qual], weights=pa[qual].clip(lower=1)))
    cuts = [float(pp[qual].quantile(q)) for q in CUT_PCTS]
    return league, cuts


def score_frame(df, recent_lean=True, postseason_skew=True):
    """Return a copy of df with all derived columns, computed in one place."""
    out = df.copy()
    is_starter = out["Role"].str.contains("Starter", case=False, na=False)

    base = out["Adjusted_Pressure_Pitch"].astype(float)
    if recent_lean:
        out["Active_PP"] = (
            base * (1 - RECENT_WEIGHT) + out["Prior_10_PP"] * RECENT_WEIGHT
        ).round(3)
    else:
        out["Active_PP"] = base.round(3)

    mult = np.where(is_starter, POSTSEASON_MULT["Starter"],
                    POSTSEASON_MULT["Reliever"])
    out["Postseason_PP"] = (out["Active_PP"] * mult).round(3)
    out["Eval_Score"] = out["Postseason_PP"] if postseason_skew else out["Active_PP"]

    league_avg, cuts = calibrate(df)
    out["Tier"] = pd.cut(
        out["Eval_Score"], bins=[-np.inf, *cuts, np.inf],
        labels=[t[0] for t in TIER_DEFS], right=False,
    ).astype(str)

    # pERA now uses the same score the tier uses.
    pressure_mult = out["Eval_Score"] / league_avg
    out["pERA"] = (
        out["Standard_ERA"] * (1 - PERA_PRESSURE_WEIGHT)
        + out["Standard_ERA"] * pressure_mult * PERA_PRESSURE_WEIGHT
    ).round(2)
    out["pERA_Variance"] = (out["pERA"] - out["Standard_ERA"]).round(2)

    # Percentile within role group (starters vs relievers). Lower score = better.
    out["Better_Than_Pct"] = (
        (1 - out.groupby(is_starter)["Eval_Score"].rank(pct=True)) * 100
    ).round(0)
    return out
