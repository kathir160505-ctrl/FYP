"""Cached data access for the dashboard. Everything is precomputed by the src/ pipeline."""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.process.features import CLUSTER_FEATURES  # noqa: E402

PROC, REF, MODELS = ROOT / "data" / "processed", ROOT / "data" / "reference", ROOT / "models"
FEATURES = list(CLUSTER_FEATURES)

LEAGUES = {"ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga", "ITA-Serie A": "Serie A"}
LEAGUE_FLAGS = {"Premier League": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "La Liga": "🇪🇸", "Serie A": "🇮🇹"}
LEAGUE_SYMBOLS = {"Premier League": "circle", "La Liga": "diamond", "Serie A": "square"}

CLUSTER_ORDER = ["Dominant Possession", "Controlled Build-up", "Direct & Cross-Oriented", "Long-Ball Low Block"]
CLUSTER_COLORS = {
    "Dominant Possession": "#1D4ED8",
    "Controlled Build-up": "#7C3AED",
    "Direct & Cross-Oriented": "#EA580C",
    "Long-Ball Low Block": "#0F766E",
}

SHORT_LABELS = {
    "possession": "Possession",
    "pass_accuracy": "Ball control",
    "passes_completed": "Passes",
    "deep_completions": "Deep completions",
    "long_ball_share": "Directness",
    "crosses": "Crosses",
    "shots": "Shots",
    "sot_pct": "On target %",
    "xg": "xG",
    "goals": "Goals",
    "goals_per_shot": "Finishing",
    "fast_attack_shots": "Counter-attacks",
    "box_shot_share": "Box presence",
}
UNITS = {
    "possession": "%", "pass_accuracy": "%", "long_ball_share": "%", "sot_pct": "%", "box_shot_share": "%",
}


def fmt(feature: str, value: float) -> str:
    if feature in UNITS:
        return f"{value:.1f}%"
    if feature == "goals_per_shot":
        return f"{value:.3f}"
    if feature == "passes_completed":
        return f"{value:.0f}"
    return f"{value:.2f}"


def readable(color: str) -> str:
    """Club colours too pale for the white theme (white, yellow, sky blue) are darkened."""
    c = str(color).lstrip("#")
    if len(c) != 6:
        return "#374151"
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum <= 170:
        return f"#{c}"
    mix = lambda v: int(v * 0.45)  # noqa: E731
    return f"#{mix(r):02x}{mix(g):02x}{mix(b):02x}"


@st.cache_data
def clubs() -> pd.DataFrame:
    """One row per club: features, context stats, cluster, PCs, record, percentiles, colours."""
    season = pd.read_csv(PROC / "team_season.csv")
    clusters = pd.read_csv(PROC / "clusters.csv")
    meta = pd.read_csv(REF / "team_meta.csv")
    tm = pd.read_csv(PROC / "team_match.csv")
    record = tm.assign(W=tm.points == 3, D=tm.points == 1, L=tm.points == 0).groupby("team").agg(
        W=("W", "sum"), D=("D", "sum"), L=("L", "sum"), GF=("goals", "sum"), GA=("goals_against", "sum"),
        Pts=("points", "sum"), xG_total=("xg", "sum"), xGA_total=("xg_against", "sum"))
    df = (season.merge(clusters.drop(columns="league"), on="team")
          .merge(meta.drop(columns="league"), on="team").merge(record.reset_index(), on="team"))
    df["league_name"] = df["league"].map(LEAGUES)
    df["position"] = df.groupby("league")["Pts"].rank(ascending=False, method="first").astype(int)
    df["color"] = df["color"].map(readable)
    for f in FEATURES:
        df[f"{f}_pct"] = df[f].rank(pct=True) * 100
        df[f"{f}_lrank"] = df.groupby("league")[f].rank(ascending=False, method="min").astype(int)
    return df.sort_values(["league", "position"]).reset_index(drop=True)


@st.cache_data
def team_matches() -> pd.DataFrame:
    tm = pd.read_csv(PROC / "team_match.csv", parse_dates=["date"])
    ai = pd.read_csv(PROC / "attacking_index.csv")[["game_id", "team", "attacking_index", "index_conceded"]]
    tm = tm.merge(ai, on=["game_id", "team"])
    tm["result"] = tm["points"].map({3: "W", 1: "D", 0: "L"})
    return tm


@st.cache_data
def shots() -> pd.DataFrame:
    return pd.read_csv(PROC / "shots.csv", parse_dates=["date"])


