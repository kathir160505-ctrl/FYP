import numpy as np
import pandas as pd
import pytest

from src.process.features import aggregate, in_box, safe_ratio, shot_summary, understat_long


def test_in_box_edges():
    x = pd.Series([0.90, 0.80, 0.90, 0.90, 0.842])  # box edge is at 1 - 16.5/105 = 0.8429
    y = pd.Series([0.50, 0.50, 0.10, 0.85, 0.50])
    assert in_box(x, y).tolist() == [True, False, False, False, False]


def test_safe_ratio_zero_denominator_is_nan():
    out = safe_ratio([1, 2], [0, 4], 100)
    assert np.isnan(out[0]) and out[1] == 50


def test_shot_summary_counts_and_excludes_own_goals():
    shots = pd.DataFrame({
        "game_id": [1, 1, 1, 1], "team": ["A", "A", "A", "B"],
        "xg": [0.1, 0.3, 0.0, 0.2],
        "result": ["Goal", "Missed Shot", "Own Goal", "Saved Shot"],
        "location_x": [0.95, 0.70, 0.99, 0.90], "location_y": [0.5, 0.5, 0.5, 0.5],
    })
    s = shot_summary(shots).set_index("team")
    assert s.loc["A", "shots"] == 2
    assert s.loc["A", "shots_on_target"] == 1
    assert s.loc["A", "box_shots"] == 1
    assert s.loc["B", "shots_on_target"] == 1


def test_understat_long_mirrors_home_and_away():
    m = pd.DataFrame({
        "league": ["L"], "game_id": [7], "date": ["2025-08-15"], "home_team": ["H"], "away_team": ["A"],
        "home_goals": [2], "away_goals": [1], "home_xg": [1.5], "away_xg": [0.5],
        "home_np_xg": [1.5], "away_np_xg": [0.5], "home_deep_completions": [9], "away_deep_completions": [3],
        "home_ppda": [8.0], "away_ppda": [12.0], "home_points": [3], "away_points": [0],
    })
    long = understat_long(m).set_index("team")
    assert long.loc["H", "goals_against"] == 1 and long.loc["A", "goals_against"] == 2
    assert long.loc["A", "xg_against"] == 1.5
    assert bool(long.loc["H", "is_home"]) and not bool(long.loc["A", "is_home"])


def test_aggregate_uses_totals_for_ratios():
    tm = pd.DataFrame({
        "league": ["L", "L"], "team": ["T", "T"],
        "goals": [3, 0], "goals_against": [0, 1], "xg": [2.0, 0.5], "np_xg": [2.0, 0.5], "xg_against": [0.4, 1.0],
        "deep_completions": [10, 4], "points": [3, 0], "shots": [10, 2], "shots_on_target": [5, 0],
        "box_shots": [8, 1], "accuratePasses": [400, 100], "totalPasses": [500, 200],
        "totalCrosses": [20, 10], "totalLongBalls": [50, 50], "possessionPct": [60, 40], "ppda": [8, 12],
    })
    row = aggregate(tm, ["league", "team"]).iloc[0]
    assert row["matches"] == 2
    assert row["possession"] == 50
    assert row["pass_accuracy"] == pytest.approx(500 / 700 * 100)  # from totals, not the mean of 80% and 50%
    assert row["sot_pct"] == pytest.approx(5 / 12 * 100)
    assert row["goals_per_shot"] == pytest.approx(3 / 12)
    assert row["long_ball_share"] == pytest.approx(100 / 700 * 100)
