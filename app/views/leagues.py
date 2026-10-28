import pandas as pd
import streamlit as st

import charts
import data
import ui


def render() -> None:
    df = data.clubs()
    test = data.cluster_model()["league_test"]
    ui.page_header("League comparison", "Do the leagues attack differently?",
                   "All three leagues are clustered in one shared feature space, so every club is measured on the same "
                   "scale. This page shows how the four philosophies are distributed across the leagues.")

    share = (df.groupby(["league_name", "cluster"]).size().rename("n").reset_index()
             .assign(share=lambda d: d.n / d.groupby("league_name").n.transform("sum") * 100))
    verdict = "is" if test["p_permutation"] < 0.05 else "is not"
    ui.kpis([("χ² statistic", f"{test['chi2']:.2f}", f"{test['dof']} degrees of freedom", "#38BDF8"),
             ("Permutation p-value", f"{test['p_permutation']:.2f}", "10,000 permutations", "#6366F1"),
             ("Cramér's V", f"{test['cramers_v']:.2f}", "effect size (0 none, 1 perfect)", "#A78BFA"),
             ("Result", "Not significant" if verdict == "is not" else "Significant", "at the 5% level", "#F59E0B")])

    c1, c2 = st.columns([1.4, 1], gap="medium")
    with c1:
        with ui.panel("Style mix per league", "Share of each league's 20 clubs in each attacking philosophy"):
            st.plotly_chart(charts.stacked_share(share, "league_name", "cluster", data.CLUSTER_COLORS,
                                                 data.CLUSTER_ORDER, 400), width="stretch")
    with c2:
        with ui.panel("Interpretation"):
            ui.callout(f"The association between league and attacking style <b>{verdict} statistically significant</b>. "
                       f"With 20 clubs per league, {test['share_expected_below_5']:.0%} of expected cell counts are below "
                       "5, so a permutation test is used instead of the asymptotic χ² p-value.")
            ui.note("The leagues lean in different directions: the Premier League towards direct, cross-oriented "
                    "attacking, Serie A towards long-ball low blocks, and La Liga towards controlled build-up. But every "
                    "philosophy appears in every league, and style varies more <i>within</i> leagues than between them.")
            st.write("")
            xt = share.pivot(index="cluster", columns="league_name", values="n").reindex(data.CLUSTER_ORDER).fillna(0)
            st.dataframe(xt.astype(int).reset_index().rename(columns={"cluster": "Style"}), hide_index=True,
                         width="stretch")

    with ui.panel("Feature by league", "Each dot is a club, coloured by its attacking philosophy · hover for names"):
        feat = st.selectbox("Feature", data.FEATURES, format_func=lambda f: data.SHORT_LABELS[f],
                            index=data.FEATURES.index("xg"))
        c1, c2 = st.columns([1.4, 1], gap="medium")
        with c1:
            st.plotly_chart(charts.league_box(df, feat), width="stretch")
        with c2:
            top = df.sort_values(feat, ascending=False).head(10)
            st.dataframe(pd.DataFrame({"": top.logo, "Club": top.team, "League": top.league_name,
                                       data.SHORT_LABELS[feat]: top[feat]}), hide_index=True, width="stretch",
                         height=388, column_config={
                             "": st.column_config.ImageColumn(width="small"),
                             data.SHORT_LABELS[feat]: st.column_config.ProgressColumn(
                                 format="%.2f", min_value=0, max_value=float(df[feat].max()))})

    with ui.panel("League tables by style"):
        tabs = st.tabs(list(data.LEAGUE_FLAGS))
        for tab, league in zip(tabs, data.LEAGUE_FLAGS):
            with tab:
                t = df[df.league_name == league].sort_values("position")
                st.dataframe(pd.DataFrame({
                    "Pos": t.position, "": t.logo, "Club": t.team, "Style": t.cluster, "Pts": t.Pts,
                    "GF": t.GF, "GA": t.GA, "xG / match": t.xg, "Possession": t.possession / 100,
                    "Shots / match": t.shots, "Long-ball share": t.long_ball_share / 100,
                    "Unique": t.dbscan_outlier.map({True: "★", False: ""})}),
                    hide_index=True, width="stretch", height=738, column_config={
                        "": st.column_config.ImageColumn(width="small"),
                        "xG / match": st.column_config.ProgressColumn(format="%.2f", min_value=0,
                                                                      max_value=float(df.xg.max())),
                        "Possession": st.column_config.NumberColumn(format="percent"),
                        "Shots / match": st.column_config.NumberColumn(format="%.1f"),
                        "Long-ball share": st.column_config.NumberColumn(format="percent")})
    ui.footer()
