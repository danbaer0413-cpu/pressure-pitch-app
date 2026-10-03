"""Build all_mlb_rosters_2026.csv from free sources.

Sources
  * Statcast pitch-level data via pybaseball -> RISP splits, role, last-10 form
  * MLB Stats API (statsapi.mlb.com)          -> ERA and player names

Usage
  pip install pybaseball pandas requests
  python build_master.py            # first run is slow (whole season); later
                                    # runs only fetch new days
  python build_master.py --refresh  # re-download everything

Regular-season games only (game_type == "R").
"""

import argparse
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SEASON = 2026
SEASON_START = f"{SEASON}-03-15"  # days with no games just return nothing
RAW = Path(f"statcast_{SEASON}_raw.csv.gz")
OUT = Path("all_mlb_rosters_2026.csv")

PRIOR_PA = 50  # shrinkage strength: how many "league-average PA" to add
RECENT_GAMES = 10  # appearances in the Prior-10 window

KEEP = [
    "game_pk", "game_date", "game_type", "pitcher", "player_name", "events",
    "on_2b", "on_3b", "inning_topbot", "home_team", "away_team",
    "at_bat_number", "pitch_number", "bat_score", "post_bat_score",
]
DEDUP = ["game_pk", "at_bat_number", "pitch_number"]

HITS = {"single", "double", "triple", "home_run"}
WALKS = {"walk", "intent_walk"}
# `events` is also filled when a runner is out mid-PA; those aren't PAs.
NOT_PA = "caught_stealing|pickoff|game_advisory|stolen_base"


# ------------------------------------------------------------- fetching ---
def fetch_statcast(refresh=False):
    from pybaseball import cache, statcast  # imported here so tests don't need it

    cache.enable()
    end = dt.date.today()
    frames = []
    start = dt.date.fromisoformat(SEASON_START)

    if RAW.exists() and not refresh:
        old = pd.read_csv(RAW, low_memory=False)
        frames.append(old)
        # re-fetch the last stored day too (may have been partial), dedupe below
        start = pd.to_datetime(old["game_date"]).max().date()

    if start <= end:
        print(f"Fetching Statcast {start} -> {end} (first run can take a while)...")
        new = statcast(start_dt=start.isoformat(), end_dt=end.isoformat())
        if new is not None and len(new):
            frames.append(new[KEEP])

    raw = pd.concat(frames, ignore_index=True).drop_duplicates(subset=DEDUP)
    raw["game_date"] = pd.to_datetime(raw["game_date"])
    raw.to_csv(RAW, index=False)
    return raw


def fetch_mlb_api():
    """Season ERA + names for every pitcher, keyed by MLBAM id."""
    r = requests.get(
        "https://statsapi.mlb.com/api/v1/stats",
        params={
            "stats": "season", "group": "pitching", "season": SEASON,
            "gameType": "R", "sportIds": 1, "playerPool": "ALL", "limit": 3000,
        },
        timeout=60,
    )
    r.raise_for_status()
    rows = [
        {
            "pitcher": s["player"]["id"],
            "Pitcher": s["player"]["fullName"],
            "Standard_ERA": pd.to_numeric(s["stat"].get("era"), errors="coerce"),
        }
        for s in r.json()["stats"][0]["splits"]
    ]
    return pd.DataFrame(rows).dropna(subset=["Standard_ERA"]).drop_duplicates("pitcher")


# ------------------------------------------------------------- modelling ---
def shrink(events, pa, league_rate, prior=PRIOR_PA):
    """Beta-binomial style shrinkage toward the league rate."""
    return (events + prior * league_rate) / (pa + prior)


def pressure_pitch_events(h, bb):
    """Numerator of the pressure-pitch rate.

    PLACEHOLDER DEFINITION: (H + BB) allowed per RISP plate appearance.
    If your original Adjusted_Pressure_Pitch used a different formula, change
    it here (and in raw_pp below) so everything downstream stays consistent.
    """
    return h + bb


