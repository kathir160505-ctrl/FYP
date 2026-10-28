"""Live 2026/27 data for the Matchday page: ESPN news and fixtures (fetched at view time, cached) and the
current-season form table written by `python -m src.collect.live`."""
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

from data import REF, ROOT, readable

LIVE = ROOT / "data" / "live"
API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUE_CODES = {"Premier League": "eng.1", "La Liga": "esp.1", "Serie A": "ita.1"}
LOCAL_TZ = timezone(timedelta(hours=8), "MYT")


def _get(url: str) -> dict:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=900, show_spinner=False)
def news(limit_per_league: int = 12) -> pd.DataFrame:
    rows = []
    for league, code in LEAGUE_CODES.items():
        try:
            articles = _get(f"{API}/{code}/news?limit={limit_per_league}").get("articles", [])
        except requests.RequestException:
            continue
        for a in articles:
            link = a.get("links", {}).get("web", {}).get("href")
            if not link:
                continue
            img = next((i.get("url") for i in a.get("images", []) if i.get("url")), None)
            rows.append({"league": league, "headline": a.get("headline", ""), "description": a.get("description", ""),
                         "published": pd.to_datetime(a.get("published"), utc=True, errors="coerce"),
                         "image": img, "link": link})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates("link").sort_values("published", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def _scoreboard(code: str, month: str) -> list[dict]:
    try:
        return _get(f"{API}/{code}/scoreboard?dates={month}").get("events", [])
    except requests.RequestException:
        return []


def fixtures(days_back: int = 7, days_ahead: int = 10) -> pd.DataFrame:
    """Results from the last `days_back` days, live matches, and fixtures in the next `days_ahead` days."""
    now = datetime.now(timezone.utc)
    months = sorted({(now + timedelta(days=d)).strftime("%Y%m") for d in (-days_back, 0, days_ahead)})
    rows = []
    for league, code in LEAGUE_CODES.items():
        for month in months:
            for ev in _scoreboard(code, month):
                comp = ev["competitions"][0]
                sides = {c["homeAway"]: c for c in comp["competitors"]}
                if {"home", "away"} - set(sides):
                    continue
                st_type = ev["status"]["type"]
                rows.append({
                    "league": league, "id": ev["id"], "kickoff": pd.to_datetime(ev["date"], utc=True),
                    "state": st_type.get("state"), "status": st_type.get("shortDetail") or st_type.get("detail", ""),
                    **{f"{s}_{k}": v for s in ("home", "away") for k, v in {
                        "espn": sides[s]["team"]["displayName"], "abbr": sides[s]["team"].get("abbreviation", ""),
                        "logo": sides[s]["team"].get("logo"), "color": readable("#" + sides[s]["team"].get("color", "6B7280")),
                        "score": sides[s].get("score")}.items()}})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("id")
    window = (df.kickoff >= now - timedelta(days=days_back)) & (df.kickoff <= now + timedelta(days=days_ahead))
    df = df[window].copy()
    names = club_names()
    df["home"] = df.home_espn.map(names).fillna(df.home_espn)
    df["away"] = df.away_espn.map(names).fillna(df.away_espn)
    df["local"] = df.kickoff.dt.tz_convert(LOCAL_TZ)
    return df.sort_values("kickoff").reset_index(drop=True)


@st.cache_data
def club_names() -> dict:
    teams = pd.concat([pd.read_csv(REF / "teams.csv"), pd.read_csv(REF / "teams_promoted_2627.csv")])
    return dict(zip(teams.espn, teams.team))


@st.cache_data(ttl=600)
def form() -> pd.DataFrame:
    path = LIVE / "team_form.csv"
    return pd.read_csv(path).set_index("team") if path.exists() else pd.DataFrame()


@st.cache_data(ttl=600)
def meta() -> dict:
    path = LIVE / "meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def time_ago(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return ""
    mins = int((datetime.now(timezone.utc) - ts.to_pydatetime()).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 1)}m ago"
    if mins < 60 * 24:
        return f"{mins // 60}h ago"
    return f"{mins // (60 * 24)}d ago"
