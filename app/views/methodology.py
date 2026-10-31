import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import charts
import data
import ui

# The twelve stages of the proposal's research process (FYP1, Figure 3.1), with what this system did at each.
PIPELINE = [
    ("01", "Problem definition & objectives", "RQ1–RQ3 and RO1–RO3 from the proposal; gaps from the Chapter 2 "
                                              "literature review."),
    ("02", "Data collection", "Automated with the SoccerData library: Understat (xG, shots, deep completions, attack "
                              "speed) and ESPN (possession, passing, crosses) for all 1,140 matches of 2025/26. FBref "
                              "as an independent cross-check (r ≥ 0.977). StatsBomb has no 2025/26 data and Opta "
                              "Analyst no API, so they could not be used."),
    ("03", "Cleaning & feature engineering", "Club names harmonised, missing values checked, 13 attacking variables "
                                             "(Table 3.1) per match (≈ per 90 minutes); documented proxies where free "
                                             "data has gaps."),
    ("04", "Exploratory data analysis", "Distributions, correlations (|r| ≥ 0.7 flagged) and outliers (|z| > 3), "
                                        "kept because unique clubs are of interest."),
    ("05", "Scaling & dimensionality reduction", "z-score standardisation (StandardScaler), then PCA: 4 components "
                                                 "with eigenvalue > 1 keep 87.4% of the variance."),
    ("06", "Clustering & model selection", "K-means (primary) vs agglomerative (Ward) vs DBSCAN for k = 2–8; k "
                                           "chosen with the elbow method and silhouette, plus Davies–Bouldin, "
                                           "Calinski–Harabasz and bootstrap stability. Final: K-means, k = 4."),
    ("07", "Cluster interpretation & profiling", "Each cluster labelled from its standardised feature means and PCA "
                                                 "loadings: Dominant Possession, Controlled Build-up, Direct & "
                                                 "Cross-Oriented, Long-Ball Low Block."),
    ("08", "Cross-league distribution", "League × cluster cross-tabulation and χ² test of independence (permutation "
                                        "p = 0.45, Cramér's V = 0.22): not significant."),
    ("09", "Team comparison & prediction", "Logistic regression (vs gradient boosting) on pre-match form predicts "
                                           "which team shows the more attacking style: AUC 0.805 on a temporal "
                                           "hold-out."),
    ("10", "Web dashboard", "Streamlit + Plotly: team profiles, head-to-head comparison with the prediction, style "
                            "map, league comparison and this methodology page."),
    ("11", "Evaluation, verification & validation", "Silhouette and the other indices, unit tests, fixed seeds, "
                                                    "bootstrap stability (ARI 0.64), split-half (80% keep their "
                                                    "cluster) and face validity (below)."),
    ("12", "Documentation & reporting", "Every stage reproducible from scripts in src/, with reports in reports/ and "
                                        "sources attributed; version-controlled with Git."),
]

SOURCES = pd.DataFrame([
    ("Possession %", "ESPN", "Direct"), ("Ball control", "ESPN", "Pass accuracy %"),
    ("Passes per match", "ESPN", "Completed passes"), ("Progressive passes", "Understat", "Proxy: deep completions"),
    ("Directness", "ESPN", "Long-ball share of passes"), ("Crosses", "ESPN", "Direct"),
    ("Shots", "Understat", "Direct"), ("Shots on target %", "Understat", "Direct"),
    ("Expected goals", "Understat", "Direct"), ("Goals", "Understat", "Direct"), ("Goals per shot", "Understat", "Direct"),
    ("Counter-attacks", "Understat", "Proxy: shots from fast attacks"),
    ("Touches in box", "Understat", "Proxy: share of shots inside the box"),
    ("Through balls", "–", "Excluded: no free source for 2025/26"),
], columns=["Proposal variable", "Source", "Measurement"])