@st.cache_data
def breakdowns() -> pd.DataFrame:
    return pd.read_csv(PROC / "team_breakdowns.csv")


@st.cache_data
def halves() -> pd.DataFrame:
    return pd.read_csv(PROC / "team_half.csv")


@st.cache_data
def similar() -> pd.DataFrame:
    return pd.read_csv(PROC / "similar_clubs.csv")


@st.cache_data
def profiles() -> pd.DataFrame:
    return pd.read_csv(PROC / "cluster_profiles.csv")


@st.cache_data
def model_selection() -> pd.DataFrame:
    return pd.read_csv(PROC / "model_selection.csv")


def _show_extensions() -> bool:
    """Matchday, Players, match centre, line-ups, 2026/27 and honours are shown by default. Setting
    SHOW_EXTENSIONS = false in .streamlit/secrets.toml (or the environment) hides them, leaving only the five
    pages the FYP1 proposal describes."""
    import os
    try:
        value = st.secrets.get("SHOW_EXTENSIONS", None)
    except Exception:  # no secrets file
        value = None
    value = os.environ.get("SHOW_EXTENSIONS", value)
    return value is None or str(value).strip().lower() not in ("0", "false", "no", "off")


EXTENSIONS = _show_extensions()

HIST = PROC / "history"
THESIS_SEASON = 2526


def season_label(season: int) -> str:
    s = f"{int(season):04d}"
    return f"20{s[:2]}/{s[2:]}"


@st.cache_data
def history() -> pd.DataFrame:
    """One row per club-season (2025/26 → current), styles projected with the 2025/26 model."""
    h = pd.read_csv(HIST / "team_season.csv")
    h["league_name"] = h["league"].map(LEAGUES)
    # Thesis clubs first; promoted clubs' crests and colours come from the live ESPN metadata.
    live_meta = ROOT / "data" / "live" / "team_meta.csv"
    meta = pd.concat([pd.read_csv(REF / "team_meta.csv"), *([pd.read_csv(live_meta)] if live_meta.exists() else [])])
    meta = meta.drop_duplicates("team")[["team", "logo", "color", "abbr"]]
    h = h.merge(meta, on="team", how="left")
    h["color"] = h["color"].fillna("#6B7280").map(readable)
    h["abbr"] = h["abbr"].fillna(h["team"].str[:3].str.upper())
    return h.sort_values(["season", "league", "position"]).reset_index(drop=True)


@st.cache_data
def season_clubs(season: int) -> pd.DataFrame:
    """The clubs of one season only, with percentiles and z-scores among that season's clubs (no mixing)."""
    df = history()[lambda h: h["season"] == season].copy()
    for f in FEATURES:
        df[f"{f}_pct"] = df[f].rank(pct=True) * 100
        df[f"{f}_z"] = (df[f] - df[f].mean()) / df[f].std()
    return df.reset_index(drop=True)


# Plain-English phrases for a feature well above / below the season average, and how to show its value.
STYLE_PHRASES = {
    "possession": ("keeping the ball", "giving the ball up", "{:.1f}% possession"),
    "pass_accuracy": ("accurate passing", "less accurate passing", "{:.1f}% pass accuracy"),
    "passes_completed": ("a high passing volume", "a low passing volume", "{:.0f} completed passes per match"),
    "deep_completions": ("reaching the final third often", "rarely reaching the final third",
                         "{:.1f} deep completions per match"),
    "long_ball_share": ("going long often", "rarely going long", "{:.1f}% long balls"),
    "crosses": ("crossing a lot", "crossing little", "{:.1f} crosses per match"),
    "shots": ("a high shot volume", "a low shot volume", "{:.1f} shots per match"),
    "sot_pct": ("accurate shooting", "inaccurate shooting", "{:.1f}% on target"),
    "xg": ("creating good chances", "creating few good chances", "{:.2f} xG per match"),
    "goals": ("scoring often", "scoring rarely", "{:.2f} goals per match"),
    "goals_per_shot": ("clinical finishing", "wasteful finishing", "{:.2f} goals per shot"),
    "fast_attack_shots": ("counter-attacking often", "rarely counter-attacking", "{:.2f} fast-attack shots per match"),
    "box_shot_share": ("shooting from inside the box", "shooting from distance", "{:.0f}% of shots in the box"),
}


