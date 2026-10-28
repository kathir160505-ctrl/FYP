"""Collect league seasons from 2025/26 (the thesis season) to the current one (Understat + ESPN).

Run from the project root, one league per process if you want them in parallel:
    python -m src.collect.history                               # all leagues, 2025/26 to now
    python -m src.collect.history --league ENG --seasons 2526-2627
    python -m src.collect.history --league ITA --current       # refresh only the current season

Each league-season is written to data/raw/history/<season>/<league>/ as soon as it is complete, so the
job can be stopped and resumed. Finished seasons are skipped on later runs; the current season is
always refreshed. Raw ESPN responses are cached, so nothing is downloaded twice.

Files per league-season:
- us_matches.csv     Understat team-match stats (xG, deep completions, PPDA, goals, points)
- us_shots.csv       Understat shot events (xG, location, situation, result)
- us_breakdowns.csv  Understat team-page splits (attack speed, shot zone, situation)
- espn_stats.csv     ESPN team box stats for every completed match (possession, passes, crosses, long balls)
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import soccerdata as sd
import soccerdata.understat as sd_understat
from soccerdata.understat import UNDERSTAT_URL

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "history"
ESPN_CACHE = ROOT / "data" / "raw" / "espn" / "json"  # shared with src/collect/espn.py (same file names)
API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUES = {"ENG": ("ENG-Premier League", "eng.1"), "ESP": ("ESP-La Liga", "esp.1"), "ITA": ("ITA-Serie A", "ita.1")}
ESPN_STATS = ["possessionPct", "accuratePasses", "totalPasses", "totalCrosses", "accurateCrosses", "totalLongBalls",
              "accurateLongBalls", "totalShots", "shotsOnTarget", "wonCorners", "effectiveTackles", "interceptions"]
BREAKDOWN_BLOCKS = ("attackSpeed", "shotZone", "situation")
WORKERS = 4
FIRST_SEASON = "2526"  # the thesis season; the app covers it and every season since

# soccerdata's label maps miss these raw Understat values (see CLAUDE.md).
sd_understat.SHOT_BODY_PARTS.update({"Head": "Head", "OtherBodyPart": "Other"})
sd_understat.SHOT_SITUATIONS.update({"Penalty": "Penalty"})


def current_season() -> str:
    now = datetime.now(timezone.utc)
    start = now.year if now.month >= 7 else now.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def season_range(spec: str) -> list[str]:
    first, last = spec.split("-")
    y0, y1 = int(first[:2]), int(last[:2])
    return [f"{y:02d}{(y + 1) % 100:02d}" for y in range(y0, y1 + 1)]


def start_year(season: str) -> int:
    return 2000 + int(season[:2])


# ---------------------------------------------------------------- ESPN
def _espn(url: str, cache: Path | None) -> dict:
    if cache is not None and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=30)
            if resp.ok:
                break
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"ESPN request failed: {url}")
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(resp.text, encoding="utf-8")
    return resp.json()


def espn_season(code: str, season: str, is_current: bool) -> pd.DataFrame:
    year = start_year(season)
    months = [f"{year}{m:02d}" for m in range(7, 13)] + [f"{year + 1}{m:02d}" for m in range(1, 8)]
    this_month = datetime.now(timezone.utc).strftime("%Y%m")
    events = {}
    for month in months:
        if month > this_month:
            break
        cache = None if (is_current and month >= this_month) else ESPN_CACHE / code / f"scoreboard_{month}.json"
        for ev in _espn(f"{API}/{code}/scoreboard?dates={month}", cache).get("events", []):
            if ev.get("season", {}).get("year") == year and ev["status"]["type"]["completed"]:
                events[ev["id"]] = ev

    def fetch(ev: dict) -> list[dict]:
        summary = _espn(f"{API}/{code}/summary?event={ev['id']}", ESPN_CACHE / code / f"summary_{ev['id']}.json")
        sides = {c["team"]["id"]: c for c in ev["competitions"][0]["competitors"]}
        home = next(c for c in sides.values() if c["homeAway"] == "home")
        away = next(c for c in sides.values() if c["homeAway"] == "away")
        rows = []
        for team in summary.get("boxscore", {}).get("teams", []):
            stats = {s["name"]: s.get("displayValue") for s in team.get("statistics", [])}
            side = sides.get(team["team"]["id"], {})
            rows.append({"event_id": ev["id"], "date": ev["date"], "espn_home": home["team"]["displayName"],
                         "espn_away": away["team"]["displayName"], "home_score": home.get("score"),
                         "away_score": away.get("score"), "espn_team": team["team"]["displayName"],
                         "home_away": side.get("homeAway"), **{k: stats.get(k) for k in ESPN_STATS}})
        return rows

    with ThreadPoolExecutor(WORKERS) as pool:
        rows = [r for chunk in pool.map(fetch, events.values()) for r in chunk]
    df = pd.DataFrame(rows)
    if not df.empty:
        df[ESPN_STATS] = df[ESPN_STATS].apply(pd.to_numeric, errors="coerce")
    return df


# ---------------------------------------------------------------- Understat
def understat_season(league: str, season: str, is_current: bool) -> dict[str, pd.DataFrame]:
    if is_current:  # refresh the stored league file so the cached reader sees new matches
        sd.Understat(leagues=league, seasons=season, no_cache=True).read_team_match_stats()
    us = sd.Understat(leagues=league, seasons=season)
    matches = us.read_team_match_stats().reset_index()
    matches = matches[matches["home_xg"].notna()]
    shots = us.read_shot_events().reset_index()
    us._ensure_cookies()
    rows = []
    for team in sorted(set(matches["home_team"]) | set(matches["away_team"])):
        slug = team.replace(" ", "_")
        cache = us.data_dir / f"team_{slug}_{start_year(season)}.json"
        if is_current and cache.exists():
            cache.unlink()
        data = json.load(us._request_api(f"{UNDERSTAT_URL}/getTeamData/{slug}/{start_year(season)}", cache))
        for block in BREAKDOWN_BLOCKS:
            for category, s in data["statistics"].get(block, {}).items():
                rows.append({"team": team, "block": block, "category": category, "shots": s["shots"],
                             "goals": s["goals"], "xg": s["xG"], "shots_against": s["against"]["shots"],
                             "goals_against": s["against"]["goals"], "xg_against": s["against"]["xG"]})
    return {"us_matches": matches, "us_shots": shots, "us_breakdowns": pd.DataFrame(rows)}


def collect(key: str, season: str, force: bool) -> None:
    league, code = LEAGUES[key]
    out = OUT / season / key
    is_current = season == current_season()
    if (out / "espn_stats.csv").exists() and not (is_current or force):
        print(f"{key} {season}: already collected, skipping")
        return
    t0 = time.time()
    tables = understat_season(league, season, is_current)
    tables["espn_stats"] = espn_season(code, season, is_current)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
    n_us, n_espn = len(tables["us_matches"]), tables["espn_stats"]["event_id"].nunique()
    print(f"{key} {season}: Understat {n_us} matches, {len(tables['us_shots'])} shots; ESPN {n_espn} matches "
          f"({time.time() - t0:.0f}s)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=[*LEAGUES, "all"], default="all")
    ap.add_argument("--seasons", default=f"{FIRST_SEASON}-{current_season()}")
    ap.add_argument("--current", action="store_true", help="only refresh the current season")
    ap.add_argument("--force", action="store_true", help="re-collect finished seasons too")
    args = ap.parse_args()
    keys = list(LEAGUES) if args.league == "all" else [args.league]
    seasons = [current_season()] if args.current else season_range(args.seasons)
    for key in keys:
        for season in seasons:
            try:
                collect(key, season, args.force)
            except Exception as exc:  # keep going; a failed season is retried on the next run
                print(f"{key} {season}: FAILED {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
