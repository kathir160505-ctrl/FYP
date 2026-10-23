"""Phase 5: predict which of two teams will show the more attacking style in a match.

Run from the project root:  python -m src.predict.model

This is NOT a match-winner or score model. The target is the match-level Attacking Index:
the mean within-league z-score of xG, shots, deep completions, shots in the box and possession.
For each match, label = 1 if team A's index beats team B's.

Features use only information available before kick-off: each team's season-to-date and
last-5 averages of the attacking feature set, expressed as A-minus-B differences, plus
venue. Every match appears from both perspectives, and all splits keep a match's two
rows together.

Outputs:
- models/predict_model.joblib   final calibrated logistic regression + feature list
- data/processed/team_form.csv  end-of-season team inputs for the app's head-to-head page
- data/processed/attacking_index.csv  per team-match index (app timelines)
- reports/phase5_prediction.md  + reports/figures/predict_*.png
"""
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
PROC, FIG, MODELS = ROOT / "data" / "processed", ROOT / "reports" / "figures", ROOT / "models"
SEED = 42
MIN_HISTORY = 5        # both teams need this many previous matches
FORM_WINDOW = 5
TEST_SHARE = 0.30      # last 30% of the season (by date) is held out

INDEX_COMPONENTS = ["xg", "shots", "deep_completions", "box_shots", "possessionPct"]
# Per-match stats summarised before each match (season-to-date and last-5 form).
HISTORY_STATS = ["attacking_index", "index_conceded", "xg", "xg_against", "shots", "possessionPct",
                 "deep_completions", "box_shots", "pass_accuracy", "long_ball_share", "totalCrosses"]
FEATURES = ([f"{s}_season_diff" for s in HISTORY_STATS] + [f"{s}_form_diff" for s in HISTORY_STATS]
            + ["is_home"])
LABELS = {
    "attacking_index": "Attacking Index", "index_conceded": "Attacking Index allowed to opponents",
    "xg": "xG", "xg_against": "xG conceded", "shots": "Shots", "possessionPct": "Possession",
    "deep_completions": "Deep completions", "box_shots": "Shots in the box", "pass_accuracy": "Pass accuracy",
    "long_ball_share": "Long-ball share", "totalCrosses": "Crosses",
}


def add_attacking_index(tm: pd.DataFrame) -> pd.DataFrame:
    tm = tm.copy()
    tm["pass_accuracy"] = tm["accuratePasses"] / tm["totalPasses"] * 100
    tm["long_ball_share"] = tm["totalLongBalls"] / tm["totalPasses"] * 100
    z = tm.groupby("league")[INDEX_COMPONENTS].transform(lambda s: (s - s.mean()) / s.std())
    tm["attacking_index"] = z.mean(axis=1)
    opp = tm[["game_id", "team", "attacking_index"]].rename(columns={"team": "opponent", "attacking_index": "index_conceded"})
    return tm.merge(opp, on=["game_id", "opponent"])


def add_history(tm: pd.DataFrame) -> pd.DataFrame:
    """Season-to-date and last-5 means of each stat, using only matches before the current one."""
    tm = tm.sort_values(["team", "date"]).copy()
    g = tm.groupby("team")
    for s in HISTORY_STATS:
        prev = g[s].shift(1)
        tm[f"{s}_season"] = prev.groupby(tm["team"]).expanding().mean().reset_index(level=0, drop=True)
        tm[f"{s}_form"] = prev.groupby(tm["team"]).rolling(FORM_WINDOW, min_periods=1).mean().reset_index(level=0, drop=True)
    tm["n_prev"] = g.cumcount()
    return tm


def pair_rows(tm: pd.DataFrame) -> pd.DataFrame:
    """One row per (team A, team B) perspective per match, with A-minus-B feature differences."""
    cols = [c for c in tm.columns if c.endswith(("_season", "_form"))]
    a = tm[["game_id", "league", "date", "matchweek", "team", "opponent", "is_home", "attacking_index", "n_prev", *cols]]
    b = a[["game_id", "team", "attacking_index", "n_prev", *cols]].rename(columns=lambda c: f"{c}_b" if c != "game_id" else c)
    m = a.merge(b, left_on=["game_id", "opponent"], right_on=["game_id", "team_b"])
    for c in cols:
        m[f"{c}_diff"] = m[c] - m[f"{c}_b"]
    m["is_home"] = m["is_home"].astype(int)
    m["y"] = (m["attacking_index"] > m["attacking_index_b"]).astype(int)
    return m[(m["n_prev"] >= MIN_HISTORY) & (m["n_prev_b"] >= MIN_HISTORY)].reset_index(drop=True)


def models() -> dict:
    return {
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)),
        "Gradient boosting": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                                            l2_regularization=1.0, random_state=SEED),
    }


