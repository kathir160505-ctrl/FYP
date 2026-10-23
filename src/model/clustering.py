"""Phase 4: PCA + clustering of attacking styles, validation, profiling and league analysis.

Run from the project root:  python -m src.model.clustering

Final model (chosen from the evidence in reports/phase4_clustering.md):
StandardScaler -> PCA (components with eigenvalue > 1) -> KMeans (k = FINAL_K).

Outputs:
- models/cluster_model.joblib        fitted pipeline + cluster names, used by the app
- data/processed/clusters.csv         one row per club: cluster, PCs, silhouette, outlier flag, halves
- data/processed/cluster_profiles.csv cluster mean z-scores and raw means per feature
- data/processed/similar_clubs.csv    5 most similar clubs per club (cross-league scouting)
- data/processed/model_selection.csv  validity indices for every algorithm and k
- reports/phase4_clustering.md        + reports/figures/cluster_*.png
"""
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.stats import chi2_contingency
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score,
                             silhouette_samples, silhouette_score)
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.process.features import CLUSTER_FEATURES

ROOT = Path(__file__).resolve().parents[2]
PROC, FIG, MODELS = ROOT / "data" / "processed", ROOT / "reports" / "figures", ROOT / "models"
SEED = 42
K_RANGE = range(2, 9)
FINAL_K = 4
N_BOOT = 200
N_PERM = 10_000
FEATURES = list(CLUSTER_FEATURES)
HALF_FEATURES = [f for f in FEATURES if f != "fast_attack_shots"]  # attack speed is season-level only

# Names are assigned by ranking clusters on PC1 (overall attacking dominance), then checked
# against each cluster's feature profile in check_names(), so a re-run cannot silently mislabel.
CLUSTER_NAMES = [
    "Dominant Possession",
    "Controlled Build-up",
    "Direct & Cross-Oriented",
    "Long-Ball Low Block",
]
CLUSTER_BLURBS = {
    "Dominant Possession": "Monopolise the ball and the opposition half: the most passes, deep completions, "
                           "shots and xG, with the fewest long balls.",
    "Controlled Build-up": "Patient, accurate passing that rarely goes long or wide: few crosses, but the "
                           "highest share of shots on target and strong finishing efficiency.",
    "Direct & Cross-Oriented": "Below-average possession, with more long balls and crosses: attacks reach the "
                               "box quickly and from wide areas rather than through sustained build-up.",
    "Long-Ball Low Block": "The most direct passing profile and the lowest possession and pass accuracy, "
                           "with the lowest attacking output and finishing return.",
}
LEAGUE_SHORT = {"ENG-Premier League": "Premier League", "ESP-La Liga": "La Liga", "ITA-Serie A": "Serie A"}


def build_pipeline(n_components: int, k: int) -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("pca", PCA(n_components=n_components, random_state=SEED)),
        ("kmeans", KMeans(n_clusters=k, n_init=100, random_state=SEED)),
    ])


def kaiser_components(Z: np.ndarray) -> PCA:
    full = PCA(random_state=SEED).fit(Z)
    return full, int((full.explained_variance_ > 1).sum())


def model_selection(P: np.ndarray) -> pd.DataFrame:
    rows = []
    for k in K_RANGE:
        km = KMeans(k, n_init=100, random_state=SEED).fit(P)
        ag = AgglomerativeClustering(k, linkage="ward").fit(P)
        for name, lab, inertia in (("KMeans", km.labels_, km.inertia_), ("Agglomerative (Ward)", ag.labels_, np.nan)):
            rows.append({"algorithm": name, "k": k, "silhouette": silhouette_score(P, lab),
                         "davies_bouldin": davies_bouldin_score(P, lab),
                         "calinski_harabasz": calinski_harabasz_score(P, lab), "inertia": inertia,
                         "min_cluster_size": int(np.bincount(lab).min()),
                         "bootstrap_ari": bootstrap_ari(P, k) if name == "KMeans" else np.nan})
    return pd.DataFrame(rows)


def bootstrap_ari(P: np.ndarray, k: int, n_boot: int = N_BOOT) -> float:
    """Mean ARI between the full-data solution and solutions refitted on bootstrap resamples."""
    rng = np.random.default_rng(SEED)
    full = KMeans(k, n_init=50, random_state=SEED).fit(P)
    scores = []
    for _ in range(n_boot):
        idx = rng.choice(len(P), len(P), replace=True)
        uniq = np.unique(idx)
        boot = KMeans(k, n_init=10, random_state=int(rng.integers(1_000_000))).fit(P[idx])
        scores.append(adjusted_rand_score(full.labels_[uniq], boot.predict(P[uniq])))
    return float(np.mean(scores))