def style_summary(row) -> str:
    """Two sentences describing a club's attacking style in one season, built from its cluster and z-scores.

    Regenerated from the data on every refresh, so the wording follows the club's current numbers."""
    matches = int(row["matches"])
    based = f"all {matches} league matches" if matches >= 38 else f"{matches} league matches so far"
    first = f"{row['team']}'s attacking style in {season_label(row['season'])} is {row['cluster']}, based on {based}"
    if row["style_confidence"] < 0.15:
        first += ", although it sits close to another style"
    z = pd.Series({f: row[f"{f}_z"] for f in FEATURES}).sort_values()
    picks = [(f, 0) for f in z.index[::-1] if z[f] >= 0.5][:2] + [(f, 1) for f in z.index if z[f] <= -0.5][:1]
    if not picks:
        return first + ". The club's attacking numbers are close to the average on every measure."
    parts = [f"{STYLE_PHRASES[f][side]} ({STYLE_PHRASES[f][2].format(row[f])})" for f, side in picks]
    listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"{first}. Compared with the other clubs that season, the club stands out for {listed}."


def comparison_summary(ra, rb, pred: dict, venue: str) -> str:
    """A few sentences on which of two clubs is more likely to show the more attacking style, and why.

    ra, rb: the two clubs' rows from season_clubs(); pred: predict_more_attacking() output; venue: "A", "B" or "N".
    Positive theme contributions favour club A."""
    a, b, p = ra["team"], rb["team"], pred["prob"]
    fav, other, fav_p, sign = (a, b, p, 1) if p >= 0.5 else (b, a, 1 - p, -1)
    shown = ">99%" if fav_p >= 0.995 else f"{fav_p:.0%}"
    if fav_p < 0.58:
        first = (f"The two sides are closely matched: {fav} is only slightly more likely than {other} to show the "
                 f"more attacking style ({shown})")
    else:
        strength = "clearly" if fav_p >= 0.70 else "moderately"
        first = f"{fav} is {strength} more likely than {other} to show the more attacking style ({shown})"
    if venue != "N":
        first += f", with {a if venue == 'A' else b} at home"
    phrases = {"Chance creation": "chance creation", "Ball dominance": "ball dominance",
               "Opposition faced": "the opposition each side has faced", "Venue": "home advantage"}
    drivers = [t for t, v in sorted(pred["themes"].items(), key=lambda kv: -kv[1] * sign) if v * sign > 0.05][:2]
    second = ""
    if drivers:
        second = (f" The main factors in {fav}'s favour are " if len(drivers) > 1 else
                  f" The main factor in {fav}'s favour is ") + " and ".join(phrases[t] for t in drivers)
        second += ", judged on season-to-date and last-five-match form." if drivers != ["Venue"] else "."
    third = (f" In {season_label(ra['season'])} league matches, {a} average {ra['xg']:.2f} xG, {ra['shots']:.1f} shots "
             f"and {ra['possession']:.0f}% possession per match, against {rb['xg']:.2f}, {rb['shots']:.1f} and "
             f"{rb['possession']:.0f}% for {b}.")
    return first + "." + second + third


@st.cache_data
def history_matches(team: str) -> pd.DataFrame:
    tm = pd.read_parquet(HIST / "team_match.parquet", filters=[("team", "==", team)])
    tm["date"] = pd.to_datetime(tm["date"])
    tm["result"] = tm["points"].map({3: "W", 1: "D", 0: "L"})
    return tm


@st.cache_data
def history_league_season(league: str, season: int) -> pd.DataFrame:
    tm = pd.read_parquet(HIST / "team_match.parquet", columns=["league", "season", "team", "matchweek", "points"],
                         filters=[("league", "==", league), ("season", "==", season)])
    return tm


PLAYERS = PROC / "players"
POSITION_GROUPS = ["Forward", "Midfielder", "Defender", "Goalkeeper"]
# Radar metrics per position group: (column, label). Percentiles are within the group and season.
PLAYER_RADAR = {
    "outfield": [("np_xg_p90", "Non-penalty xG"), ("shots_p90", "Shots"), ("goals_p90", "Goals"),
                 ("xa_p90", "Expected assists"), ("key_passes_p90", "Key passes"), ("xg_chain_p90", "xG chain"),
                 ("xg_buildup_p90", "xG build-up"), ("crosses_p90", "Crosses"), ("tackles_won_p90", "Tackles won"),
                 ("interceptions_p90", "Interceptions")],
    "Goalkeeper": [("saves_p90", "Saves"), ("save_pct", "Save %"), ("xg_buildup_p90", "xG build-up"),
                   ("interceptions_p90", "Interceptions")],
}


