"""Phase C: player data for the three leagues, 2025/26 onwards.

Run from the project root after src.collect.history:  python -m src.collect.players
                                                                             python -m src.collect.players --current

Writes data/raw/players/:
- understat_<season>.csv   attacking season stats per player and club (xG, xA, shots, key passes, xGChain, ...)
- fbref_<table>_<season>.csv  FBref 'standard' (minutes, nation, position, birth year), 'misc' (tackles won,
                              interceptions, fouls, crosses) and 'keeper' (saves, clean sheets) tables
- lineups.csv              every player on every league match sheet: starter, formation slot, position,
                           minutes on/off, goals, assists, cards (parsed from the cached ESPN match summaries)
- wikidata_players.csv     footballers linked to our clubs on Wikidata, with birth date and a Commons photo
- wikidata_names.csv       footballers whose English label equals a player name in our data (for players whose
                           Wikidata entry is not linked to their current club); birth year decides between namesakes

Finished seasons are kept; the current season is always refreshed. ESPN summaries are read from the cache the
history collector fills, so this script makes no ESPN requests.
"""
import argparse
import json
from pathlib import Path

import pandas as pd
import soccerdata as sd

from src.collect.history import ESPN_CACHE, FIRST_SEASON, LEAGUES, ROOT, current_season, season_range
from src.collect.legacy import run_batched

OUT = ROOT / "data" / "raw" / "players"
FBREF_TABLES = ("standard", "misc", "keeper")

# Footballers whose spell at one of our clubs is open or ended after the thesis season began.
WIKIDATA_PLAYERS = """SELECT ?club ?p ?pLabel ?born ?img WHERE {
  VALUES ?club { %s }
  ?p p:P54 ?st . ?st ps:P54 ?club . ?p wdt:P106 wd:Q937857 ; wdt:P569 ?born .
  OPTIONAL { ?st pq:P582 ?end }
  FILTER(?born >= "1980-01-01"^^xsd:dateTime && (!BOUND(?end) || ?end >= "2025-07-01"^^xsd:dateTime))
  OPTIONAL { ?p wdt:P18 ?img }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""


WIKIDATA_BY_NAME = """SELECT ?name ?p ?born ?img WHERE {
  VALUES ?name { %s } ?p rdfs:label ?name ; wdt:P106 wd:Q937857 ; wdt:P569 ?born .
  FILTER(?born >= "1980-01-01"^^xsd:dateTime) OPTIONAL { ?p wdt:P18 ?img } }"""


def wikidata_by_name(names: list[str], batch: int = 80) -> pd.DataFrame:
    from src.collect.legacy import PAUSE, sparql
    import time
    rows = []
    for i in range(0, len(names), batch):
        vals = " ".join('"%s"@en' % n.replace("\\", "").replace('"', "") for n in names[i:i + batch])
        rows += sparql(WIKIDATA_BY_NAME % vals)
        time.sleep(PAUSE)
    df = pd.DataFrame(rows)
    if len(df):
        df["p"] = df.p.str.rsplit("/", n=1).str[1]
    return df


def flatten(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index()
    df.columns = ["_".join(c for c in col if c).strip("_") if isinstance(col, tuple) else col for col in df.columns]
    return df


def understat(season: str, fresh: bool) -> pd.DataFrame:
    leagues = [v[0] for v in LEAGUES.values()]
    return sd.Understat(leagues=leagues, seasons=season, no_cache=fresh).read_player_season_stats().reset_index()


def fbref(season: str, fresh: bool) -> dict[str, pd.DataFrame]:
    leagues = [v[0] for v in LEAGUES.values()]
    fb = sd.FBref(leagues=leagues, seasons=season, no_cache=fresh)
    return {t: flatten(fb.read_player_season_stats(stat_type=t)) for t in FBREF_TABLES}


def lineups() -> pd.DataFrame:
    """Players on every cached match sheet of our league seasons."""
    events = []
    for path in (ROOT / "data" / "raw" / "history").glob("*/*/espn_stats.csv"):
        code = dict((k, v[1]) for k, v in LEAGUES.items())[path.parent.name]
        events += [(code, int(path.parent.parent.name), e) for e in pd.read_csv(path).event_id.unique()]
    rows = []
    for code, season, event in events:
        cache = ESPN_CACHE / code / f"summary_{event}.json"
        if not cache.exists():
            continue
        summary = json.loads(cache.read_text(encoding="utf-8"))
        date = summary.get("header", {}).get("competitions", [{}])[0].get("date")
        for side in summary.get("rosters", []):
            for p in side.get("roster", []):
                stats = {s["name"]: s.get("value") for s in p.get("stats", [])}
                plays = p.get("plays", [])
                sub_minute = next((pl["clock"]["displayValue"] for pl in plays if pl.get("substitution")), None)
                rows.append({
                    "competition": code, "season": season, "event_id": event, "date": date,
                    "espn_team": side["team"]["displayName"], "home_away": side.get("homeAway"),
                    "formation": side.get("formation"), "athlete_id": p["athlete"]["id"],
                    "player": p["athlete"]["displayName"], "jersey": p.get("jersey"), "starter": p.get("starter"),
                    "formation_place": p.get("formationPlace"), "position": p.get("position", {}).get("displayName"),
                    "position_abbr": p.get("position", {}).get("abbreviation"),
                    "subbed_in": p.get("subbedIn"), "subbed_out": p.get("subbedOut"), "sub_minute": sub_minute,
                    "goals": stats.get("totalGoals"), "assists": stats.get("goalAssists"),
                    "shots": stats.get("totalShots"), "shots_on_target": stats.get("shotsOnTarget"),
                    "saves": stats.get("saves"), "yellow": stats.get("yellowCards"), "red": stats.get("redCards")})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", action="store_true", help="only refresh the current season")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    now = current_season()
    seasons = [now] if args.current else season_range(f"{FIRST_SEASON}-{now}")
    for season in seasons:
        fresh = season == now
        path = OUT / f"understat_{season}.csv"
        if fresh or not path.exists():
            df = understat(season, fresh)
            df.to_csv(path, index=False, encoding="utf-8")
            print(f"Understat {season}: {len(df):,} player-club rows", flush=True)
        for table in FBREF_TABLES:
            if fresh or not (OUT / f"fbref_{table}_{season}.csv").exists():
                for t, df in fbref(season, fresh).items():
                    df.to_csv(OUT / f"fbref_{t}_{season}.csv", index=False, encoding="utf-8")
                    print(f"FBref {t} {season}: {len(df):,} rows", flush=True)
                break
    lu = lineups()
    lu.to_csv(OUT / "lineups.csv", index=False, encoding="utf-8")
    print(f"Lineups: {lu.event_id.nunique():,} matches, {len(lu):,} player rows", flush=True)
    clubs = pd.read_csv(ROOT / "data" / "reference" / "clubs_wikidata.csv")
    wd = run_batched(WIKIDATA_PLAYERS, clubs.wikidata.tolist())
    wd.to_csv(OUT / "wikidata_players.csv", index=False, encoding="utf-8")
    print(f"Wikidata: {wd.p.nunique():,} players, {wd.img.notna().sum():,} with a photo", flush=True)
    names = sorted(set(pd.concat([pd.read_csv(f).player for f in OUT.glob("understat_*.csv")])))
    byname = wikidata_by_name(names)
    byname.to_csv(OUT / "wikidata_names.csv", index=False, encoding="utf-8")
    print(f"Wikidata by name: {byname.name.nunique():,} names found, {byname.img.notna().sum():,} photos", flush=True)


if __name__ == "__main__":
    main()
