"""Injuries and suspensions.

Premier League: the official Fantasy Premier League data feed (public, no key), which the Premier League keeps up
to date during the week: each player's status (injured, doubtful, suspended, unavailable), a note such as
"Hamstring injury - Expected back 8 Nov" and a chance-of-playing percentage. Cached for 30 minutes.

Other competitions: API-Football (api-sports.io) when the user's key and plan cover the current season
(API_FOOTBALL_KEY in .streamlit/secrets.toml). The free plan does not, and then only the Premier League list
appears; the match centre falls back to team news derived from ESPN match sheets.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

import live

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src.process

BASE = "https://v3.football.api-sports.io"
FPL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_CLUBS = {"Leeds": "Leeds United", "Man City": "Manchester City", "Man Utd": "Manchester United",
             "Newcastle": "Newcastle United", "Nott'm Forest": "Nottingham Forest", "Spurs": "Tottenham",
             "Wolves": "Wolves", "West Ham": "West Ham"}
FPL_STATUS = {"i": "injured", "s": "suspended", "d": "doubtful", "n": "unavailable"}  # "u": left the club / on loan
FPL_POSITION = {1: "Goalkeeper", 2: "Defender", 3: "Midfielder", 4: "Forward"}
LEAGUE_IDS = {"Premier League": 39, "La Liga": 140, "Serie A": 135, "Champions League": 2}


def api_key() -> str | None:
    try:
        key = st.secrets.get("API_FOOTBALL_KEY")
    except Exception:  # no secrets file
        key = None
    return key or os.environ.get("API_FOOTBALL_KEY")


def season_year() -> int:
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1  # API-Football names a season by its start year


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def access_error() -> str | None:
    """None when the key can read this season's injuries; otherwise API-Football's reason (e.g. the free plan only
    covers past seasons). One request, cached for six hours."""
    key = api_key()
    if not key:
        return "no key"
    try:
        body = requests.get(f"{BASE}/injuries", params={"league": LEAGUE_IDS["Premier League"], "season": season_year()},
                            headers={"x-apisports-key": key}, timeout=20).json()
    except (requests.RequestException, ValueError):
        return "API-Football is unreachable"
    errors = body.get("errors")
    return "; ".join(str(v) for v in errors.values()) if isinstance(errors, dict) and errors else (str(errors) if errors else None)


def available() -> bool:
    return access_error() is None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def league_injuries(league_id: int, season: int) -> pd.DataFrame:
    key = api_key()
    if not key:
        return pd.DataFrame()
    try:
        r = requests.get(f"{BASE}/injuries", params={"league": league_id, "season": season},
                         headers={"x-apisports-key": key}, timeout=20)
        r.raise_for_status()
        body = r.json()
    except requests.RequestException:
        return pd.DataFrame()
    if body.get("errors"):
        st.session_state["injuries_error"] = body["errors"]
        return pd.DataFrame()
    rows = [{"player": x["player"]["name"], "type": x["player"].get("type"), "reason": x["player"].get("reason"),
             "team": x["team"]["name"], "fixture_id": x["fixture"]["id"],
             "fixture_date": pd.to_datetime(x["fixture"]["date"], utc=True)} for x in body.get("response", [])]
    return pd.DataFrame(rows)


def _our_team(name: str) -> str:
    """API-Football club names to ours ('Manchester United' / 'Inter' / 'Atletico Madrid')."""
    from matchcentre import fold, names_in
    ours = set(live.club_names().values())
    if name in ours:
        return name
    exact = [t for t in ours if fold(t) == fold(name)]  # 'Atletico Madrid' -> 'Atlético Madrid'
    if len(exact) == 1:
        return exact[0]
    hits = [t for t in ours if names_in(t, fold(name)) or names_in(name, fold(t))]
    return hits[0] if len(hits) == 1 else name


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def current() -> pd.DataFrame:
    """Each player's latest listing across the four competitions, for fixtures from the last week onwards."""
    if not available():
        return pd.DataFrame()
    frames = [league_injuries(lid, season_year()).assign(competition=comp) for comp, lid in LEAGUE_IDS.items()]
    df = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) else pd.DataFrame()
    if df.empty:
        return df
    recent = df[df.fixture_date >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)]
    latest = recent.sort_values("fixture_date").drop_duplicates(["team", "player"], keep="last")
    latest["club"] = latest.team.map(_our_team)
    return latest.reset_index(drop=True)