def knee(values: np.ndarray) -> float:
    """Knee of a sorted curve: the point furthest from the line joining its endpoints."""
    y = np.sort(values)
    x = np.linspace(0, 1, len(y))
    yn = (y - y[0]) / (y[-1] - y[0])
    return float(y[np.argmax(x - yn)])


DBSCAN_MIN_SAMPLES = range(3, 11)
DBSCAN_EPS_SCALE = (0.9, 1.0, 1.1)


def dbscan_uniqueness(P: np.ndarray) -> np.ndarray:
    """Share of DBSCAN settings in which each club is a noise point.

    At n = 60 a single DBSCAN setting is very sensitive to min_samples and eps, so it is run
    over a grid (min_samples 3-10, eps at 0.9/1.0/1.1 x the knee of the k-distance curve).
    A club flagged as noise in most settings is statistically unique.
    """
    noise, runs = np.zeros(len(P)), 0
    for ms in DBSCAN_MIN_SAMPLES:
        kdist = NearestNeighbors(n_neighbors=ms).fit(P).kneighbors(P)[0][:, -1]
        for scale in DBSCAN_EPS_SCALE:
            noise += DBSCAN(eps=knee(kdist) * scale, min_samples=ms).fit_predict(P) == -1
            runs += 1
    return noise / runs


def name_clusters(labels: np.ndarray, pcs: np.ndarray) -> dict[int, str]:
    order = pd.Series(pcs[:, 0]).groupby(labels).mean().sort_values(ascending=False).index
    return {int(c): CLUSTER_NAMES[i] for i, c in enumerate(order)}


def check_names(profile_z: pd.DataFrame) -> None:
    """Fail loudly if a cluster's profile no longer matches the meaning of its name."""
    p = profile_z
    assert p.loc["Dominant Possession", "possession"] == p["possession"].max()
    assert p.loc["Long-Ball Low Block", "long_ball_share"] == p["long_ball_share"].max()
    assert p.loc["Controlled Build-up", "crosses"] < 0 < p.loc["Direct & Cross-Oriented", "crosses"]
    assert p.loc["Controlled Build-up", "sot_pct"] == p["sot_pct"].max()


def similar_clubs(df: pd.DataFrame, Z: np.ndarray, n: int = 5) -> pd.DataFrame:
    """Nearest clubs in standardised feature space (Euclidean), with a 0-100 similarity score."""
    d = np.linalg.norm(Z[:, None, :] - Z[None, :, :], axis=2)
    scale = np.quantile(d[np.triu_indices(len(Z), 1)], 0.95)
    rows = []
    for i in range(len(df)):
        for rank, j in enumerate(np.argsort(d[i])[1:n + 1], 1):
            rows.append({"team": df.team[i], "rank": rank, "similar_team": df.team[j],
                         "similar_league": df.league[j], "distance": d[i, j],
                         "similarity": max(0.0, 100 * (1 - d[i, j] / scale))})
    return pd.DataFrame(rows)


def league_test(crosstab: pd.DataFrame) -> dict:
    chi2, p, dof, expected = chi2_contingency(crosstab)
    n = crosstab.to_numpy().sum()
    cramers_v = np.sqrt(chi2 / (n * (min(crosstab.shape) - 1)))
    # Many expected counts are < 5 at n = 60, so also report a permutation p-value.
    rng = np.random.default_rng(SEED)
    leagues = np.repeat(crosstab.index, crosstab.sum(axis=1))
    clusters = np.concatenate([np.repeat(crosstab.columns, row) for _, row in crosstab.iterrows()])
    perm = [chi2_contingency(pd.crosstab(leagues, rng.permutation(clusters)))[0] for _ in range(N_PERM)]
    return {"chi2": chi2, "dof": dof, "p_asymptotic": p, "p_permutation": (np.sum(np.array(perm) >= chi2) + 1) / (N_PERM + 1),
            "cramers_v": cramers_v, "min_expected": expected.min(), "share_expected_below_5": (expected < 5).mean()}


