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
    "Dominant Possession": "#38bdf8",
    "Controlled Build-up": "#a78bfa",
    "Direct & Cross-Oriented": "#f59e0b",
    "Long-Ball Low Block": "#f43f5e",
}
CLUSTER_ICONS = {
    "Dominant Possession": "🎯",
    "Controlled Build-up": "🧩",
    "Direct & Cross-Oriented": "⚡",
    "Long-Ball Low Block": "🧱",
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


def _readable(color: str) -> str:
    """Club colours that are too dark for the dark theme are lightened."""
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum >= 60:
        return f"#{c}"
    mix = lambda v: int(v + (255 - v) * 0.55)  # noqa: E731
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
    df["color"] = df["color"].map(_readable)
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


def predict_more_attacking(team_a: str, team_b: str, venue: str) -> dict:
    """P(team A shows the more attacking style), with contributions grouped by theme.

    venue: "A" (A at home), "B" (B at home) or "N" (neutral, average of both).
    """
    pm, form = predict_model(), team_form()
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
