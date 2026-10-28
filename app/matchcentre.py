"""Match centre data: one ESPN match summary (fetched at view time, cached) turned into line-ups with per-player
events, the key-event timeline, team stats and video, plus Understat xG/shots when the match is in our data.
Highlights come from YouTube when a YouTube Data API key is configured (see highlights())."""
import os
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

import data
import live

STAT_ROWS = [("possessionPct", "Possession %"), ("totalShots", "Shots"), ("shotsOnTarget", "Shots on target"),
             ("totalPasses", "Passes"), ("passPct", "Pass accuracy"), ("totalCrosses", "Crosses"),
             ("wonCorners", "Corners"), ("totalTackles", "Tackles"), ("interceptions", "Interceptions"),
             ("saves", "Saves"), ("foulsCommitted", "Fouls"), ("offsides", "Offsides")]
EVENT_ICONS = {"Goal": "⚽", "Own Goal": "⚽", "Penalty - Scored": "⚽", "Yellow Card": "🟨", "Red Card": "🟥",
               "Substitution": "🔄", "Penalty - Missed": "❌", "Penalty - Saved": "🧤"}


@st.cache_data(ttl=600, show_spinner=False)
def summary(code: str, event_id: str) -> dict:
    try:
        resp = requests.get(f"{live.API}/{code}/summary?event={event_id}", timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {}


def header(s: dict) -> dict:
    comp = s.get("header", {}).get("competitions", [{}])[0]
    sides = {c["homeAway"]: c for c in comp.get("competitors", [])}
    names = live.club_names()
    out = {"date": pd.to_datetime(comp.get("date"), utc=True), "state": comp.get("status", {}).get("type", {}).get("state"),
           "status": comp.get("status", {}).get("type", {}).get("shortDetail", ""),
           "venue": s.get("gameInfo", {}).get("venue", {}).get("fullName", "")}
    for side in ("home", "away"):
        c = sides.get(side, {})
        t = c.get("team", {})
        espn = t.get("displayName", "")
        out[side] = {"espn": espn, "team": names.get(espn, espn), "score": c.get("score"),
                     "logo": next((l.get("href") for l in t.get("logos", []) if l.get("href")), t.get("logo")),
                     "abbr": t.get("abbreviation", ""), "color": data.readable("#" + (t.get("color") or "6B7280")),
                     "winner": c.get("winner"),
                     "alt_color": data.readable("#" + (t.get("alternateColor") or "9CA3AF"))}
    # Two similar kit colours would make the teams indistinguishable: switch the away side to its alternate.
    if not distinct(out["home"]["color"], out["away"]["color"]):
        alt = out["away"]["alt_color"]
        out["away"]["color"] = alt if distinct(out["home"]["color"], alt) and alt.upper() != "#FFFFFF" else "#111827"
    return out


def distinct(c1: str, c2: str) -> bool:
    rgb = lambda c: [int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]  # noqa: E731
    return sum((x - y) ** 2 for x, y in zip(rgb(c1), rgb(c2))) ** 0.5 > 110


def lineups(s: dict) -> dict[str, pd.DataFrame]:
    """Per side: every player on the sheet with starter flag, position code, shirt and event counts."""
    out = {}
    for side in s.get("rosters", []):
        rows = []
        for p in side.get("roster", []):
            st_ = {x["name"]: x.get("value") for x in p.get("stats", [])}
            sub = next((pl["clock"]["displayValue"] for pl in p.get("plays", []) if pl.get("substitution")), "")
            rows.append({"player": p["athlete"]["displayName"], "athlete_id": p["athlete"]["id"],
                         "jersey": p.get("jersey", ""), "starter": bool(p.get("starter")),
                         "position_abbr": p.get("position", {}).get("abbreviation", ""),
                         "position": p.get("position", {}).get("displayName", ""),
                         "subbed_in": bool(p.get("subbedIn")), "subbed_out": bool(p.get("subbedOut")), "sub_minute": sub,
                         "goals": int(st_.get("totalGoals") or 0), "assists": int(st_.get("goalAssists") or 0),
                         "own_goals": int(st_.get("ownGoals") or 0), "yellow": int(st_.get("yellowCards") or 0),
                         "red": int(st_.get("redCards") or 0), "saves": int(st_.get("saves") or 0)})
        df = pd.DataFrame(rows)
        if len(df):
            df["badges"] = [badges(r) for r in df.itertuples()]
        out[side.get("homeAway")] = df.assign(formation=side.get("formation"))
    return out


def badges(r) -> str:
    """Icons for one player: a ball per goal, a boot per assist, cards, and the minute he went off."""
    icons = "⚽" * r.goals + "🔴" * r.own_goals + "👟" * r.assists + "🟨" * min(r.yellow, 1) + "🟥" * r.red
    if r.starter and r.subbed_out and r.sub_minute:
        icons += f" ▼{r.sub_minute}"
    if not r.starter and r.subbed_in and r.sub_minute:
        icons += f" ▲{r.sub_minute}"
    return icons


def key_events(s: dict) -> pd.DataFrame:
    rows = []
    for k in s.get("keyEvents", []):
        kind = k.get("type", {}).get("text", "")
        if kind not in EVENT_ICONS:
            continue
        who = [p.get("athlete", {}).get("displayName", "") for p in k.get("participants", [])]
        rows.append({"minute": k.get("clock", {}).get("displayValue", ""), "type": kind, "icon": EVENT_ICONS[kind],
                     "team": k.get("team", {}).get("displayName", ""), "who": who, "text": k.get("text", "")})
    return pd.DataFrame(rows)


def team_stats(s: dict) -> pd.DataFrame:
    rows = {}
    for t in s.get("boxscore", {}).get("teams", []):
        vals = {x["name"]: x.get("displayValue") for x in t.get("statistics", [])}
        rows[t.get("homeAway") or t["team"]["displayName"]] = vals
    if {"home", "away"} - set(rows):
        return pd.DataFrame()
    out = []
    for key, label in STAT_ROWS:
        h, a = rows["home"].get(key), rows["away"].get(key)
        try:
            h, a = float(h), float(a)
        except (TypeError, ValueError):
            continue
        if key == "passPct":
            h, a = h * 100 if h <= 1 else h, a * 100 if a <= 1 else a
        out.append({"stat": label, "home": h, "away": a})
    return pd.DataFrame(out)


def understat_match(event_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Our processed team-match rows (xG, attacking index) and the shots for this ESPN event, if it is a league
    match we have collected."""
    tm = pd.read_parquet(data.HIST / "team_match.parquet",
                         columns=["event_id", "game_id", "team", "is_home", "xg", "goals", "attacking_index"])
    tm = tm[tm.event_id.astype("Int64").astype(str) == str(event_id)]
    if tm.empty:
        return tm, pd.DataFrame()
    shots = pd.read_parquet(data.HIST / "shots.parquet", filters=[("game_id", "==", int(tm.game_id.iloc[0]))])
    return tm, shots


def youtube_key() -> str | None:
    try:
        key = st.secrets.get("YOUTUBE_API_KEY")
    except Exception:  # no secrets file
        key = None
    return key or os.environ.get("YOUTUBE_API_KEY")


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def highlights(home: str, away: str, kickoff: str) -> dict | None:
    """Best embeddable YouTube highlights video published after kick-off whose title names both clubs."""
    key = youtube_key()
    if not key:
        return None
    try:
        resp = requests.get("https://www.googleapis.com/youtube/v3/search", timeout=15, params={
            "key": key, "part": "snippet", "type": "video", "videoEmbeddable": "true", "maxResults": 10,
            "q": f"{home} vs {away} highlights", "publishedAfter": kickoff, "order": "relevance"})
        resp.raise_for_status()
    except requests.RequestException:
        return None
    for item in resp.json().get("items", []):
        title = fold(item["snippet"]["title"])
        if names_in(home, title) and names_in(away, title) and "highlight" in title:
            return {"id": item["id"]["videoId"], "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"]}
    return None


ALIASES = {"Manchester United": ["man utd", "man united"], "Manchester City": ["man city"],
           "Paris Saint-Germain": ["psg"], "Bayern Munich": ["bayern"], "Tottenham": ["spurs"],
           "Wolves": ["wolverhampton"], "Inter": ["internazionale"], "Atlético Madrid": ["atleti"],
           "Athletic Club": ["athletic bilbao"], "Newcastle United": ["newcastle"], "Nottingham Forest": ["forest"]}
GENERIC = {"fc", "cf", "club", "real", "city", "united", "de", "the", "sporting", "athletic", "ac", "as", "sc"}


def fold(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def names_in(team: str, title: str) -> bool:
    """Whether a video title mentions the club: full name, a known alias, or a distinctive word of its name."""
    words = [w for w in fold(team).replace("-", " ").split() if w not in GENERIC and len(w) > 2]
    options = [fold(team), *ALIASES.get(team, []), *words]
    return any(o in title for o in options)


def youtube_search_url(home: str, away: str, date: pd.Timestamp) -> str:
    from urllib.parse import quote_plus
    return "https://www.youtube.com/results?search_query=" + quote_plus(f"{home} vs {away} highlights {date:%d %B %Y}")


def espn_videos(s: dict) -> list[dict]:
    return [{"headline": v.get("headline", ""), "url": v.get("links", {}).get("web", {}).get("href")}
            for v in s.get("videos", []) if v.get("links", {}).get("web", {}).get("href")]


def form_chips(team: str, before: datetime, n: int = 5) -> list[tuple[str, str]]:
    """Last n league results before a date: (result, 'H 2-1 Opponent')."""
    tm = data.history_matches(team)
    tm = tm[pd.to_datetime(tm.date) < pd.Timestamp(before).tz_localize(None)].sort_values("date").tail(n)
    return [(r.result, f"{'H' if r.is_home else 'A'} {int(r.goals)}-{int(r.goals_against)} {r.opponent}")
            for r in tm.itertuples()]


def now() -> datetime:
    return datetime.now(timezone.utc)
