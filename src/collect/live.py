"""Refresh current-season (2026/27) form for the Matchday page's attacking-style predictions.

Run from the project root:  python -m src.collect.live

Pulls every played 2026/27 league match (Understat xG/shots, ESPN possession/passing), computes
each club's season-to-date and last-5 attacking profile exactly as the prediction model expects,
and writes small tables the dashboard reads:
- data/live/team_form.csv  inputs for predict_more_attacking(), keyed by canonical club name
- data/live/team_meta.csv  crest, colours and abbreviation for every current club
- data/live/meta.json      refresh time and match counts
Raw responses are cached in data/raw/live/ so re-runs only fetch new matches.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import soccerdata as sd
import soccerdata.understat as sd_understat

from src.predict.model import add_attacking_index, team_form
from src.process.features import shot_summary, understat_long

ROOT = Path(__file__).resolve().parents[2]
REF, OUT, CACHE = ROOT / "data" / "reference", ROOT / "data" / "live", ROOT / "data" / "raw" / "live" / "espn"
SEASON = "2627"
MONTHS = [f"2026{m:02d}" for m in range(8, 13)] + [f"2027{m:02d}" for m in range(1, 7)]
LEAGUES = {"ENG-Premier League": "eng.1", "ESP-La Liga": "esp.1", "ITA-Serie A": "ita.1"}
API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ESPN_STATS = ["possessionPct", "accuratePasses", "totalPasses", "totalCrosses", "totalLongBalls"]

sd_understat.SHOT_BODY_PARTS.update({"Head": "Head", "OtherBodyPart": "Other"})
sd_understat.SHOT_SITUATIONS.update({"Penalty": "Penalty"})


def club_names() -> pd.DataFrame:
    return pd.concat([pd.read_csv(REF / "teams.csv"), pd.read_csv(REF / "teams_promoted_2627.csv")], ignore_index=True)


def espn_json(url: str, cache_file: Path | None) -> dict:
    if cache_file is not None and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    if cache_file is not None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(resp.text, encoding="utf-8")
    time.sleep(0.3)
    return resp.json()


def espn_played(code: str, today: str) -> tuple[pd.DataFrame, list[dict]]:
    """Team stats for every completed match this season, plus club metadata seen on the scoreboards."""
    rows, meta = [], {}
    for month in MONTHS:
        if month > today[:6]:
            break
        # Past months never change; the current month is re-fetched on every run.
        cache = CACHE / code / f"scoreboard_{month}.json" if month < today[:6] else None
        for ev in espn_json(f"{API}/{code}/scoreboard?dates={month}", cache).get("events", []):
            comps = {c["team"]["id"]: c for c in ev["competitions"][0]["competitors"]}
            for c in comps.values():
                t = c["team"]
                meta[t["displayName"]] = {"espn": t["displayName"], "abbr": t.get("abbreviation"),
                                          "color": "#" + t.get("color", "888888"), "logo": t.get("logo")}
            if not ev["status"]["type"]["completed"]:
                continue
            summary = espn_json(f"{API}/{code}/summary?event={ev['id']}", CACHE / code / f"summary_{ev['id']}.json")
            home = next(c["team"]["displayName"] for c in comps.values() if c["homeAway"] == "home")
            away = next(c["team"]["displayName"] for c in comps.values() if c["homeAway"] == "away")
            for team in summary.get("boxscore", {}).get("teams", []):
                stats = {s["name"]: s.get("displayValue") for s in team.get("statistics", [])}
                rows.append({"espn_home": home, "espn_away": away, "espn_team": team["team"]["displayName"],
                             **{k: stats.get(k) for k in ESPN_STATS}})
    df = pd.DataFrame(rows)
    df[ESPN_STATS] = df[ESPN_STATS].apply(pd.to_numeric, errors="coerce")
    return df, list(meta.values())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = club_names()
    us_to_team, espn_to_team = dict(zip(names.understat, names.team)), dict(zip(names.espn, names.team))
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    frames, metas, counts = [], [], {}
    for league, code in LEAGUES.items():
        # A no-cache read refreshes the stored league file, so the cached reader below sees new matches too.
        sd.Understat(leagues=league, seasons=SEASON, no_cache=True).read_team_match_stats()
        us = sd.Understat(leagues=league, seasons=SEASON)
        matches = us.read_team_match_stats().reset_index()
        matches = matches[matches["home_xg"].notna()]
        shots = us.read_shot_events().reset_index()
        tm = understat_long(matches).merge(shot_summary(shots), on=["game_id", "team"], how="left")
        tm[["shots", "shots_on_target", "box_shots"]] = tm[["shots", "shots_on_target", "box_shots"]].fillna(0)
        for col in ("team", "opponent", "home_team", "away_team"):
            tm[col] = tm[col].map(us_to_team)

        espn, meta = espn_played(code, today)
        espn["home_team"] = espn["espn_home"].map(espn_to_team)
        espn["away_team"] = espn["espn_away"].map(espn_to_team)
        espn["team"] = espn["espn_team"].map(espn_to_team)
        tm = tm.merge(espn[["home_team", "away_team", "team", *ESPN_STATS]], on=["home_team", "away_team", "team"],
                      how="inner")
        unmapped = sorted(set(m["espn"] for m in meta) - set(espn_to_team))
        if tm["team"].isna().any() or unmapped:
            raise SystemExit(f"{league}: unmapped club names {unmapped}; add them to data/reference/teams_promoted_2627.csv")
        frames.append(tm)
        metas += [{**m, "team": espn_to_team[m["espn"]], "league": league} for m in meta]
        counts[league] = int(tm["game_id"].nunique())
        print(f"{league}: {counts[league]} matches with full stats")

    tm = add_attacking_index(pd.concat(frames, ignore_index=True))
    form = team_form(tm)
    form["matches"] = form["team"].map(tm.groupby("team").size())
    form.to_csv(OUT / "team_form.csv", index=False)
    pd.DataFrame(metas).drop_duplicates("team")[["league", "team", "abbr", "color", "logo"]].to_csv(
        OUT / "team_meta.csv", index=False)
    (OUT / "meta.json").write_text(json.dumps({
        "season": "2026/27", "updated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "matches": counts, "clubs": int(form["team"].nunique())}, indent=1), encoding="utf-8")
    print(f"team_form: {len(form)} clubs -> {OUT}")


if __name__ == "__main__":
    main()