def split_half(season: pd.DataFrame, halves: pd.DataFrame, n_components: int, final_labels: np.ndarray) -> dict:
    """Fit on season data without the season-only feature, then assign each club's H1 and H2 profiles."""
    model = build_pipeline(n_components, FINAL_K).fit(season[HALF_FEATURES])
    season_lab = model.predict(season[HALF_FEATURES])
    out = {"ari_12_vs_13_features": adjusted_rand_score(final_labels, season_lab)}
    h = {}
    for half in ("H1", "H2"):
        part = halves[halves["half"] == half].set_index("team").loc[season["team"]]
        h[half] = model.predict(part[HALF_FEATURES])
    out["same_cluster_h1_h2"] = float(np.mean(h["H1"] == h["H2"]))
    out["ari_h1_h2"] = adjusted_rand_score(h["H1"], h["H2"])
    out["ari_h2_vs_season"] = adjusted_rand_score(season_lab, h["H2"])
    # Map the 12-feature model's cluster ids onto the final names via majority overlap.
    mapping = pd.crosstab(season_lab, final_labels).idxmax(axis=1).to_dict()
    out["h1"] = np.vectorize(mapping.get)(h["H1"])
    out["h2"] = np.vectorize(mapping.get)(h["H2"])
    return out


def plots(df, P, pca_full, n_comp, sel, prof_z, labels_named, loadings, Z):
    FIG.mkdir(parents=True, exist_ok=True)
    km = sel[sel.algorithm == "KMeans"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    axes[0].plot(km.k, km.inertia, "o-")
    axes[0].set(title="Elbow (KMeans within-cluster SS)", xlabel="k", ylabel="inertia")
    for alg, g in sel.groupby("algorithm"):
        axes[1].plot(g.k, g.silhouette, "o-", label=alg)
        axes[2].plot(g.k, g.davies_bouldin, "o-", label=alg)
    axes[1].set(title="Silhouette (higher is better)", xlabel="k")
    axes[2].set(title="Davies-Bouldin (lower is better)", xlabel="k")
    axes[1].legend()
    for ax in axes:
        ax.axvline(FINAL_K, color="grey", ls="--", lw=1)
    fig.tight_layout()
    fig.savefig(FIG / "cluster_model_selection.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    evr = pca_full.explained_variance_ratio_
    ax.bar(range(1, len(evr) + 1), evr * 100, label="per component")
    ax.plot(range(1, len(evr) + 1), np.cumsum(evr) * 100, "o-", color="C1", label="cumulative")
    ax.axvline(n_comp + 0.5, color="grey", ls="--", lw=1)
    ax.set(title=f"PCA explained variance ({n_comp} components retained, eigenvalue > 1)", xlabel="component", ylabel="%")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "cluster_pca_variance.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 7))
    sns.heatmap(loadings, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax)
    ax.set_title("PCA loadings")
    fig.tight_layout()
    fig.savefig(FIG / "cluster_pca_loadings.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.scatterplot(x=P[:, 0], y=P[:, 1], hue=labels_named, style=df.league, s=90, ax=ax, hue_order=CLUSTER_NAMES)
    for i, t in enumerate(df.team):
        ax.annotate(t, (P[i, 0], P[i, 1]), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.legend(title="Cluster (colour) / league (marker)", fontsize=8)
    ax.set(title="Attacking-style map: clubs on the first two principal components",
           xlabel=f"PC1 ({pca_full.explained_variance_ratio_[0]:.0%}) attacking dominance",
           ylabel=f"PC2 ({pca_full.explained_variance_ratio_[1]:.0%}) crossing volume vs finishing efficiency")
    fig.tight_layout()
    fig.savefig(FIG / "cluster_style_map.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(13, 4))
    sns.heatmap(prof_z.loc[CLUSTER_NAMES], annot=True, fmt=".1f", cmap="RdBu_r", center=0, ax=ax)
    ax.set_title("Cluster profiles (mean z-score per feature)")
    fig.tight_layout()
    fig.savefig(FIG / "cluster_profiles.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(16, 5))
    dendrogram(linkage(P, "ward"), labels=df.team.tolist(), leaf_font_size=7, ax=ax)
    ax.set_title("Ward hierarchical clustering on the retained principal components")
    fig.tight_layout()
    fig.savefig(FIG / "cluster_dendrogram.png", dpi=130)
    plt.close(fig)


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    df = pd.read_csv(PROC / "team_season.csv")
    halves = pd.read_csv(PROC / "team_half.csv")
    Z = StandardScaler().fit_transform(df[FEATURES])
    pca_full, n_comp = kaiser_components(Z)
    P = pca_full.transform(Z)[:, :n_comp]

    sel = model_selection(P)
    model = build_pipeline(n_comp, FINAL_K).fit(df[FEATURES])
    labels = model.predict(df[FEATURES])
    names = name_clusters(labels, P)
    named = np.array([names[c] for c in labels])

    k2 = KMeans(2, n_init=100, random_state=SEED).fit_predict(P)
    k2_named = np.where(pd.Series(P[:, 0]).groupby(k2).transform("mean") > 0, "Possession-dominant", "Reactive / direct")
    ward = AgglomerativeClustering(FINAL_K, linkage="ward").fit_predict(P)
    uniqueness = dbscan_uniqueness(P)

    zdf = pd.DataFrame(Z, columns=FEATURES).assign(cluster=named)
    prof_z = zdf.groupby("cluster")[FEATURES].mean()
    check_names(prof_z)
    prof_raw = df[FEATURES].assign(cluster=named).groupby("cluster").mean()
    sh = split_half(df, halves, n_comp, labels)
    xt = pd.crosstab(df["league"].map(LEAGUE_SHORT), named)[CLUSTER_NAMES]
    test = league_test(xt)
    loadings = pd.DataFrame(pca_full.components_[:n_comp].T, index=FEATURES, columns=[f"PC{i + 1}" for i in range(n_comp)])

    clusters = df[["league", "team"]].assign(
        cluster=named, cluster_id=labels, top_level=k2_named, silhouette=silhouette_samples(P, labels),
        uniqueness=uniqueness, dbscan_outlier=uniqueness > 0.5, ward_cluster=ward, cluster_h1=[names[c] for c in sh["h1"]],
        cluster_h2=[names[c] for c in sh["h2"]],
        **{f"PC{i + 1}": P[:, i] for i in range(n_comp)})
    clusters.to_csv(PROC / "clusters.csv", index=False)
    pd.concat({"z": prof_z, "mean": prof_raw}, names=["kind"]).reset_index().to_csv(PROC / "cluster_profiles.csv", index=False)
    similar_clubs(df, Z).to_csv(PROC / "similar_clubs.csv", index=False)
    sel.to_csv(PROC / "model_selection.csv", index=False)
    joblib.dump({"pipeline": model, "features": FEATURES, "names": names, "blurbs": CLUSTER_BLURBS,
                 "n_components": n_comp, "explained_variance": pca_full.explained_variance_ratio_[:n_comp],
                 "loadings": loadings, "league_test": test, "split_half": {k: v for k, v in sh.items() if k not in ("h1", "h2")}},
                MODELS / "cluster_model.joblib")
    plots(df, P, pca_full, n_comp, sel, prof_z, named, loadings, Z)
    write_report(df, pca_full, n_comp, loadings, sel, clusters, prof_z, prof_raw, xt, test, sh, ward, labels)


def write_report(df, pca_full, n_comp, loadings, sel, clusters, prof_z, prof_raw, xt, test, sh, ward, labels):
    evr = pca_full.explained_variance_ratio_
    final = sel[(sel.algorithm == "KMeans") & (sel.k == FINAL_K)].iloc[0]
    L = ["# Phase 4: Clustering attacking styles", "",
         "## 1. Dimensionality reduction (PCA)", "",
         f"Features were z-scored and reduced by PCA. **{n_comp} components** have eigenvalue > 1 (Kaiser criterion) "
         f"and together explain **{evr[:n_comp].sum():.1%}** of the variance "
         f"({', '.join(f'PC{i + 1} {v:.1%}' for i, v in enumerate(evr[:n_comp]))}).", "",
         loadings.round(2).to_markdown(), "",
         "- **PC1, attacking dominance:** possession, passing volume and accuracy, deep completions, shots, xG and goals, against long balls.",
         "- **PC2, crossing volume vs finishing efficiency:** crosses and shots against shots on target % and goals per shot.",
         "- **PC3, box presence:** share of shots inside the penalty area and crosses.",
         "- **PC4, counter-attack:** fast-attack shots.", "",
         "## 2. Model selection", "",
         "KMeans and Ward agglomerative clustering were compared for k = 2–8 on the retained components. "
         f"KMeans stability is the mean adjusted Rand index (ARI) over {N_BOOT} bootstrap resamples.", "",
         sel.round(3).to_markdown(index=False), "",
         f"**Chosen: KMeans, k = {FINAL_K}.** Silhouette is highest at k = 2. That solution only separates "
         "possession-dominant clubs from the rest, so it is kept as a top-level split (`top_level` in clusters.csv). "
         f"Among k ≥ 3, k = {FINAL_K} has the highest bootstrap stability, sits at the elbow of the within-cluster "
         "sum of squares, and gives interpretable, reasonably balanced groups within the 3–6 range expected in H2. "
         f"Final indices: silhouette {final.silhouette:.3f}, Davies–Bouldin {final.davies_bouldin:.3f}, "
         f"Calinski–Harabasz {final.calinski_harabasz:.1f}, bootstrap ARI {final.bootstrap_ari:.2f}. "
         f"Agreement with Ward clustering at the same k: ARI = {adjusted_rand_score(labels, ward):.2f}.", "",
         "Silhouette values of 0.25–0.40 indicate moderate, overlapping structure. This is typical for team-level "
         "style data, where styles sit on a continuum rather than in sharply separated groups (Gu et al., 2025).", "",
         "## 3. Cluster profiles", ""]
    for name in CLUSTER_NAMES:
        members = clusters[clusters.cluster == name]
        z = prof_z.loc[name].sort_values()
        L += [f"### {name} ({len(members)} clubs)", "", CLUSTER_BLURBS[name], "",
              f"- Highest features: {', '.join(f'{f} ({v:+.1f} SD)' for f, v in z[::-1][:3].items())}",
              f"- Lowest features: {', '.join(f'{f} ({v:+.1f} SD)' for f, v in z[:3].items())}",
              f"- Clubs: {', '.join(members.sort_values('PC1', ascending=False).team)}", ""]
    L += ["Mean raw values per cluster:", "", prof_raw.loc[CLUSTER_NAMES].round(2).T.to_markdown(), "",
          "## 4. Statistically unique clubs (DBSCAN)", "",
          "DBSCAN is used as an outlier detector. At n = 60 it cannot form stable groups, and any single "
          "setting is highly sensitive to `min_samples` and `eps`. It was therefore run over "
          f"{len(DBSCAN_MIN_SAMPLES) * len(DBSCAN_EPS_SCALE)} settings (min_samples "
          f"{DBSCAN_MIN_SAMPLES.start}–{DBSCAN_MIN_SAMPLES.stop - 1}; eps at 0.9, 1.0 and 1.1 × the knee of the k-distance curve). "
          "A club's *uniqueness* is the share of settings in which it is a noise point. Clubs above 50% are flagged:", "",
          clusters.sort_values("uniqueness", ascending=False).head(10)[["team", "league", "cluster", "uniqueness"]]
          .round(2).to_markdown(index=False), "",
          f"Flagged as statistically unique: **{', '.join(clusters[clusters.dbscan_outlier].sort_values('uniqueness', ascending=False).team)}**.", "",
          "## 5. Validation", "",
          f"- **Bootstrap stability:** mean ARI {final.bootstrap_ari:.2f} over {N_BOOT} resamples.",
          f"- **Split-half:** the model was refitted without the season-only counter-attack feature "
          f"(ARI vs the 13-feature solution: {sh['ari_12_vs_13_features']:.2f}). First-half and second-half profiles were then assigned. "
          f"**{sh['same_cluster_h1_h2']:.0%} of clubs keep the same cluster** across the two halves "
          f"(ARI H1 vs H2 = {sh['ari_h1_h2']:.2f}).",
          "- **Face validity:** see the cluster memberships above, compared with the clubs' documented reputations.", "",
          "Clubs whose cluster changed between halves:", "",
          "\n".join(f"- {r.team}: {r.cluster_h1} → {r.cluster_h2}" for r in clusters.itertuples() if r.cluster_h1 != r.cluster_h2) or "- none", "",
          "## 6. Cluster distribution across leagues (RQ2)", "",
          xt.to_markdown(), "",
          f"χ² = {test['chi2']:.2f}, df = {test['dof']}, asymptotic p = {test['p_asymptotic']:.3f}, "
          f"permutation p = {test['p_permutation']:.3f} ({N_PERM:,} permutations), Cramér's V = {test['cramers_v']:.2f}. "
          f"{test['share_expected_below_5']:.0%} of expected counts are below 5, so the permutation p-value is the one to report.", "",
          "## Figures", "",
          *[f"- `figures/{f}`" for f in ("cluster_pca_variance.png", "cluster_pca_loadings.png", "cluster_model_selection.png",
                                          "cluster_style_map.png", "cluster_profiles.png", "cluster_dendrogram.png")]]
    (ROOT / "reports" / "phase4_clustering.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
