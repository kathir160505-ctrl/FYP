import pandas as pd

from src.model.commentary_xg import parse_shot, side_of


def test_parse_goal_header_from_cross():
    p = parse_shot("Goal! Hull City 2, Manchester United 0. Nobel Mendy (Hull City) header from very close range to the "
                   "bottom right corner. Assisted by Regan Slater with a cross following a corner.")
    assert p["goal"] and p["body"] == "head" and p["zone"] == "very_close"
    assert p["assist"] == "cross" and p["situation"] == "corner" and p["team"] == "Hull City"


def test_parse_blocked_long_shot_and_non_shots():
    p = parse_shot("Attempt blocked. Youri Tielemans (Manchester United) right footed shot from outside the box is blocked.")
    assert not p["goal"] and p["zone"] == "outside" and p["assist"] == "none" and p["situation"] == "open_play"
    assert parse_shot("Corner,  Manchester United. Conceded by Ryan Giles.") is None
    assert parse_shot("Own Goal by Harry Maguire, Manchester United.  Hull City 1, Manchester United 0.") is None


def test_side_of_matches_commentary_names_to_espn():
    shots = pd.DataFrame({"team": ["Inter Milan", "Paris Saint Germain", "Inter Milan"]})
    side = side_of(shots, home="Internazionale", away="Paris Saint-Germain")
    assert side.tolist() == ["home", "away", "home"]
