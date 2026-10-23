"""Phase 3: exploratory data analysis of the 13 season-level attacking features.

Run from the project root:  python -m src.model.eda
Writes figures to reports/figures/eda_*.png and a summary to reports/phase3_eda.md.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

from src.process.features import CLUSTER_FEATURES

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "reports" / "figures"
LEAGUE_ORDER = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A"]
LEAGUE_SHORT = {"ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga", "ITA-Serie A": "Serie A"}


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ROOT / "data" / "processed" / "team_season.csv")
    feats = list(CLUSTER_FEATURES)
    X = df[feats]
    lines = ["# Phase 3: Exploratory data analysis", "", f"Clubs: {len(df)} (20 per league). Features: {len(feats)}.", ""]

    # Descriptive statistics and normality (skew; Shapiro-Wilk is informative at n = 60).
    desc = X.describe().T[["mean", "std", "min", "max"]]
    desc["skew"] = X.skew()
    desc["shapiro_p"] = [stats.shapiro(X[c]).pvalue for c in feats]
    lines += ["## Descriptive statistics", "", desc.round(3).to_markdown(), ""]

    # League means and one-way ANOVA / Kruskal-Wallis per feature.
    rows = []
    for c in feats:
        groups = [df.loc[df["league"] == lg, c] for lg in LEAGUE_ORDER]
        rows.append({"feature": c, **{LEAGUE_SHORT[lg]: g.mean() for lg, g in zip(LEAGUE_ORDER, groups)},
                     "anova_p": stats.f_oneway(*groups).pvalue, "kruskal_p": stats.kruskal(*groups).pvalue})
    league = pd.DataFrame(rows).set_index("feature")
    lines += ["## League means (context only; league is not a clustering feature)", "", league.round(3).to_markdown(), "",
              "Possession averages exactly 50% in every league by construction (it is zero-sum within a league), "
              "and most volume features are close to that: league averages barely differ. Differences in "
              "*style* therefore have to show up in how clubs are spread within each league, which is what the "
              "cluster-by-league analysis (Phase 4) tests.", ""]

    # Correlation structure: motivates PCA.
    corr = X.corr()
    upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), 1))
    pairs = upper.stack().dropna().sort_values(key=abs, ascending=False)
    strong = pairs[pairs.abs() >= 0.7]
    lines += ["## Strong correlations (|r| >= 0.7)", "",
              "\n".join(f"- {a} ~ {b}: r = {r:.2f}" for (a, b), r in strong.items()), "",
              f"{len(strong)} of {len(pairs)} feature pairs have |r| >= 0.7, confirming the multicollinearity "
              "that motivates PCA before clustering (Gu et al., 2025).", ""]

    # Outliers: |z| > 3 on any feature (flagged, not removed; outlier clubs are of interest for DBSCAN).
    z = (X - X.mean()) / X.std()
    out = [(df.loc[i, "team"], c, z.loc[i, c]) for i in z.index for c in feats if abs(z.loc[i, c]) > 3]
    lines += ["## Outliers (|z| > 3)", "",
              "\n".join(f"- {t}: {c} (z = {v:.2f})" for t, c, v in out) or "- none", "",
              "Outliers are kept: they are real clubs, and identifying statistically unique clubs is an "
              "explicit aim of the DBSCAN stage.", ""]

    # Figures.
    fig, axes = plt.subplots(4, 4, figsize=(16, 13))
    for ax, c in zip(axes.flat, feats):
        sns.histplot(df, x=c, hue="league", hue_order=LEAGUE_ORDER, multiple="stack", ax=ax, legend=ax is axes.flat[0])
        ax.set_title(CLUSTER_FEATURES[c], fontsize=9)
        ax.set_xlabel("")
    for ax in axes.flat[len(feats):]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "eda_distributions.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1, square=True, ax=ax, annot_kws={"size": 8})
    ax.set_title("Correlation of attacking features (60 clubs, 2025/26)")
    fig.tight_layout()
    fig.savefig(FIG / "eda_correlation.png", dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(4, 4, figsize=(16, 13))
    for ax, c in zip(axes.flat, feats):
        sns.boxplot(df, x="league", y=c, order=LEAGUE_ORDER, ax=ax)
        ax.set_xticks(range(3), [LEAGUE_SHORT[lg] for lg in LEAGUE_ORDER], fontsize=8)
        ax.set_title(CLUSTER_FEATURES[c], fontsize=9)
        ax.set_xlabel("")
        ax.set_ylabel("")
    for ax in axes.flat[len(feats):]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "eda_league_boxplots.png", dpi=130)
    plt.close(fig)

    lines += ["## Figures", "", "- `figures/eda_distributions.png`", "- `figures/eda_correlation.png`",
              "- `figures/eda_league_boxplots.png`"]
    (ROOT / "reports" / "phase3_eda.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
