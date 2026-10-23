import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import charts
import data
import ui

PIPELINE = [
    ("1 · Collect", "Understat (xG, shots, deep completions, attack speed) and ESPN (possession, passing, crosses) "
                    "for all 1,140 matches; FBref as an independent cross-check."),
    ("2 · Engineer", "13 attacking features per club, per match ≈ per 90. Ratios from season totals. Proxies where "
                     "free data has gaps."),
    ("3 · Reduce", "z-score scaling, then PCA. Components with eigenvalue > 1 retained (Kaiser criterion)."),
    ("4 · Cluster", "K-means vs Ward hierarchical vs DBSCAN for k = 2–8, judged by silhouette, Davies–Bouldin, "
                    "Calinski–Harabasz, elbow and bootstrap stability."),
    ("5 · Validate", "Bootstrap stability, split-half (first vs second half of season), face validity, chi-square "
                     "by league with a permutation test."),
    ("6 · Predict", "Logistic regression on pre-match form estimates which club shows the more attacking style; "
                    "temporal hold-out evaluation."),
]

SOURCES = pd.DataFrame([
    ("Possession %", "ESPN", "direct"), ("Ball control", "ESPN", "pass accuracy %"),
    ("Passes per match", "ESPN", "completed passes"), ("Progressive passes", "Understat", "proxy: deep completions"),
    ("Directness", "ESPN", "long-ball share of passes"), ("Crosses", "ESPN", "direct"),
    ("Shots", "Understat", "direct"), ("Shots on target %", "Understat", "direct"),
    ("Expected goals", "Understat", "direct"), ("Goals", "Understat", "direct"), ("Goals per shot", "Understat", "direct"),
    ("Counter-attacks", "Understat", "proxy: shots from fast attacks"),
    ("Touches in box", "Understat", "proxy: share of shots inside the box"),
    ("Through balls", "–", "no free source for 2025/26; excluded"),
], columns=["Proposal variable", "Source", "Measurement"])


def render() -> None:
    cm, pm = data.cluster_model(), data.predict_model()
    sel = data.model_selection()
    ui.hero("Methodology", "How the attacking philosophies were found",
            "A reproducible, CRISP-DM-style pipeline: every number in this dashboard is produced by version-controlled "
            "code from openly available data.")

    cols = st.columns(3)
    for i, (title, text) in enumerate(PIPELINE):
        cols[i % 3].markdown(f'<div class="card" style="margin-bottom:0.8rem"><h4>{title}</h4><p>{text}</p></div>',
                             unsafe_allow_html=True)

    ui.section("Features and data sources")
    st.dataframe(SOURCES, hide_index=True, width="stretch")
    ui.callout("League and season are grouping variables only. They are never clustering inputs, so clubs are grouped by "
               "how they attack rather than where they play.")

    ui.section("Dimensionality reduction")
    c1, c2 = st.columns([1, 1.2])
    with c1:
        ev = cm["explained_variance"]
        fig = go.Figure(go.Bar(x=[f"PC{i + 1}" for i in range(len(ev))], y=ev * 100, marker_color="#38bdf8",
                               text=[f"{v:.1%}" for v in ev], textposition="outside"))
        fig.update_yaxes(title="% variance explained")
        st.plotly_chart(charts._layout(fig, height=320), width="stretch")
        st.markdown(f"**{ev.sum():.1%}** of variance retained in {len(ev)} components.")
    with c2:
        load = cm["loadings"].rename(index=data.SHORT_LABELS)
        fig = go.Figure(go.Heatmap(z=load.values, x=load.columns, y=load.index, colorscale="RdBu", zmid=0,
                                   text=load.round(2).values, texttemplate="%{text}"))
        st.plotly_chart(charts._layout(fig, height=420), width="stretch")
    st.markdown("PC1 **attacking dominance** · PC2 **crossing volume vs finishing efficiency** · "
                "PC3 **box presence** · PC4 **counter-attacking**")

    ui.section("Choosing the number of clusters")
    st.plotly_chart(charts.model_selection_chart(sel, 4), width="stretch")
    st.dataframe(sel.round(3), hide_index=True, width="stretch")
    ui.callout("k = 2 has the highest silhouette but only separates possession-dominant clubs from the rest. Among k ≥ 3, "
               "k = 4 is the most stable under bootstrap resampling and sits at the elbow of the within-cluster sum of "
               "squares. Silhouettes of 0.25–0.40 indicate overlapping styles on a continuum, which is typical of "
               "team-level style data.")

    ui.section("Validation")
    sh = cm["split_half"]
    final = sel[(sel.algorithm == "KMeans") & (sel.k == 4)].iloc[0]
    ui.kpis([("Bootstrap stability", f"{final.bootstrap_ari:.2f}", "mean ARI, 200 resamples"),
             ("Split-half agreement", f"{sh['same_cluster_h1_h2']:.0%}", "clubs in the same cluster H1 vs H2"),
             ("Silhouette", f"{final.silhouette:.3f}", "K-means, k = 4"),
             ("Davies–Bouldin", f"{final.davies_bouldin:.2f}", "lower is better")])

    ui.section("Prediction model")
    m = pd.DataFrame(pm["metrics"])
    st.dataframe(m.round(3), hide_index=True, width="stretch")
    ui.callout(f"Trained on matches before {pm['cutoff']}, tested on the remaining 30% of the season. The target is the "
               "match-level Attacking Index (xG, shots, deep completions, box shots, possession), not the result.")

    ui.section("Limitations and responsible use")
    st.markdown("""
- **Attacking play only.** Defensive organisation, pressing and individual players are outside the scope.
- **Proxies.** Progressive passes, counter-attacks and penalty-box touches are measured through the closest free
  equivalents. Through balls could not be measured for 2025/26.
- **Small sample.** 60 clubs, one season. Clusters describe tendencies on a continuum, not fixed identities.
- **Predictions are probabilistic** estimates of attacking style. They are not match results and must not be used for betting.
- **Attribution.** Data from Understat, ESPN and FBref; club crests via ESPN. Used for non-commercial academic research.
""")
    ui.footer()
