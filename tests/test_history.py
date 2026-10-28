import pandas as pd

from src.collect.history import current_season, season_range, start_year
from src.process.build_history import add_standings, match_names


def test_season_helpers():
    assert season_range("1415-1718") == ["1415", "1516", "1617", "1718"]
    assert season_range("9900-0102") == []  # ranges never wrap around the century
    assert start_year("2526") == 2025
    assert len(current_season()) == 4


def test_match_names_aligns_clubs_by_date_and_score():
    us = pd.DataFrame({
        "date": ["2025-08-16 15:00", "2025-08-23 15:00", "2025-08-23 17:30"],
        "home_team": ["Wolves", "Spurs", "Leeds"], "away_team": ["Spurs", "Wolves", "Fulham"],
        "home_goals": [1, 2, 1], "away_goals": [0, 2, 1]})
    espn = pd.DataFrame({
        "event_id": [1, 2, 3],
        "date": ["2025-08-16T14:00Z", "2025-08-23T14:00Z", "2025-08-23T16:30Z"],  # UTC, a different hour
        "espn_home": ["Wolverhampton Wanderers", "Tottenham Hotspur", "Leeds United"],
        "espn_away": ["Tottenham Hotspur", "Wolverhampton Wanderers", "Fulham"],
        "home_score": [1, 2, 1], "away_score": [0, 2, 1]})
    nm = match_names(us, espn).set_index("understat")
    assert nm.loc["Spurs", "espn"] == "Tottenham Hotspur"
    assert nm.loc["Wolves", "espn"] == "Wolverhampton Wanderers"
    assert (nm["share"] >= 1).all()


def test_add_standings_uses_points_then_goal_difference():
    tm = pd.DataFrame({
        "league": ["L"] * 4, "season": [2526] * 4, "game_id": [1, 1, 2, 2],
        "team": ["A", "B", "C", "D"], "points": [3, 0, 3, 0], "goals": [1, 0, 4, 0], "goals_against": [0, 1, 0, 4]})
    ts = pd.DataFrame({"league": ["L"] * 4, "season": [2526] * 4, "team": ["A", "B", "C", "D"]})
    out = add_standings(ts, tm).set_index("team")
    assert out.loc["C", "position"] == 1 and out.loc["A", "position"] == 2  # same points, better goal difference
    assert out.loc["C", "pts"] == 3 and out.loc["C", "gd"] == 4
