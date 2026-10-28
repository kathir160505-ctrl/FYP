"""Phase B: Champions League matches and ESPN box stats, 2025/26 onwards (league phase to the final).

Run from the project root:  python -m src.collect.ucl            (finished seasons are kept, the current one refreshed)
                            python -m src.collect.ucl --force    (re-collect every season)

Writes data/raw/ucl/<season>/ucl_stats.csv: one row per team per completed match, with the stage, score and the
same ESPN box stats as the league data. Understat has no Champions League data, so there is no xG.
Qualifying rounds (a separate ESPN competition) are not included.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

from src.collect.history import (API, ESPN_CACHE, ESPN_STATS, FIRST_SEASON, ROOT, WORKERS, _espn, current_season,
                                 season_range, start_year)

CODE = "uefa.champions"
OUT = ROOT / "data" / "raw" / "ucl"
EXTRA_STATS = ["foulsCommitted", "saves", "blockedShots", "totalTackles", "effectiveClearance"]


def collect_season(season: str, is_current: bool) -> pd.DataFrame:
    year = start_year(season)
    months = [f"{year}{m:02d}" for m in range(7, 13)] + [f"{year + 1}{m:02d}" for m in range(1, 7)]
    this_month = datetime.now(timezone.utc).strftime("%Y%m")
    events = {}
    for month in months:
        if month > this_month:
            break
        cache = None if (is_current and month >= this_month) else ESPN_CACHE / CODE / f"scoreboard_{month}.json"
        for ev in _espn(f"{API}/{CODE}/scoreboard?dates={month}", cache).get("events", []):
            if ev.get("season", {}).get("year") == year and ev["status"]["type"]["completed"]:
                events[ev["id"]] = ev

    def fetch(ev: dict) -> list[dict]:
        summary = _espn(f"{API}/{CODE}/summary?event={ev['id']}", ESPN_CACHE / CODE / f"summary_{ev['id']}.json")
        comp = ev["competitions"][0]
        sides = {c["team"]["id"]: c for c in comp["competitors"]}
        home = next(c for c in sides.values() if c["homeAway"] == "home")
        away = next(c for c in sides.values() if c["homeAway"] == "away")
        rows = []
        for team in summary.get("boxscore", {}).get("teams", []):
            stats = {s["name"]: s.get("displayValue") for s in team.get("statistics", [])}
            side = sides.get(team["team"]["id"], {})
            rows.append({"event_id": ev["id"], "date": ev["date"], "stage": ev["season"].get("slug"),
                         "espn_home": home["team"]["displayName"], "espn_away": away["team"]["displayName"],
                         "home_score": home.get("score"), "away_score": away.get("score"),
                         "home_winner": home.get("winner"), "away_winner": away.get("winner"),
                         "espn_team": team["team"]["displayName"], "logo": team["team"].get("logo"),
                         "home_away": side.get("homeAway"),
                         **{k: stats.get(k) for k in ESPN_STATS + EXTRA_STATS}})
        return rows

    with ThreadPoolExecutor(WORKERS) as pool:
        rows = [r for chunk in pool.map(fetch, events.values()) for r in chunk]
    df = pd.DataFrame(rows)
    if not df.empty:
        num = ESPN_STATS + EXTRA_STATS + ["home_score", "away_score"]
        df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    now = current_season()
    for season in season_range(f"{FIRST_SEASON}-{now}"):
        path = OUT / season / "ucl_stats.csv"
        is_current = season == now
        if path.exists() and not (is_current or args.force):
            print(f"UCL {season}: kept")
            continue
        df = collect_season(season, is_current)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8")
        n = df.event_id.nunique() if len(df) else 0
        print(f"UCL {season}: {n} matches, {df.espn_team.nunique() if len(df) else 0} clubs")


if __name__ == "__main__":
    main()