def build_table(raw, api):
    raw = raw[raw["game_type"] == "R"].copy()
    raw["pit_team"] = np.where(raw["inning_topbot"] == "Top",
                               raw["home_team"], raw["away_team"])
    raw = raw.sort_values(["game_pk", "at_bat_number", "pitch_number"])

    # --- appearances, role, team
    apps = raw.drop_duplicates(["game_pk", "pitcher"])[
        ["game_pk", "game_date", "pitcher", "pit_team"]
    ]
    starters = raw.drop_duplicates(["game_pk", "pit_team"])[["pitcher"]]
    gs = starters["pitcher"].value_counts()
    g = apps["pitcher"].value_counts()
    info = pd.DataFrame({"G": g})
    info["GS"] = gs.reindex(info.index).fillna(0)
    info["Role"] = np.where(info["GS"] / info["G"] >= 0.5, "Starter", "Reliever")
    info["Team"] = apps.sort_values("game_date").groupby("pitcher")["pit_team"].last()

    # --- plate appearances with RISP
    pa = raw[raw["events"].notna()]
    pa = pa[~pa["events"].str.contains(NOT_PA)].copy()
    pa["H"] = pa["events"].isin(HITS).astype(int)
    pa["BB"] = pa["events"].isin(WALKS).astype(int)
    pa["R"] = (pa["post_bat_score"] - pa["bat_score"]).clip(lower=0)
    risp = pa[pa["on_2b"].notna() | pa["on_3b"].notna()]

    def agg(df):
        return df.groupby("pitcher").agg(
            PA=("events", "size"), H=("H", "sum"), BB=("BB", "sum"), R=("R", "sum")
        )

    season = agg(risp).reindex(info.index).fillna(0)
    league_rate = pressure_pitch_events(season["H"].sum(), season["BB"].sum()) / season["PA"].sum()

    recent_ids = (
        apps.sort_values(["pitcher", "game_date", "game_pk"])
        .groupby("pitcher").tail(RECENT_GAMES)[["pitcher", "game_pk"]]
    )
    recent = agg(risp.merge(recent_ids, on=["pitcher", "game_pk"])).reindex(info.index).fillna(0)

    out = info.copy()
    out["PA_RISP"] = season["PA"].astype(int)
    out["H_RISP"] = season["H"].astype(int)
    out["BB_RISP"] = season["BB"].astype(int)
    out["R_RISP"] = season["R"].astype(int)
    ev = pressure_pitch_events(season["H"], season["BB"])
    out["Raw_PP"] = (ev / season["PA"].replace(0, np.nan)).round(3)
    out["Adjusted_Pressure_Pitch"] = shrink(ev, season["PA"], league_rate).round(3)
    ev10 = pressure_pitch_events(recent["H"], recent["BB"])
    out["Prior_10_PP"] = shrink(ev10, recent["PA"], league_rate).round(3)
    # positive = recent form is WORSE than season baseline (higher PP is worse)
    out["Trend_Delta"] = (out["Prior_10_PP"] - out["Adjusted_Pressure_Pitch"]).round(3)

    out = out.reset_index().rename(columns={"index": "pitcher"})
    out = out.merge(api, on="pitcher", how="inner")
    cols = ["Pitcher", "Team", "Role", "PA_RISP", "H_RISP", "BB_RISP", "R_RISP",
            "Standard_ERA", "Adjusted_Pressure_Pitch", "Prior_10_PP",
            "Trend_Delta", "Raw_PP"]
    return out[cols].sort_values("Pitcher").reset_index(drop=True), league_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download all Statcast data")
    args = ap.parse_args()

    raw = fetch_statcast(args.refresh)
    api = fetch_mlb_api()
    table, league_rate = build_table(raw, api)
    table.to_csv(OUT, index=False)

    q = table.loc[table["PA_RISP"] >= 30, "Adjusted_Pressure_Pitch"]
    print(f"Wrote {len(table)} pitchers to {OUT}")
    print(f"League RISP rate (H+BB per PA): {league_rate:.3f}")
    print("Suggested engine calibration (pitchers with >=30 RISP PA):")
    print(f"  LEAGUE_AVG_PP = {league_rate:.3f}")
    print(f"  tier cutoffs  = {q.quantile(.10):.3f} / {q.quantile(.40):.3f} / {q.quantile(.75):.3f}"
          "  (ELITE / GREAT / SHAKY upper bounds)")


if __name__ == "__main__":
    main()