def players_ready() -> bool:
    """Player data is built by src.process.build_players; the pages degrade gracefully until it exists."""
    return all((PLAYERS / f).exists() for f in ("players.csv", "lineups.parquet", "probable_xi.csv"))


@st.cache_data
def players() -> pd.DataFrame:
    p = pd.read_csv(PLAYERS / "players.csv", dtype={"athlete_id": str, "jersey": str})
    p["league_name"] = p["league"].map(LEAGUES)
    return p


@st.cache_data
def lineups(team: str) -> pd.DataFrame:
    return pd.read_parquet(PLAYERS / "lineups.parquet", filters=[("team", "==", team)])


@st.cache_data
def player_matches(athlete_id: str) -> pd.DataFrame:
    return pd.read_parquet(PLAYERS / "lineups.parquet", filters=[("athlete_id", "==", athlete_id)])


@st.cache_data
def probable_candidates() -> pd.DataFrame:
    """Probable XI with ranked replacements per slot (rank 1 = first choice), from src.process.build_players."""
    df = pd.read_csv(PLAYERS / "probable_xi.csv", dtype={"athlete_id": str}, parse_dates=["last_match"])
    return df if "rank" in df else df.assign(rank=1)


def probable_xi() -> pd.DataFrame:
    df = probable_candidates()
    return df[df["rank"] == 1]


def probable_lineup(team: str, unavailable: dict[str, str] | None = None) -> pd.DataFrame:
    """The club's probable XI without unavailable players (athlete_id -> reason): each slot takes its best available
    candidate. Rows that changed carry a note naming the player they replace."""
    c = probable_candidates()
    c = c[c.team == team].sort_values(["formation_place", "rank"])
    unavailable = unavailable or {}
    taken, rows = set(), []
    for place, g in c.groupby("formation_place", sort=True):
        first = g.iloc[0]
        pick = next((r for r in g.itertuples() if r.athlete_id not in unavailable and r.athlete_id not in taken), None)
        if pick is None:  # nobody available for this slot: keep the first choice, flagged
            pick = first
        taken.add(pick.athlete_id)
        row = pick._asdict() if hasattr(pick, "_asdict") else pick.to_dict()
        row.pop("Index", None)
        if row["athlete_id"] != first.athlete_id:
            row["note"] = f"in for {first.player} ({unavailable.get(first.athlete_id, 'unavailable')})"
        elif first.athlete_id in unavailable:
            row["note"] = f"{unavailable[first.athlete_id]}, no recent replacement"
        else:
            row["note"] = f"started {row['recent_starts']} of the last {row['of_matches']} league matches"
        rows.append(row)
    return pd.DataFrame(rows)


@st.cache_data
def player_links() -> dict:
    """ESPN athlete id -> Players page URL for that player's latest season and club."""
    from urllib.parse import urlencode
    if not players_ready():
        return {}
    p = players().dropna(subset=["athlete_id"]).sort_values(["season", "minutes"])
    p = p.drop_duplicates("athlete_id", keep="last")
    return {a: "players?" + urlencode({"season": int(s), "club": t, "player": n})
            for a, s, t, n in zip(p.athlete_id, p.season, p.team, p["name"])}


def initials(name: str) -> str:
    parts = [p for p in str(name).split() if p[:1].isalpha()]
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def avatar(name: str, color: str = "#6B7280") -> str:
    """An initials badge as an SVG data URI, for players without a free photo."""
    from urllib.parse import quote
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><circle cx="32" cy="32" r="32" '
           f'fill="{color}"/><text x="32" y="41" font-family="Arial" font-size="24" font-weight="700" '
           f'fill="#fff" text-anchor="middle">{initials(name)}</text></svg>')
    return "data:image/svg+xml;utf8," + quote(svg)


def photos(df: pd.DataFrame, color: str | None = None) -> pd.Series:
    """Photo URL per player row, falling back to an initials avatar in the club (or given) colour."""
    colors = history().drop_duplicates("team").set_index("team").color
    return pd.Series([ph if isinstance(ph, str) and ph else avatar(n, color or colors.get(t, "#6B7280"))
                      for ph, n, t in zip(df.photo, df["name"], df.team)], index=df.index)