@st.cache_data(ttl=1800, show_spinner=False)
def fpl() -> pd.DataFrame:
    """Premier League players flagged by Fantasy Premier League, linked to our player table where possible."""
    try:
        body = requests.get(FPL, timeout=20, headers={"User-Agent": "FYP-TacticalProfiles/0.1 (academic project)"}).json()
    except (requests.RequestException, ValueError):
        return pd.DataFrame()
    teams = {t["id"]: FPL_CLUBS.get(t["name"], t["name"]) for t in body.get("teams", [])}
    rows = [{"club": teams.get(e["team"]), "fpl_name": f'{e["first_name"]} {e["second_name"]}', "web_name": e["web_name"],
             "kind": FPL_STATUS[e["status"]], "detail": e.get("news") or "",
             "chance": e.get("chance_of_playing_next_round"), "position": FPL_POSITION.get(e["element_type"], ""),
             "updated": pd.to_datetime(e.get("news_added"), utc=True, errors="coerce")}
            for e in body.get("elements", []) if e.get("status") in FPL_STATUS]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Link to our players (photo, shirt number, ESPN id) by club and name, as in src.process.build_players.
    import data
    from src.process.build_players import match_within
    df["player"], df["athlete_id"], df["photo"], df["jersey"] = df.web_name, None, None, None
    if data.players_ready():
        # Long-term injured players may not have played this season yet: use each player's latest row at the club.
        p = (data.players().sort_values("season").drop_duplicates(["team", "name"], keep="last")
             .reset_index(drop=True))
        idx = match_within(df.assign(team=df.club), p, ["team"], "fpl_name", "name")
        web = match_within(df.assign(team=df.club), p, ["team"], "web_name", "name")
        idx = idx.fillna(web)
        hit = idx.dropna().astype(int)
        df.loc[hit.index, "player"] = p.loc[hit.to_numpy(), "name"].to_numpy()
        for col in ("athlete_id", "photo", "jersey"):
            df.loc[hit.index, col] = p.loc[hit.to_numpy(), col].to_numpy()
    df["source"] = "Fantasy Premier League"
    return df


def for_club(club: str) -> pd.DataFrame:
    """Current injury and suspension list for one club: player, kind (injured / suspended / doubtful /
    unavailable), detail, chance (% for doubts), photo, jersey, position, athlete_id, source."""
    f = fpl()
    if len(f) and club in set(f.club):
        order = {"suspended": 0, "injured": 1, "unavailable": 2, "doubtful": 3}
        return f[f.club == club].sort_values("kind", key=lambda k: k.map(order)).reset_index(drop=True)
    df = current()
    if df.empty:
        return df
    df = df[df.club == club]
    kind = ["doubtful" if t == "Questionable" else "suspended" if any(k in str(r).lower() for k in ("card", "suspend"))
            else "injured" for t, r in zip(df.type, df.reason)]
    return pd.DataFrame({"player": df.player, "kind": kind, "detail": df.reason.fillna(""), "chance": None,
                         "photo": None, "jersey": None, "position": "", "athlete_id": None,
                         "source": "API-Football"}).reset_index(drop=True)


def unavailable_ids(club: str) -> dict[str, str]:
    """athlete_id -> 'injured' / 'suspended' / 'unavailable' / 'doubtful (25%)' for players expected to miss the
    next match: everyone injured, suspended or unavailable, and doubts at 25% or less."""
    df = for_club(club)
    if df.empty or "athlete_id" not in df:
        return {}
    out = {}
    for r in df.dropna(subset=["athlete_id"]).itertuples():
        chance = r.chance if r.chance == r.chance else None  # NaN -> None
        if r.kind != "doubtful" or (chance is not None and chance <= 25):
            out[str(r.athlete_id)] = r.kind if r.kind != "doubtful" else f"doubtful ({int(chance)}%)"
    return out


def doubts(club: str) -> dict[str, str]:
    """athlete_id -> 'doubtful (75%)' for doubts who are still likely to play."""
    df = for_club(club)
    if df.empty or "athlete_id" not in df:
        return {}
    d = df[(df.kind == "doubtful") & df.athlete_id.notna() & (df.chance.fillna(0) > 25)]
    return {str(a): f"doubtful ({int(c)}%)" for a, c in zip(d.athlete_id, d.chance)}
