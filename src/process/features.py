"""Feature definitions shared by processing, modelling and the dashboard.

Every count is per match. A league match is ~90 minutes, so per-match equals per-90
for team-level data. Ratio features are computed from season totals, not by
averaging match ratios, so low-volume matches do not distort them.
"""
import numpy as np
import pandas as pd

# Penalty area on Understat's 0-1 pitch (length 105 m, width 68 m, attacking towards x=1).
BOX_X_MIN = 1 - 16.5 / 105
BOX_Y_MIN, BOX_Y_MAX = 0.5 - 20.16 / 68, 0.5 + 20.16 / 68
ON_TARGET_RESULTS = {"Goal", "Saved Shot"}

# Clustering features: proposal Table 3.1, mapped to available data (see reports/phase0_data_audit.md).
CLUSTER_FEATURES = {
    "possession": "Possession %",
    "pass_accuracy": "Ball control (pass accuracy %)",
    "passes_completed": "Completed passes per match",
    "deep_completions": "Deep completions per match (progressive-pass proxy)",
    "long_ball_share": "Long-ball share of passes % (directness)",
    "crosses": "Crosses per match",
    "shots": "Shots per match",
    "sot_pct": "Shots on target %",
    "xg": "Expected goals (xG) per match",
    "goals": "Goals per match",
    "goals_per_shot": "Goals per shot",
    "fast_attack_shots": "Fast-attack shots per match (counter-attack proxy)",
    "box_shot_share": "Share of shots inside the penalty area % (box-presence proxy)",
}


def in_box(x: pd.Series, y: pd.Series) -> pd.Series:
    """True where an Understat shot location lies inside the opponent's penalty area."""
    return (x >= BOX_X_MIN) & y.between(BOX_Y_MIN, BOX_Y_MAX)


def safe_ratio(num, den, scale: float = 1.0):
    """num/den * scale, NaN where the denominator is zero."""
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den * scale, np.nan)


def shot_summary(shots: pd.DataFrame) -> pd.DataFrame:
    """Per team per match shot counts from Understat shot events (own goals excluded)."""
    s = shots[shots["result"] != "Own Goal"].assign(
        on_target=lambda d: d["result"].isin(ON_TARGET_RESULTS),
        box=lambda d: in_box(d["location_x"], d["location_y"]),
    )
    return (
        s.groupby(["game_id", "team"])
        .agg(shots=("xg", "size"), shots_on_target=("on_target", "sum"), box_shots=("box", "sum"))
        .reset_index()
    )


def understat_long(matches: pd.DataFrame) -> pd.DataFrame:
    """Convert Understat's one-row-per-match table to one row per team per match."""
    sides = []
    for side, other in (("home", "away"), ("away", "home")):
        sides.append(pd.DataFrame({
            "league": matches["league"],
            "game_id": matches["game_id"],
            "date": pd.to_datetime(matches["date"]),
            "team": matches[f"{side}_team"],
            "opponent": matches[f"{other}_team"],
            "is_home": side == "home",
            "home_team": matches["home_team"],
            "away_team": matches["away_team"],
            "goals": matches[f"{side}_goals"],
            "goals_against": matches[f"{other}_goals"],
            "xg": matches[f"{side}_xg"],
            "np_xg": matches[f"{side}_np_xg"],
            "xg_against": matches[f"{other}_xg"],
            "deep_completions": matches[f"{side}_deep_completions"],
            "ppda": matches[f"{side}_ppda"],
            "points": matches[f"{side}_points"],
        }))
    return pd.concat(sides, ignore_index=True)


SUM_COLUMNS = [
    "goals", "goals_against", "xg", "np_xg", "xg_against", "deep_completions", "points",
    "shots", "shots_on_target", "box_shots", "accuratePasses", "totalPasses",
    "totalCrosses", "totalLongBalls", "possessionPct", "ppda",
]


def aggregate(team_match: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Aggregate team-match rows into per-match features for each group in `keys`."""
    g = team_match.groupby(keys)
    tot = g[SUM_COLUMNS].sum()
    n = g.size().rename("matches")
    out = pd.DataFrame(index=tot.index)
    out["matches"] = n
    out["possession"] = tot["possessionPct"] / n
    out["pass_accuracy"] = safe_ratio(tot["accuratePasses"], tot["totalPasses"], 100)
    out["passes_completed"] = tot["accuratePasses"] / n
    out["deep_completions"] = tot["deep_completions"] / n
    out["long_ball_share"] = safe_ratio(tot["totalLongBalls"], tot["totalPasses"], 100)
    out["crosses"] = tot["totalCrosses"] / n
    out["shots"] = tot["shots"] / n
    out["sot_pct"] = safe_ratio(tot["shots_on_target"], tot["shots"], 100)
    out["xg"] = tot["xg"] / n
    out["goals"] = tot["goals"] / n
    out["goals_per_shot"] = safe_ratio(tot["goals"], tot["shots"])
    out["box_shot_share"] = safe_ratio(tot["box_shots"], tot["shots"], 100)
    # Context (not clustering features): results and defensive numbers shown in the app.
    out["points_per_match"] = tot["points"] / n
    out["goals_against"] = tot["goals_against"] / n
    out["xg_against"] = tot["xg_against"] / n
    out["np_xg"] = tot["np_xg"] / n
    out["ppda"] = tot["ppda"] / n
    return out.reset_index()
