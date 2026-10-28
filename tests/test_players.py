import pandas as pd

from src.process.build_players import match_within, norm, position_group, probable_xi, similarity


def test_norm_and_similarity():
    assert norm("Vinícius Júnior") == "vinicius junior"
    assert norm("Martin Ødegaard") == "martin odegaard"
    assert similarity("Vinicius Junior", "Vinícius José Paixão de Oliveira Júnior") >= 0.8
    assert similarity("Bruno Fernandes", "Bruno Guimarães") < 0.8


def test_match_within_prefers_exact_then_unique_fuzzy():
    left = pd.DataFrame({"team": ["A", "A", "A"], "name": ["Rodri", "Ødegaard Martin", "Ben White"]})
    right = pd.DataFrame({"team": ["A", "A", "A", "B"],
                          "player": ["Ben White", "Martin Odegaard", "Declan Rice", "Rodri"]})
    m = match_within(left, right, ["team"], "name", "player")
    assert m[2] == 0                 # exact
    assert m[1] == 1                 # same tokens, accents and order differ
    assert pd.isna(m[0])             # "Rodri" in club B must not match club A


def test_position_group():
    assert position_group("F M S", "FW") == "Forward"
    assert position_group("GK", "GK") == "Goalkeeper"
    assert position_group("S", "DF,MF") == "Defender"


def test_probable_xi_uses_recent_formation_and_starters():
    rows = []
    for i, (form, striker) in enumerate([("4-4-2", "Old"), ("4-3-3", "A"), ("4-3-3", "A"), ("4-3-3", "B")]):
        rows.append({"competition": "eng.1", "season": 2627, "team": "X", "event_id": i,
                     "date": pd.Timestamp("2026-09-01") + pd.Timedelta(days=7 * i), "starter": True,
                     "formation": form, "formation_place": "11", "athlete_id": striker, "player": striker,
                     "position_abbr": "F", "position": "Forward"})
    xi = probable_xi(pd.DataFrame(rows))
    assert xi.formation.iloc[0] == "4-3-3"
    assert xi.player.iloc[0] == "A"  # two recent starts beat one more recent start
