"""Phase 2: merge raw Understat + ESPN data into analysis-ready tables.

Run from the project root:  python -m src.process.build_dataset

Outputs (data/processed/):
- team_match.csv   one row per club per match, with matchweek number and season half
- team_season.csv  one row per club, the 13 clustering features plus context stats
- team_half.csv    one row per club per season half (split-half validation)
- shots.csv        cleaned shot events with canonical club names (shot maps)
- team_breakdowns.csv  Understat attack-speed / shot-zone / situation splits per club
- fyp.sqlite       the same five tables
"""
import sqlite3
from pathlib import Path

import pandas as pd

from src.process.features import aggregate, in_box, shot_summary, understat_long

ROOT = Path(__file__).resolve().parents[2]
RAW, REF, OUT = ROOT / "data" / "raw", ROOT / "data" / "reference", ROOT / "data" / "processed"
ESPN_STATS = ["possessionPct", "accuratePasses", "totalPasses", "totalCrosses", "accurateCrosses",
              "totalLongBalls", "accurateLongBalls", "totalShots", "shotsOnTarget", "wonCorners"]


def load_teams() -> pd.DataFrame:
    return pd.read_csv(REF / "teams.csv")


def build_team_match(teams: pd.DataFrame) -> pd.DataFrame:
    us = pd.read_csv(RAW / "understat" / "team_match_stats.csv")
    shots = pd.read_csv(RAW / "understat" / "shots.csv")
    tm = understat_long(us).merge(shot_summary(shots), on=["game_id", "team"], how="left")
    tm[["shots", "shots_on_target", "box_shots"]] = tm[["shots", "shots_on_target", "box_shots"]].fillna(0)

    us_to_team = dict(zip(teams["understat"], teams["team"]))
    for col in ("team", "opponent", "home_team", "away_team"):
        tm[col] = tm[col].map(us_to_team)

    espn = pd.read_csv(RAW / "espn" / "team_match_stats.csv")
    espn["team"] = espn["team"].map(dict(zip(teams["espn"], teams["team"])))
    espn[ESPN_STATS] = espn[ESPN_STATS].apply(pd.to_numeric, errors="coerce")
    home = espn[espn["home_away"] == "home"][["event_id", "team"]].rename(columns={"team": "home_team"})
    away = espn[espn["home_away"] == "away"][["event_id", "team"]].rename(columns={"team": "away_team"})
    espn = espn.merge(home, on="event_id").merge(away, on="event_id")
    # Each home/away pairing happens exactly once per season, so it is a safe join key across sources.
    tm = tm.merge(espn[["league", "home_team", "away_team", "team", "event_id", *ESPN_STATS]],
                  on=["league", "home_team", "away_team", "team"], how="left", validate="one_to_one")

    tm = tm.sort_values(["team", "date"]).reset_index(drop=True)
    tm["matchweek"] = tm.groupby("team").cumcount() + 1
    tm["half"] = (tm["matchweek"] > 19).map({False: "H1", True: "H2"})
    return tm


def fast_attack(teams: pd.DataFrame) -> pd.DataFrame:
    """Season-level counter-attack proxy from Understat's attack-speed breakdown."""
    br = pd.read_csv(RAW / "understat" / "team_breakdowns.csv")
    br["team"] = br["team"].map(dict(zip(teams["understat"], teams["team"])))
    speed = br[br["block"] == "attackSpeed"].pivot_table(index="team", columns="category", values=["shots", "xg"])
    total_shots = speed["shots"].sum(axis=1)
    return pd.DataFrame({
        "fast_attack_shots_total": speed[("shots", "Fast")],
        "fast_attack_xg_total": speed[("xg", "Fast")],
        "fast_attack_shot_share": speed[("shots", "Fast")] / total_shots * 100,
    }).reset_index()


def build_shots(teams: pd.DataFrame, team_match: pd.DataFrame) -> pd.DataFrame:
    shots = pd.read_csv(RAW / "understat" / "shots.csv")
    shots["team"] = shots["team"].map(dict(zip(teams["understat"], teams["team"])))
    shots = shots.merge(team_match[["game_id", "team", "opponent", "matchweek", "is_home"]], on=["game_id", "team"])
    shots["in_box"] = in_box(shots["location_x"], shots["location_y"])
    keep = ["league", "game_id", "date", "matchweek", "team", "opponent", "is_home", "player", "assist_player",
            "minute", "xg", "location_x", "location_y", "body_part", "situation", "result", "in_box"]
    return shots[keep]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    teams = load_teams()
    tm = build_team_match(teams)
    unmatched = tm["event_id"].isna().sum()
    if tm["team"].isna().any() or unmatched:
        raise SystemExit(f"Join problem: {tm['team'].isna().sum()} unmapped names, {unmatched} matches without ESPN stats")

    season = aggregate(tm, ["league", "team"]).merge(fast_attack(teams), on="team")
    season["fast_attack_shots"] = season["fast_attack_shots_total"] / season["matches"]
    halves = aggregate(tm, ["league", "team", "half"])
    shots = build_shots(teams, tm)
    breakdowns = pd.read_csv(RAW / "understat" / "team_breakdowns.csv")
    breakdowns["team"] = breakdowns["team"].map(dict(zip(teams["understat"], teams["team"])))

    tables = {"team_match": tm, "team_season": season, "team_half": halves, "shots": shots,
              "team_breakdowns": breakdowns}
    with sqlite3.connect(OUT / "fyp.sqlite") as con:
        for name, df in tables.items():
            df.to_csv(OUT / f"{name}.csv", index=False)
            df.to_sql(name, con, if_exists="replace", index=False)
    for name, df in tables.items():
        print(f"{name}: {len(df)} rows")


if __name__ == "__main__":
    main()
