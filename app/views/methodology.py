import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import charts
import data
import ui

PIPELINE = [
    ("01", "Collect", "Understat (xG, shots, deep completions, attack speed) and ESPN (possession, passing, crosses) for "
                      "all 1,140 matches. FBref used as an independent cross-check."),
    ("02", "Engineer", "13 attacking features per club, per match (≈ per 90). Ratios from season totals; documented "
                       "proxies where free data has gaps."),
    ("03", "Reduce", "z-score scaling, then PCA. Components with eigenvalue > 1 retained (Kaiser criterion)."),
    ("04", "Cluster", "K-means vs Ward hierarchical vs DBSCAN for k = 2–8, judged by silhouette, Davies–Bouldin, "
                      "Calinski–Harabasz, elbow and bootstrap stability."),
    ("05", "Validate", "Bootstrap stability, split-half (first vs second half of the season), face validity, and a "
                       "league χ² test with permutation p-value."),
    ("06", "Predict", "Logistic regression on pre-match form estimates which club shows the more attacking style; "
                      "evaluated on a temporal hold-out."),
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
- **Champions League.** ESPN match stats (possession, passing, crosses, shots) from the league phase onwards;
  qualifiers are not included. Understat has no Champions League data, so there is no xG, and comparisons with
  the league use ESPN figures on both sides.
- **Players.** Attacking stats from Understat, tackles won, interceptions and goalkeeping from FBref, line-ups
  from ESPN match sheets; players are matched across sources by club and name (96% FBref, 98% ESPN). Percentiles
  compare players of the same position group with at least 30% of their club's minutes. The probable XI is a
  data-driven guess from recent starts and does not know about injuries or suspensions. Photos are freely licensed
  images from Wikimedia Commons (via Wikidata); players without one are shown with their initials.
- **Honours and managers.** From Wikidata (community-maintained, CC0). Each trophy is counted once per season;
  revoked titles, missing finals and missing manager spells are hand-corrected and listed in `data/reference`.
  League, domestic-cup and European counts match published totals for all 95 checked club counts. Super cups are
  left out because Wikidata records too few of them.
- **Injuries.** Premier League injury, suspension and doubt lists come from the official Fantasy Premier League
  data feed (status, reason, expected return, chance of playing), refreshed every 30 minutes; the probable XI leaves
  out players marked unavailable. La Liga and Serie A have no free equivalent, so their team news comes from match
  sheets.
- **Attribution.** Data from Understat, ESPN, FBref, Wikidata and Fantasy Premier League; crests via ESPN; player photos from Wikimedia Commons (CC licences, credited on Commons). Non-commercial academic use.
""")
    ui.footer()