def render() -> None:
    cm, pm = data.cluster_model(), data.predict_model()
    sel = data.model_selection()
    ui.page_header("Methodology", "How the attacking philosophies were found",
                   "A reproducible, CRISP-DM-style pipeline. Every number in this dashboard is produced by "
                   "version-controlled code from openly available data.")

    cols = st.columns(3, gap="small")
    for i, (num, title, text) in enumerate(PIPELINE):
        cols[i % 3].markdown(f'<div class="card" style="margin-bottom:0.75rem"><div class="note" style="color:#D50000;'
                             f'font-weight:700;letter-spacing:0.1em">STEP {num}</div><h4 style="margin-top:0.2rem">{title}</h4>'
                             f'<p>{text}</p></div>', unsafe_allow_html=True)

    data_pipeline()

    c1, c2 = st.columns([1.2, 1], gap="medium")
    with c1:
        with ui.panel("Features and data sources", "Proposal Table 3.1 mapped to the free 2025/26 data"):
            st.dataframe(SOURCES, hide_index=True, placeholder="–", width="stretch", height=530)
    with c2:
        with ui.panel("Design choices"):
            ui.callout("League and season are grouping variables only. They are never clustering inputs, so clubs are "
                       "grouped by <b>how</b> they attack rather than where they play.")
            ui.note("Counts are per match, which equals per 90 minutes for team data. Ratios such as pass accuracy and "
                    "goals per shot are computed from season totals, so low-volume matches do not distort them.<br><br>"
                    "Club and match xG use Understat's match figure, which combines shots from the same rebound sequence "
                    "(1 − Π(1 − xGᵢ), at most 1.0 per chance). Shot maps sum individual shots, which is 1.5% higher for "
                    "the median club.")

    c1, c2 = st.columns([1, 1.2], gap="medium")
    with c1:
        with ui.panel("Explained variance", f"{cm['explained_variance'].sum():.1%} retained in "
                      f"{len(cm['explained_variance'])} components"):
            ev = cm["explained_variance"]
            fig = go.Figure(go.Bar(x=[f"PC{i + 1}" for i in range(len(ev))], y=ev * 100, marker_color="#0B0D10",
                                   text=[f"{v:.1%}" for v in ev], textposition="outside"))
            fig.update_yaxes(title="% of variance")
            st.plotly_chart(charts._layout(fig, height=360), width="stretch")
    with c2:
        with ui.panel("Component loadings", "PC1 attacking dominance · PC2 crossing vs finishing · PC3 box presence · "
                      "PC4 counter-attacking"):
            load = cm["loadings"].rename(index=data.SHORT_LABELS)
            fig = go.Figure(go.Heatmap(z=load.values, x=load.columns, y=load.index, colorscale="RdBu", zmid=0,
                                       text=load.round(2).values, texttemplate="%{text}", showscale=False))
            st.plotly_chart(charts._layout(fig, height=360), width="stretch")

    with ui.panel("Choosing the number of clusters", "Silhouette for both algorithms and bootstrap stability for "
                  "K-means, k = 2–8"):
        st.plotly_chart(charts.model_selection_chart(sel, 4), width="stretch")
        ui.callout("k = 2 has the highest silhouette but only separates possession-dominant clubs from the rest. Among "
                   "k ≥ 3, k = 4 is the most stable under bootstrap resampling and sits at the elbow of the within-cluster "
                   "sum of squares. Silhouettes of 0.25–0.40 indicate overlapping styles on a continuum, which is typical "
                   "of team-level style data.")
        st.dataframe(sel, hide_index=True, placeholder="–", width="stretch", column_config={
            c: st.column_config.NumberColumn(format="%.3f") for c in ("silhouette", "davies_bouldin", "bootstrap_ari")}
            | {"calinski_harabasz": st.column_config.NumberColumn(format="%.1f"),
               "inertia": st.column_config.NumberColumn(format="%.1f")})

    sh = cm["split_half"]
    final = sel[(sel.algorithm == "KMeans") & (sel.k == 4)].iloc[0]
    st.write("")
    ui.kpis([("Bootstrap stability", f"{final.bootstrap_ari:.2f}", "mean ARI over 200 resamples", "#0B0D10"),
             ("Split-half agreement", f"{sh['same_cluster_h1_h2']:.0%}", "clubs in the same style both halves", "#0B0D10"),
             ("Silhouette", f"{final.silhouette:.3f}", "K-means, k = 4", "#0B0D10"),
             ("Davies–Bouldin", f"{final.davies_bouldin:.2f}", "lower is better", "#0B0D10")])

    face_validity()

    c1, c2 = st.columns([1.3, 1], gap="medium")
    with c1:
        with ui.panel("Prediction model", f"Trained on matches before {pm['cutoff']}, tested on the final 30% of the season"):
            m = pd.DataFrame(pm["metrics"])
            st.dataframe(m, hide_index=True, placeholder="–", width="stretch", column_config={
                c: st.column_config.NumberColumn(format="%.3f") for c in m.columns if c != "model"})
            ui.note("Target: the match-level Attacking Index (xG, shots, deep completions, box shots, possession), "
                    "not the result.")
    with c2:
        with ui.panel("Limitations and responsible use"):
            st.markdown("""
- **Attacking play only.** Defensive organisation, pressing and individual players are out of scope.
- **Proxies.** Progressive passes, counter-attacks and box touches use the closest free equivalents; through balls
  could not be measured.
- **Small sample.** 60 clubs, one season: clusters describe tendencies on a continuum, not fixed identities.
- **Probabilistic.** Predictions estimate attacking style, not match results, and must not be used for betting.

- **Attribution.** Data from Understat and ESPN (FBref cross-check); crests via ESPN. Non-commercial academic use.
""")
            if data.EXTENSIONS:
                st.markdown(EXTENSION_NOTES)
    ui.footer()


