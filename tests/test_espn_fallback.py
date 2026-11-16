"""ESPN fallback: shots parsed from ESPN play-by-play in Understat's format."""
from src.model.espn_fallback import geometry, parse_shots


def _play(text, x, y, team="Leeds United", kind="shot-on-target"):
    return {"text": text, "time": {"displayValue": "23'"},
            "play": {"type": {"type": kind}, "fieldPositionX": x, "fieldPositionY": y,
                     "team": {"displayName": team}}}


def test_parse_shots_reads_outcome_location_and_features():
    summary = {"commentary": [
        _play("Goal! Leeds United 1, Sunderland 0. Ao Tanaka (Leeds United) header from the centre of the box to the "
              "top left corner. Assisted by Jayden Bogle with a cross.", 94.0, 57.0),
        _play("Attempt saved. Brian Brobbey (Sunderland) right footed shot from outside the box is saved.", 77.5, 63.2,
              team="Sunderland"),
        _play("Attempt blocked. Chris Rigg (Sunderland) left footed shot from the right side of the box is blocked.",
              85.8, 30.7, team="Sunderland", kind="shot-blocked"),
        {"text": "Own Goal by Somebody (Sunderland), Leeds United 2, Sunderland 0."},
        {"text": "Corner, Sunderland. Conceded by Ethan Ampadu."},
    ]}
    s = parse_shots(summary)
    assert list(s.result) == ["Goal", "Saved Shot", "Blocked Shot"]
    assert list(s.team) == ["Leeds United", "Sunderland", "Sunderland"]
    goal = s.iloc[0]
    assert goal.player == "Ao Tanaka" and goal.body == "head" and goal.assist == "cross" and goal.minute == 23
    # ESPN's 0-100 position becomes Understat's 0-1 pitch, attacking towards x = 1, same y orientation.
    assert abs(goal.location_x - 0.94) < 1e-9 and abs(goal.location_y - 0.57) < 1e-9
    g = geometry(s)
    assert g.distance.iloc[0] < g.distance.iloc[1]  # the header was closer than the shot from outside the box
