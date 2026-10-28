import pandas as pd

from src.process.build_legacy import assign_managers, honours, season_end_year

NAMES = {"Q1": "Arsenal", "Q2": "Juventus"}


def raw_honours(rows):
    return pd.DataFrame(rows, columns=["club", "ev", "evLabel", "comp", "parentComp"])


def test_season_end_year():
    assert season_end_year("1984–85 European Cup") == 1985
    assert season_end_year("2005 UEFA Champions League Final") == 2005
    assert season_end_year("Juventus FC 2-0 Pafos FC") is None
    assert season_end_year("2020-10-20 Dynamo Kyiv vs Juventus") is None


def test_honours_dedupes_season_and_final_and_drops_matches():
    h = honours(raw_honours([
        ("Q1", "E1", "2013–14 FA Cup", "Q11151", None),
        ("Q1", "E2", "2014 FA Cup Final", None, "Q11151"),  # the same trophy, recorded twice
        ("Q1", "E3", "1930–31 Football League", "Q213347", None),
        ("Q1", "E4", "1930–31 Football League First Division", "Q754839", None),  # same title again
        ("Q1", "E5", "Arsenal v Swansea 2016-17 Premier League", None, "Q9448"),  # a single match
        ("Q1", "E6", "2001–02 Football League First Division", "Q754839", None),  # second tier after 1992
    ]), NAMES)
    counts = h[h.team == "Arsenal"].groupby("category").size().to_dict()
    assert counts == {"Domestic cup": 1, "League title": 1, "Second-tier title": 1}


def test_honours_applies_corrections():
    h = honours(raw_honours([("Q2", "E1", "2004–05 Serie A", "Q15804", None),
                             ("Q2", "E2", "2011–12 Serie A", "Q15804", None)]), NAMES)
    league = h[(h.team == "Juventus") & (h.category == "League title")]
    assert league.season.tolist() == ["2011/12"]  # 2004/05 was revoked
    assert "2023/24" in h[(h.team == "Juventus") & (h.category == "Domestic cup")].season.tolist()  # added by hand


def test_assign_managers_prefers_latest_spell():
    tm = pd.DataFrame({"team": ["A"] * 3, "date": pd.to_datetime(["2025-09-01", "2026-01-10", "2026-03-01"])})
    spells = pd.DataFrame({"team": ["A", "A", "A"], "manager": ["Old", "Caretaker", "New"],
                           "start": pd.to_datetime(["2024-07-01", "2026-01-05", "2026-01-20"]),
                           "end": pd.to_datetime(["2026-01-04", "2026-01-19", None])})
    assert assign_managers(tm, spells).tolist() == ["Old", "Caretaker", "New"]