# What the literature reviewed in Chapter 2 leads us to expect of each style (proposal Section 3.12, face validity).
EXPECTED = {
    "Dominant Possession": "Possession-heavy, high-volume attacks: the profile associated with clubs such as Barcelona "
                           "and Manchester City (Gyarmati et al., 2014; Kempe et al., 2014).",
    "Controlled Build-up": "Patient, accurate passing without dominating the ball: an intermediate profile between the "
                           "possession and direct poles (Bekkers & Dabadghao, 2019).",
    "Direct & Cross-Oriented": "Less possession, more long balls and crosses: the direct play described for much of the "
                               "Premier League (Mitrotasios et al., 2019; Sarmento et al., 2013).",
    "Long-Ball Low Block": "The most direct passing and lowest possession: the direct pole of the possession-versus-"
                           "direct continuum (Kempe et al., 2014).",
}


def face_validity() -> None:
    """Cluster membership set against documented reputations and league standing (proposal Section 3.12)."""
    df = data.clubs()
    rows = []
    for cluster in data.CLUSTER_ORDER:
        g = df[df.cluster == cluster].sort_values("PC1", ascending=False)
        rows.append({"Style": cluster, "Clubs": len(g), "Average league finish": g.position.mean(),
                     "Possession %": g.possession.mean(), "Long-ball share %": g.long_ball_share.mean(),
                     "Most typical clubs": ", ".join(g.team.head(6)), "Expected from the literature": EXPECTED[cluster]})
    with ui.panel("Face validity", "Do the clusters match clubs' documented styles? Typical clubs = highest attacking "
                  "dominance (PC1) within the cluster"):
        st.dataframe(pd.DataFrame(rows), hide_index=True, placeholder="–", width="stretch", column_config={
            "Average league finish": st.column_config.NumberColumn(format="%.1f"),
            "Possession %": st.column_config.NumberColumn(format="%.1f"),
            "Long-ball share %": st.column_config.NumberColumn(format="%.1f"),
            "Expected from the literature": st.column_config.TextColumn(width="large")})
        ui.note("The four styles line up with the possession-versus-direct continuum in the literature, and with "
                "league standing: possession-dominant clubs finish highest on average, long-ball sides lowest. "
                "Where the data disagree with expectations (no significant league effect), it is reported as a "
                "finding.")


EXTENSION_NOTES = """
- **Players.** Attacking stats from Understat, tackles won, interceptions and goalkeeping from FBref, line-ups
  from ESPN match sheets; players are matched across sources by club and name (96% FBref, 98% ESPN). Percentiles
  compare players of the same position group with at least 30% of their club's minutes. The probable XI is a
  data-driven guess from recent starts and does not know about injuries or suspensions. Photos are freely licensed
  images from Wikimedia Commons (via Wikidata); players without one are shown with their initials.
- **Honours and managers.** From Wikidata (community-maintained, CC0). Each trophy is counted once per season;
  revoked titles, missing finals and missing manager spells are hand-corrected and listed in `data/reference`.
  League, domestic-cup and European counts match published totals for all 95 checked club counts. Super cups are
  left out because Wikidata records too few of them.
- **Extension sources.** Wikidata (honours, managers, player photos via Wikimedia Commons, CC licences); YouTube
  for highlights.
"""


MATCH_COLUMNS = {"date": "Date", "team": "Club", "opponent": "Opponent", "goals": "Goals", "xg": "xG",
                 "shots": "Shots", "deep_completions": "Deep completions", "box_shots": "Box shots",
                 "possessionPct": "Possession %", "accuratePasses": "Accurate passes", "totalPasses": "Passes",
                 "totalCrosses": "Crosses", "totalLongBalls": "Long balls"}


