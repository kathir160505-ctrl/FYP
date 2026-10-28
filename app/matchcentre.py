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
# ESPN key-event type -> our event kind (icons in icons.py). Goal variants: header, volley, free-kick.
EVENT_KINDS = {"Goal": "goal", "Goal - Header": "goal", "Goal - Volley": "goal", "Goal - Free-kick": "goal",
               "Penalty - Scored": "goal", "Own Goal": "own_goal", "Yellow Card": "yellow", "Red Card": "red",
               "Substitution": "sub", "Penalty - Missed": "penalty_miss", "Penalty - Saved": "penalty_miss",
               "Penalty - Hit Woodwork": "penalty_miss", "Halftime": "ht", "End Regular Time": "ft"}
# Broadcasters and league channels preferred for highlights over re-uploads.
OFFICIAL_CHANNELS = ("bein sports", "tnt sports", "cbs sports", "sky sports", "dazn", "espn", "nbc sports",
                     "premier league", "laliga", "serie a", "uefa", "stadium astro", "optus sport", "movistar",
                     "sportmediaset", "amazon prime video sport", "canal+", "viaplay", "fox sports", "paramount+")


@st.cache_data(ttl=30, show_spinner=False)  # short: live matches change every minute
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
        out[side.get("homeAway")] = pd.DataFrame(rows).assign(formation=side.get("formation"))
    return out


def key_events(s: dict, home_espn: str) -> pd.DataFrame:
    """Goals (with assister and running score), cards, substitutions, penalties and the half/full-time markers."""
    rows, score = [], [0, 0]
    yellows: dict[str, int] = {}
    for k in s.get("keyEvents", []):
        kind = EVENT_KINDS.get(k.get("type", {}).get("text", ""))
        if not kind:
            continue
        who = [p.get("athlete", {}).get("displayName", "") for p in k.get("participants", [])]
        team = k.get("team", {}).get("displayName", "")
        side = "home" if team == home_espn else ("away" if team else "")
        row = {"minute": k.get("clock", {}).get("displayValue", ""), "kind": kind, "side": side,
               "player": who[0] if who else "", "other": who[1] if len(who) > 1 else "",
               "text": k.get("text", ""), "score": "", "injury": False}
        if kind in ("goal", "own_goal"):
            # ESPN files an own goal under the team that benefited
            score[0 if side == "home" else 1] += 1
            row["score"] = f"{score[0]}–{score[1]}"
            if kind == "own_goal":
                row["other"] = ""
        elif kind == "yellow" and row["player"]:
            yellows[row["player"]] = yellows.get(row["player"], 0) + 1
            if yellows[row["player"]] == 2:
                row["kind"] = "second_yellow"
        elif kind == "sub":  # ESPN lists the player coming on first
            row["injury"] = "injur" in row["text"].lower()
        rows.append(row)
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
    import html as _html
    hits = []
    for item in resp.json().get("items", []):
        raw = _html.unescape(item["snippet"]["title"])
        title, channel = fold(raw), item["snippet"]["channelTitle"]
        if names_in(home, title) and names_in(away, title) and "highlight" in title:
            official = any(c in fold(channel) for c in OFFICIAL_CHANNELS)
            hits.append((not official, len(hits), {"id": item["id"]["videoId"], "title": raw, "channel": channel,
                                                    "official": official}))
    return min(hits, key=lambda h: h[:2])[2] if hits else None


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


def form_chips(team: str, before, n: int = 5) -> list[tuple[str, str]]:
    """Last n competitive results before a date, oldest first: (result, 'Premier League · H 2-1 Opponent · 24 Oct').
    Live from ESPN in every competition; falls back to our league data if ESPN is unreachable."""
    r = live.recent_results(team, pd.Timestamp(before).isoformat(), n)
    if len(r):
        return [(x.result, f"{x.competition} · {'H' if x.home else 'A'} {x.goals}-{x.goals_against} {x.opponent} · "
                           f"{x.date:%d %b}") for x in r.iloc[::-1].itertuples()]
    tm = data.history_matches(team)
    tm = tm[pd.to_datetime(tm.date) < pd.Timestamp(before).tz_convert(None)].sort_values("date").tail(n)
    return [(x.result, f"{'H' if x.is_home else 'A'} {int(x.goals)}-{int(x.goals_against)} {x.opponent}")
            for x in tm.itertuples()]


def now() -> datetime:
    return datetime.now(timezone.utc)


def related_news(s: dict, home: str, away: str, limit: int = 6) -> list[dict]:
    """The match report plus ESPN articles that mention either club (the summary feed is only loosely related)."""
    out, seen = [], set()
    rep = s.get("article") or {}
    if rep.get("headline") and rep.get("links", {}).get("web", {}).get("href"):
        out.append({"headline": rep["headline"], "link": rep["links"]["web"]["href"], "report": True,
                    "image": next((i.get("url") for i in rep.get("images", []) if i.get("url")), None),
                    "published": pd.to_datetime(rep.get("published"), utc=True, errors="coerce")})
        seen.add(rep["links"]["web"]["href"])
    keys = [w for t in (home, away) for w in [fold(t), *ALIASES.get(t, []),
            *[x for x in fold(t).split() if x not in GENERIC and len(x) > 3]]]
    for a in s.get("news", {}).get("articles", []):
        link = a.get("links", {}).get("web", {}).get("href")
        text = fold(f"{a.get('headline', '')} {a.get('description', '')}")
        if not link or link in seen or not any(k in text for k in keys):
            continue
        seen.add(link)
        out.append({"headline": a.get("headline", ""), "link": link, "report": False,
                    "image": next((i.get("url") for i in a.get("images", []) if i.get("url")), None),
                    "published": pd.to_datetime(a.get("published"), utc=True, errors="coerce")})
    return out[:limit]


def squad_absentees(team: str, on_sheet: set, min_apps: int = 3) -> list[str]:
    """Players who have played for the club this season (at least min_apps league matches) but are not on the
    match sheet. The source does not say why: injury, suspension, illness or selection."""
    if not data.players_ready():
        return []
    p = data.players()
    p = p[(p.team == team) & (p.season == p.season.max()) & (p.matches >= min_apps)].dropna(subset=["athlete_id"])
    return p[~p.athlete_id.isin(on_sheet)].sort_values("minutes", ascending=False)["name"].tolist()


@st.cache_data(ttl=1800, show_spinner=False)
def previous_match_news(team: str, before: str) -> dict:
    """From the club's last recorded match before `before`: who went off injured and who was sent off."""
    if not data.players_ready():
        return {}
    lu = data.lineups(team)
    lu = lu[lu.date < pd.Timestamp(before).tz_convert(None)]
    if lu.empty:
        return {}
    last = lu.sort_values("date").iloc[-1]
    code = {"Premier League": "eng.1", "La Liga": "esp.1", "Serie A": "ita.1",
            "Champions League": "uefa.champions"}.get(last.competition_name, "eng.1")
    s = summary(code, str(last.event_id))
    side = last.home_away
    home_espn = next((r["team"]["displayName"] for r in s.get("rosters", []) if r.get("homeAway") == "home"), "")
    ev = key_events(s, home_espn) if s else pd.DataFrame()
    injured, sent_off = [], []
    if len(ev):
        mine = ev[ev.side == side]
        injured = mine[(mine.kind == "sub") & mine.injury].other.tolist()
        sent_off = mine[mine.kind.isin(["red", "second_yellow"])].player.tolist()
    return {"opponent": last.opponent, "date": last.date, "competition": last.competition_name,
            "injured": injured, "sent_off": sent_off}
