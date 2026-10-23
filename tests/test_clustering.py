import numpy as np
import pandas as pd
import pytest

from src.model.clustering import CLUSTER_NAMES, check_names, knee, league_test, name_clusters, similar_clubs


def test_knee_finds_the_bend():
    curve = np.array([1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 4.0, 8.0])
    assert knee(curve) == 1.5


def test_name_clusters_orders_by_pc1():
    labels = np.array([0, 0, 1, 1, 2, 2, 3, 3])
    pcs = np.array([[-5], [-5], [5], [5], [0], [0], [2], [2]], dtype=float)
    names = name_clusters(labels, pcs)
    assert names == {1: CLUSTER_NAMES[0], 3: CLUSTER_NAMES[1], 2: CLUSTER_NAMES[2], 0: CLUSTER_NAMES[3]}


def test_check_names_rejects_a_mislabelled_profile():
    good = pd.DataFrame({
        "possession": [1.0, 0.2, -0.4, -1.0], "long_ball_share": [-1.0, -0.5, 0.4, 1.4],
        "crosses": [0.0, -0.7, 0.4, -0.2], "sot_pct": [0.2, 1.0, -0.3, -0.8],
    }, index=CLUSTER_NAMES)
    check_names(good)
    with pytest.raises(AssertionError):
        check_names(good.rename(index={CLUSTER_NAMES[0]: CLUSTER_NAMES[3], CLUSTER_NAMES[3]: CLUSTER_NAMES[0]}))


def test_similar_clubs_excludes_self_and_ranks_nearest_first():
    df = pd.DataFrame({"team": list("ABCDEFG"), "league": ["L"] * 7})
    Z = np.array([[0.0], [0.1], [5.0], [5.2], [9.0], [9.5], [20.0]])
    sim = similar_clubs(df, Z, n=2)
    a = sim[sim.team == "A"]
    assert a.similar_team.tolist() == ["B", "C"]
    assert (sim.team != sim.similar_team).all()
    assert a.similarity.iloc[0] > a.similarity.iloc[1]


def test_league_test_detects_strong_association():
    strong = pd.DataFrame([[10, 0], [0, 10]], index=["L1", "L2"], columns=["c1", "c2"])
    res = league_test(strong)
    assert res["p_permutation"] < 0.01
    assert res["cramers_v"] == pytest.approx(1.0, abs=0.15)