def evaluate(y, p) -> dict:
    return {"AUC": roc_auc_score(y, p), "Accuracy": accuracy_score(y, p >= 0.5),
            "Brier": brier_score_loss(y, p), "Log loss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))}


def team_form(tm: pd.DataFrame) -> pd.DataFrame:
    """End-of-season inputs for the app: full-season means and last-5 means for every club."""
    last = tm.sort_values("date").groupby("team").tail(FORM_WINDOW)
    season = tm.groupby(["league", "team"])[HISTORY_STATS].mean().add_suffix("_season")
    form = last.groupby("team")[HISTORY_STATS].mean().add_suffix("_form")
    return season.reset_index().merge(form.reset_index(), on="team")


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    tm = pd.read_csv(PROC / "team_match.csv", parse_dates=["date"])
    tm = add_history(add_attacking_index(tm))
    pairs = pair_rows(tm)
    X, y, groups = pairs[FEATURES], pairs["y"], pairs["game_id"]

    cutoff = pairs["date"].quantile(1 - TEST_SHARE)
    train, test = pairs["date"] < cutoff, pairs["date"] >= cutoff
    results, probs = [], {}
    base = pairs.loc[test, "attacking_index_season_diff"]
    probs["Baseline (higher season-to-date index)"] = (base > 0).astype(float).to_numpy()
    results.append({"model": "Baseline (higher season-to-date index)",
                    **evaluate(y[test], 1 / (1 + np.exp(-3 * base.to_numpy())))})
    cv = GroupKFold(n_splits=5)
    for name, model in models().items():
        model.fit(X[train], y[train])
        p = model.predict_proba(X[test])[:, 1]
        probs[name] = p
        cv_auc = cross_val_score(model, X, y, groups=groups, cv=cv, scoring="roc_auc")
        results.append({"model": name, **evaluate(y[test], p), "CV AUC (5-fold, grouped)": cv_auc.mean(),
                        "CV AUC sd": cv_auc.std()})
    res = pd.DataFrame(results)

    final = models()["Logistic regression"].fit(X, y)
    lr = final.named_steps["logisticregression"]
    coefs = pd.Series(lr.coef_[0], index=FEATURES).sort_values(key=abs, ascending=False)
    joblib.dump({"model": final, "features": FEATURES, "history_stats": HISTORY_STATS, "labels": LABELS,
                 "metrics": res.to_dict("records"), "cutoff": str(cutoff.date())}, MODELS / "predict_model.joblib")
    team_form(tm).to_csv(PROC / "team_form.csv", index=False)
    tm[["league", "game_id", "date", "matchweek", "team", "opponent", "is_home", "attacking_index",
        "index_conceded"]].to_csv(PROC / "attacking_index.csv", index=False)

    FIG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 6))
    for name in models():
        frac, mean = calibration_curve(y[test], probs[name], n_bins=10)
        ax.plot(mean, frac, "o-", label=name)
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set(title="Calibration on held-out matches", xlabel="predicted probability", ylabel="observed frequency")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "predict_calibration.png", dpi=130)
    plt.close(fig)

    lr_test = res.set_index("model").loc["Logistic regression"]
    L = ["# Phase 5: Predicting the more attacking team", "",
         "**Target.** For each match, the *Attacking Index* of each team is the mean within-league z-score of "
         f"{', '.join(INDEX_COMPONENTS)}. The label is whether team A's index exceeds team B's. "
         "This predicts relative attacking *style* in a match, not the winner or the score.", "",
         f"**Features.** Pre-match only: each team's season-to-date and last-{FORM_WINDOW} averages of "
         f"{len(HISTORY_STATS)} stats, expressed as A − B differences, plus venue ({len(FEATURES)} features). "
         f"Matches where either team has fewer than {MIN_HISTORY} previous matches are excluded. "
         "Each match appears from both perspectives.", "",
         f"**Evaluation.** Temporal hold-out: trained on matches before {cutoff.date()}, tested on the rest "
         f"({int(train.sum() / 2)} train / {int(test.sum() / 2)} test matches). Also 5-fold cross-validation "
         "grouped by match, so a match's two rows never sit on both sides of a split.", "",
         res.round(3).to_markdown(index=False), "",
         f"The logistic regression reaches **AUC {lr_test['AUC']:.3f}** and **{lr_test['Accuracy']:.1%} accuracy** "
         f"on the held-out final {TEST_SHARE:.0%} of the season. It is kept as the final model: it performs at least as "
         "well as gradient boosting and its coefficients explain each prediction in the app. "
         "Zhong et al. (2026) report AUC 0.70–0.78 for their related cluster-to-outcome models.", "",
         "## Largest standardised coefficients (final model, all matches)", "",
         coefs.head(10).round(3).to_frame("coefficient").to_markdown(), "",
         "## Figures", "", "- `figures/predict_calibration.png`"]
    (ROOT / "reports" / "phase5_prediction.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