def data_pipeline() -> None:
    """The data at each step of the pipeline, so a reader can see it was processed and used (stages 2 to 7)."""
    tm = pd.read_csv(data.PROC / "team_match.csv", parse_dates=["date"])
    ts = pd.read_csv(data.PROC / "team_season.csv")
    shots = len(pd.read_csv(data.PROC / "shots.csv", usecols=["team"]))
    cm = data.cluster_model()
    pipe, feats = cm["pipeline"], cm["features"]
    X = ts[feats]
    z = pd.DataFrame(pipe.named_steps["scale"].transform(X), columns=feats)
    pcs = pipe[:-1].transform(X)
    clusters = [cm["names"][int(k)] for k in pipe.predict(X)]
    ident = ts[["team", "league"]].assign(league=ts.league.map(data.LEAGUES)).rename(
        columns={"team": "Club", "league": "League"})

    with ui.panel("From raw data to results", "The actual data at each step of the pipeline, for all 60 clubs of "
                  "2025/26 · every table can be downloaded"):
        ui.kpis([("Matches", f"{tm.game_id.nunique():,}", "380 per league", "#0B0D10"),
                 ("Team-match rows", f"{len(tm):,}", "one per club per match", "#0B0D10"),
                 ("Shots", f"{shots:,}", "with pitch coordinates", "#0B0D10"),
                 ("Clubs × features", f"{len(ts)} × {len(feats)}", "the clustering dataset", "#0B0D10"),
                 ("PCA components", f"{pcs.shape[1]}", f"{cm['explained_variance'].sum():.1%} of the variance", "#0B0D10"),
                 ("Clusters", f"{len(set(clusters))}", "K-means, seed 42", "#0B0D10")])
        t1, t2, t3, t4 = st.tabs(["1 · Match data", "2 · 13 features per club", "3 · Standardised (z-scores)",
                                  "4 · PCA scores and cluster"])
        with t1:
            ui.note("Cleaned match data: Understat and ESPN merged on club and date, one row per club per match. "
                    "The 13 features are aggregated from these rows.")
            sample = tm.sort_values(["date", "team"])[list(MATCH_COLUMNS)].rename(columns=MATCH_COLUMNS)
            st.dataframe(sample, hide_index=True, placeholder="–", width="stretch", height=320,
                         column_config={"Date": st.column_config.DateColumn(format="DD MMM YYYY"),
                                        "xG": st.column_config.NumberColumn(format="%.2f")})
            st.download_button("Download match data (CSV)", tm.to_csv(index=False).encode("utf-8"),
                               "team_match_2025-26.csv", "text/csv", icon=":material/download:")
        with t2:
            ui.note("Per-match averages per club (≈ per 90 minutes); ratios from season totals. This 60 × 13 table is "
                    "the input to the clustering.")
            feat_df = pd.concat([ident, X.rename(columns=data.SHORT_LABELS)], axis=1)
            st.dataframe(feat_df, hide_index=True, placeholder="–", width="stretch", height=320,
                         column_config={c: st.column_config.NumberColumn(format="%.2f")
                                        for c in feat_df.columns if c not in ("Club", "League")})
            st.download_button("Download club features (CSV)", feat_df.to_csv(index=False).encode("utf-8"),
                               "club_features_2025-26.csv", "text/csv", icon=":material/download:")
        with t3:
            ui.note(f"z = (value − mean) ÷ standard deviation, so every feature counts equally in the distances. Check: "
                    f"column means are {z.mean().abs().max():.0e} or less, standard deviations "
                    f"{z.std(ddof=0).min():.2f}–{z.std(ddof=0).max():.2f}.")
            z_df = pd.concat([ident, z.rename(columns=data.SHORT_LABELS)], axis=1)
            st.dataframe(z_df, hide_index=True, placeholder="–", width="stretch", height=320,
                         column_config={c: st.column_config.NumberColumn(format="%+.2f")
                                        for c in z_df.columns if c not in ("Club", "League")})
        with t4:
            ui.note("The standardised features projected onto the 4 retained principal components; K-means assigns "
                    "each club to the nearest of the 4 cluster centres in this space.")
            pc_df = pd.concat([ident, pd.DataFrame(pcs, columns=[f"PC{i + 1}" for i in range(pcs.shape[1])]),
                               pd.DataFrame({"Cluster": clusters})], axis=1)
            st.dataframe(pc_df, hide_index=True, placeholder="–", width="stretch", height=320,
                         column_config={f"PC{i + 1}": st.column_config.NumberColumn(format="%+.2f")
                                        for i in range(pcs.shape[1])})
            st.download_button("Download PCA scores and clusters (CSV)", pc_df.to_csv(index=False).encode("utf-8"),
                               "pca_clusters_2025-26.csv", "text/csv", icon=":material/download:")
        xlsx = data.ROOT / "data" / "FYP_dataset_2025-26.xlsx"
        if xlsx.exists():
            st.download_button("Download the full dataset (Excel, with a data dictionary)", xlsx.read_bytes(),
                               xlsx.name, icon=":material/table_view:")