LEGACY = PROC / "legacy"
# Trophy categories shown in the app, in display order (super cups are excluded: Wikidata lists too few).
TROPHY_COLORS = {"League title": "#B45309", "Domestic cup": "#1D4ED8", "League Cup": "#0F766E",
                 "European Cup": "#D50000", "UEFA Cup": "#EA580C", "Cup Winners' Cup": "#7C3AED",
                 "Conference League": "#16A34A", "UEFA Super Cup": "#6B7280", "World club title": "#0B0D10",
                 "Second-tier title": "#9CA3AF"}
TROPHY_LABELS = {"League title": "League titles", "Domestic cup": "Domestic cups", "League Cup": "League Cups",
                 "European Cup": "European Cups", "UEFA Cup": "UEFA Cup / Europa League",
                 "Cup Winners' Cup": "Cup Winners' Cups", "Conference League": "Conference League",
                 "UEFA Super Cup": "UEFA Super Cups", "World club title": "World club titles",
                 "Second-tier title": "Second-tier titles"}


@st.cache_data
def honours() -> pd.DataFrame:
    return pd.read_csv(LEGACY / "honours.csv")


@st.cache_data
def managers() -> pd.DataFrame:
    return pd.read_csv(LEGACY / "managers.csv", parse_dates=["start", "end", "born"])


@st.cache_data
def manager_records() -> pd.DataFrame:
    return pd.read_csv(LEGACY / "manager_records.csv", parse_dates=["first_match", "last_match"])


@st.cache_data
def club_info() -> pd.DataFrame:
    return pd.read_csv(LEGACY / "club_info.csv")


def legacy_retrieved() -> str:
    return pd.Timestamp((LEGACY / "retrieved.txt").read_text(encoding="utf-8").strip()).strftime("%d %b %Y")


def seasons() -> list[int]:
    return sorted(history()["season"].unique().tolist(), reverse=True)


@st.cache_resource
def cluster_model() -> dict:
    return joblib.load(MODELS / "cluster_model.joblib")


@st.cache_resource
def predict_model() -> dict:
    return joblib.load(MODELS / "predict_model.joblib")


@st.cache_data
def team_form() -> pd.DataFrame:
    return pd.read_csv(PROC / "team_form.csv").set_index("team")


PREDICTION_THEMES = {
    "Ball dominance": ["possessionPct", "pass_accuracy", "long_ball_share"],
    "Chance creation": ["attacking_index", "xg", "shots", "deep_completions", "box_shots", "totalCrosses"],
    "Opposition faced": ["index_conceded", "xg_against"],
}


def predict_more_attacking(team_a: str, team_b: str, venue: str, form: pd.DataFrame | None = None) -> dict:
    """P(team A shows the more attacking style), with contributions grouped by theme.

    venue: "A" (A at home), "B" (B at home) or "N" (neutral, average of both).
    form: club inputs indexed by team; defaults to end-of-2025/26 form, the Matchday page passes 2026/27 form.
    """
    pm = predict_model()
    form = team_form() if form is None else form
    model, feats, stats = pm["model"], pm["features"], pm["history_stats"]
    base = {}
    for s in stats:
        for kind in ("season", "form"):
            base[f"{s}_{kind}_diff"] = form.loc[team_a, f"{s}_{kind}"] - form.loc[team_b, f"{s}_{kind}"]
    homes = {"A": [1], "B": [0], "N": [1, 0]}[venue]
    rows = pd.DataFrame([{**base, "is_home": h} for h in homes])[feats]
    prob = float(model.predict_proba(rows)[:, 1].mean())

    scaler, lr = model.named_steps["standardscaler"], model.named_steps["logisticregression"]
    z = (rows.mean().to_numpy() - scaler.mean_) / scaler.scale_
    contrib = pd.Series(z * lr.coef_[0], index=feats)
    themes = {name: sum(contrib[f"{s}_{k}_diff"] for s in members for k in ("season", "form"))
              for name, members in PREDICTION_THEMES.items()}
    themes["Venue"] = contrib["is_home"]
    return {"prob": prob, "themes": themes}


def league_of(df: pd.DataFrame, team: str) -> str:
    return df.loc[df.team == team, "league_name"].iloc[0]


def percent_rank(series: pd.Series, value: float) -> float:
    return float((series < value).mean() * 100 + (series == value).mean() * 50)


def club_options(df: pd.DataFrame) -> list[str]:
    return df.sort_values("team")["team"].tolist()


def nan_to_none(x):
    return None if (isinstance(x, float) and np.isnan(x)) else x
