import pandas as pd

from src.process.build_ucl import team_rows, ucl_season

NAMES = {"Arsenal": "Arsenal", "Internazionale": "Inter"}


def match(event, stage, home, away, hs, as_, home_winner=None):
    base = {"event_id": event, "date": "2026-05-30T19:00Z", "stage": stage, "espn_home": home, "espn_away": away,
            "home_score": hs, "away_score": as_, "home_winner": home_winner if home_winner is not None else hs > as_,
            "away_winner": (not home_winner) if home_winner is not None else as_ > hs, "logo": None, "season": 2526,
            "possessionPct": 50.0, "accuratePasses": 400, "totalPasses": 500, "totalLongBalls": 50,
            "totalCrosses": 10, "totalShots": 12, "shotsOnTarget": 4}
    return [{**base, "espn_team": home, "home_away": "home"}, {**base, "espn_team": away, "home_away": "away"}]


def test_team_rows_maps_names_and_results():
    m = team_rows(pd.DataFrame(match(1, "league-phase", "Internazionale", "PSV", 2, 0)), NAMES)
    inter = m[m.team == "Inter"].iloc[0]
    assert inter.ours and inter.goals == 2 and inter.points == 3 and inter.opponent == "PSV"
    assert not m[m.team == "PSV"].iloc[0].ours


def test_drawn_final_goes_to_winner_flag():
    rows = match(1, "league-phase", "Arsenal", "PSV", 1, 0) + match(2, "final", "Arsenal", "Inter", 1, 1, home_winner=False)
    s = ucl_season(team_rows(pd.DataFrame(rows), NAMES)).set_index("team")
    assert s.loc["Inter", "stage_reached"] == "winner"  # won on penalties
    assert s.loc["Arsenal", "stage_reached"] == "final"
    assert s.loc["Arsenal", "league_phase_position"] == 1
