"""Collect ESPN 2025/26 per-match team statistics from the public site API.

soccerdata's ESPN.read_matchsheet is broken for this season (KeyError: 'form'),
so this calls the JSON API directly. Raw responses are cached in data/raw/espn/json/,
so a re-run only downloads what is missing.

Output: data/raw/espn/team_match_stats.csv, one row per team per match.
"""
import json
import time

import pandas as pd
import requests

from config import LEAGUES, RAW, SEASON_MONTHS, log_step

API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
OUT = RAW / "espn"
CACHE = OUT / "json"
DELAY_S = 0.3  # stay polite to the public API


def get_json(url: str, cache_file) -> dict:
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    for attempt in range(4):
        resp = requests.get(url, timeout=30)
        if resp.ok:
            break
        time.sleep(2 ** attempt)
    resp.raise_for_status()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(resp.text, encoding="utf-8")
    time.sleep(DELAY_S)
    return resp.json()


def season_events(code: str) -> list[dict]:
    events = {}
    for month in SEASON_MONTHS:
        data = get_json(f"{API}/{code}/scoreboard?dates={month}", CACHE / code / f"scoreboard_{month}.json")
        for ev in data.get("events", []):
            if ev["status"]["type"]["completed"]:
                events[ev["id"]] = ev
    return list(events.values())


def match_rows(league: str, code: str, ev: dict) -> list[dict]:
    summary = get_json(f"{API}/{code}/summary?event={ev['id']}", CACHE / code / f"summary_{ev['id']}.json")
    comp = {c["team"]["id"]: c for c in ev["competitions"][0]["competitors"]}
    rows = []
    for team in summary["boxscore"]["teams"]:
        tid = team["team"]["id"]
        row = {
            "league": league, "event_id": ev["id"], "date": ev["date"],
            "team_id": tid, "team": team["team"]["displayName"],
            "home_away": comp[tid]["homeAway"], "score": comp[tid].get("score"),
        }
        row.update({s["name"]: s.get("displayValue") for s in team["statistics"]})
        rows.append(row)
    return rows


def main() -> None:
    rows, counts = [], {}
    for league, meta in LEAGUES.items():
        events = season_events(meta["espn"])
        for i, ev in enumerate(events, 1):
            rows.extend(match_rows(league, meta["espn"], ev))
            if i % 50 == 0:
                print(f"{league}: {i}/{len(events)} matches")
        counts[league] = len(events)
        print(f"{league}: {len(events)} completed matches")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "team_match_stats.csv", index=False)
    log_step("espn", matches=counts, rows=len(df))


if __name__ == "__main__":
    main()
