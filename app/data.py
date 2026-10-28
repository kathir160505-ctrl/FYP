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
    meta = meta.drop_duplicates("team")[["team", "logo", "color"]]
    h = h.merge(meta, on="team", how="left")
    h["color"] = h["color"].fillna("#6B7280").map(readable)
    return h.sort_values(["season", "league", "position"]).reset_index(drop=True)


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


UCL = PROC / "ucl"


@st.cache_data
def ucl_matches() -> pd.DataFrame:
    return pd.read_csv(UCL / "ucl_match.csv", parse_dates=["date"])


@st.cache_data
def ucl_seasons() -> pd.DataFrame:
    s = pd.read_csv(UCL / "ucl_season.csv")
    s["league_name"] = s["league"].map(LEAGUES)
    return s


@st.cache_data
def ucl_vs_league() -> pd.DataFrame:
    return pd.read_csv(UCL / "ucl_vs_league.csv")


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
def probable_xi() -> pd.DataFrame:
    return pd.read_csv(PLAYERS / "probable_xi.csv", dtype={"athlete_id": str}, parse_dates=["last_match"])


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
