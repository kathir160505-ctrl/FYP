"""Collect Understat 2025/26 data: team-match stats, shot events, and team-page breakdowns.

Outputs (data/raw/understat/):
- team_match_stats.csv  one row per match (home/away xG, goals, PPDA, deep completions)
- shots.csv             one row per shot (team, xG, x/y location, situation, result)
- team_breakdowns.csv   one row per team x block x category (attackSpeed, shotZone, situation)
"""
import json

import pandas as pd
import soccerdata as sd
from soccerdata.understat import UNDERSTAT_URL

from config import LEAGUES, RAW, SEASON, UNDERSTAT_SEASON, log_step

OUT = RAW / "understat"
BLOCKS = ("attackSpeed", "shotZone", "situation")


def team_breakdowns(us: sd.Understat, league: str, teams: list[str]) -> pd.DataFrame:
    rows = []
    for team in teams:
        slug = team.replace(" ", "_")
        cache = us.data_dir / f"team_{slug}_{UNDERSTAT_SEASON}.json"
        data = json.load(us._request_api(f"{UNDERSTAT_URL}/getTeamData/{slug}/{UNDERSTAT_SEASON}", cache))
        for block in BLOCKS:
            for category, s in data["statistics"][block].items():
                rows.append({
                    "league": league, "team": team, "block": block, "category": category,
                    "shots": s["shots"], "goals": s["goals"], "xg": s["xG"],
                    "shots_against": s["against"]["shots"], "goals_against": s["against"]["goals"],
                    "xg_against": s["against"]["xG"],
                })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    matches, shots, breakdowns = [], [], []
    for league in LEAGUES:
        us = sd.Understat(leagues=league, seasons=SEASON)
        tm = us.read_team_match_stats().reset_index()
        matches.append(tm)
        shots.append(us.read_shot_events().reset_index())
        us._ensure_cookies()
        teams = sorted(set(tm["home_team"]) | set(tm["away_team"]))
        breakdowns.append(team_breakdowns(us, league, teams))
        print(f"{league}: {len(tm)} matches, {len(teams)} teams")

    outputs = {
        "team_match_stats.csv": pd.concat(matches, ignore_index=True),
        "shots.csv": pd.concat(shots, ignore_index=True),
        "team_breakdowns.csv": pd.concat(breakdowns, ignore_index=True),
    }
    for name, df in outputs.items():
        df.to_csv(OUT / name, index=False)
    log_step("understat", soccerdata=sd.__version__, rows={k: len(v) for k, v in outputs.items()})


if __name__ == "__main__":
    main()
