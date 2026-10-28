"""Injuries and suspensions from API-Football (api-sports.io), when the user has configured a free API key
(API_FOOTBALL_KEY in .streamlit/secrets.toml). Without a key every function returns empty results and the app
falls back to the team news it can derive from ESPN match sheets.

API-Football lists, per fixture, the players expected to miss it (type "Missing Fixture" for injuries and
suspensions, "Questionable" for doubts) with a reason ("Knee Injury", "Red Card", ...). One request per league and
season returns the whole list; each league is fetched at most every six hours to stay well inside the free
plan's 100 requests per day.
"""
import os
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

import live

BASE = "https://v3.football.api-sports.io"
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
    hits = [t for t in ours if names_in(t, fold(name)) or names_in(name, fold(t))]
    return hits[0] if len(hits) == 1 else name


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def current() -> pd.DataFrame:
    """Each player's latest listing across the four competitions, for fixtures from the last week onwards."""
    if not api_key():
        return pd.DataFrame()
    frames = [league_injuries(lid, season_year()).assign(competition=comp) for comp, lid in LEAGUE_IDS.items()]
    df = pd.concat([f for f in frames if len(f)], ignore_index=True) if any(len(f) for f in frames) else pd.DataFrame()
    if df.empty:
        return df
    recent = df[df.fixture_date >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)]
    latest = recent.sort_values("fixture_date").drop_duplicates(["team", "player"], keep="last")
    latest["club"] = latest.team.map(_our_team)
    return latest.reset_index(drop=True)


def for_club(club: str) -> pd.DataFrame:
    df = current()
    return df[df.club == club] if len(df) else df
