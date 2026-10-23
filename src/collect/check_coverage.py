"""Verify Phase 1 raw data: every club present, 38 matches each, no gaps in key stats."""
import sys

import pandas as pd

from config import RAW

EXPECTED_TEAMS, EXPECTED_MATCHES = 20, 380
problems = []


def check(cond: bool, msg: str) -> None:
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        problems.append(msg)


us = pd.read_csv(RAW / "understat" / "team_match_stats.csv")
for league, g in us.groupby("league"):
    per_team = pd.concat([g["home_team"], g["away_team"]]).value_counts()
    check(len(g) == EXPECTED_MATCHES, f"Understat {league}: {len(g)} matches")
    check(len(per_team) == EXPECTED_TEAMS and (per_team == 38).all(), f"Understat {league}: {len(per_team)} teams x 38 matches")

shots = pd.read_csv(RAW / "understat" / "shots.csv")
check(shots[["xg", "location_x", "location_y"]].notna().all().all(), f"Understat shots: {len(shots)} rows, no missing xg/location")

br = pd.read_csv(RAW / "understat" / "team_breakdowns.csv")
check(br.groupby("block")["team"].nunique().eq(60).all(), "Understat team breakdowns: 60 teams in every block")

espn = pd.read_csv(RAW / "espn" / "team_match_stats.csv")
key_stats = ["possessionPct", "totalShots", "shotsOnTarget", "accuratePasses", "totalPasses", "totalCrosses", "totalLongBalls"]
for league, g in espn.groupby("league"):
    check(g["event_id"].nunique() == EXPECTED_MATCHES, f"ESPN {league}: {g['event_id'].nunique()} matches")
    per_team = g["team"].value_counts()
    check(len(per_team) == EXPECTED_TEAMS and (per_team == 38).all(), f"ESPN {league}: {len(per_team)} teams x 38 matches")
    missing = g[key_stats].isna().sum()
    check(missing.sum() == 0, f"ESPN {league}: missing key stats {missing[missing > 0].to_dict()}")

fb = pd.read_csv(RAW / "fbref" / "team_season_stats.csv")
check(len(fb) == 60, f"FBref: {len(fb)} teams")
# A stale soccerdata season cache once served the in-progress 2026/27 season under "2526".
check(fb["standard_Playing Time_MP"].eq(38).all(), "FBref: every team has 38 matches (complete 2025/26 season)")

sys.exit(1 if problems else 0)
