import pandas as pd
import streamlit as st

import charts
import data
import ui


def render() -> None:
    df = data.clubs()
    test = data.cluster_model()["league_test"]
    ui.hero("Cross-league comparison", "Do the leagues attack differently?",
            "All three leagues are clustered in one shared feature space, so every club is measured on the same "
            "scale. Here is how the four philosophies are distributed across the Premier League, La Liga and Serie A.")

    share = (df.groupby(["league_name", "cluster"]).size().rename("n").reset_index()
             .assign(share=lambda d: d.n / d.groupby("league_name").n.transform("sum") * 100))
    c1, c2 = st.columns([1.4, 1])
    with c1:
        ui.section("Style mix per league")
        st.plotly_chart(charts.stacked_share(share, "league_name", "cluster", data.CLUSTER_COLORS, data.CLUSTER_ORDER, 380),
                        width="stretch")
    with c2:
        ui.section("Is the difference significant?")
        ui.kpis([("χ² statistic", f"{test['chi2']:.2f}", f"df = {test['dof']}"),
                 ("Permutation p", f"{test['p_permutation']:.2f}", "10,000 permutations"),
                 ("Cramér's V", f"{test['cramers_v']:.2f}", "effect size")])
        verdict = "is" if test["p_permutation"] < 0.05 else "is not"
        ui.callout(f"The association between league and attacking style <b>{verdict} statistically significant</b> "
                   f"at the 5% level. With only 20 clubs per league, {test['share_expected_below_5']:.0%} of expected cell "
                   "counts are below 5, so the permutation test is used. Leagues lean in different directions, but "
                   "every philosophy appears in every league: style varies more <i>within</i> leagues than between them.")

    ui.section("Feature by league")
    feat = st.selectbox("Feature", data.FEATURES, format_func=lambda f: data.SHORT_LABELS[f], index=data.FEATURES.index("xg"))
    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.plotly_chart(charts.league_box(df, feat), width="stretch")
        st.markdown('<div class="note">Each dot is a club, coloured by its attacking philosophy. Hover for names.</div>',
                    unsafe_allow_html=True)
    with c2:
        top = df.sort_values(feat, ascending=False)[["team", "league_name", "cluster", feat]].head(10)
        top[feat] = top[feat].map(lambda v: data.fmt(feat, v))
        st.markdown(f"**Top 10: {data.SHORT_LABELS[feat]}**")
        st.dataframe(top.rename(columns={"team": "Club", "league_name": "League", "cluster": "Style",
                                         feat: data.SHORT_LABELS[feat]}), hide_index=True, width="stretch")

    ui.section("League tables by style")
    tabs = st.tabs(list(data.LEAGUE_FLAGS))
    for tab, league in zip(tabs, data.LEAGUE_FLAGS):
        with tab:
            t = df[df.league_name == league].sort_values("position")
            st.dataframe(pd.DataFrame({
                "Pos": t.position, "Club": t.team, "Style": t.cluster, "Pts": t.Pts, "GF": t.GF, "GA": t.GA,
                "xG/match": t.xg.round(2), "Poss %": t.possession.round(1), "Shots/match": t.shots.round(1),
                "Long-ball %": t.long_ball_share.round(1), "Unique": t.dbscan_outlier.map({True: "★", False: ""})}),
                hide_index=True, width="stretch", height=740)
    ui.footer()
