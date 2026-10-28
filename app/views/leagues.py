import html

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
    ui.kpis([("χ² statistic", f"{test['chi2']:.2f}", f"{test['dof']} degrees of freedom", "#0B0D10"),
             ("Permutation p-value", f"{test['p_permutation']:.2f}", "10,000 permutations", "#0B0D10"),
             ("Cramér's V", f"{test['cramers_v']:.2f}", "effect size (0 none, 1 perfect)", "#0B0D10"),
             ("Result", "Not significant" if verdict == "is not" else "Significant", "at the 5% level", "#D50000")])

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

    hist = data.history()
    hist = hist[hist.cluster.notna()]
    with ui.panel("Style mix: last season vs this season", "Share of each league's clubs in each philosophy · "
                  f"{data.season_label(hist.season.max())} is in progress and uses the 2025/26 model"):
        tabs = st.tabs(list(data.LEAGUE_FLAGS))
        for tab, league in zip(tabs, data.LEAGUE_FLAGS):
            with tab:
                st.plotly_chart(charts.league_style_trend(hist, league), width="stretch", key=f"trend-{league}")
        dom = (hist.assign(dom=hist.cluster == "Dominant Possession").groupby(["league_name", "season_label"]).dom.mean()
               .unstack(0) * 100)
        if len(dom) > 1:
            first, last = dom.iloc[0], dom.iloc[-1]
            ui.note("Share of clubs playing Dominant Possession, 2025/26 vs 2026/27 so far: " + " · ".join(
                f"{lg} {first[lg]:.0f}% → {last[lg]:.0f}%" for lg in dom.columns))

    europe(hist)

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


STAGE_ORDER = ["League phase", "Knockout play-off", "Round of 16", "Quarter-final", "Semi-final", "Final", "Winner"]


def europe(hist: pd.DataFrame) -> None:
    """How each league's clubs, and each attacking style, fared in the Champions League."""
    s = data.ucl_seasons()
    ours = s[s.ours].merge(hist[["season", "team", "PC1"]], on=["season", "team"], how="left")
    seasons = sorted(ours.season.unique(), reverse=True)
    done = [x for x in seasons if s[s.season == x].champion.any()]
    ui.section("In the Champions League")
    pick = st.segmented_control("UCL season", seasons, default=done[0] if done else seasons[0],
                                format_func=data.season_label, key="ucl_season_leagues",
                                label_visibility="collapsed") or seasons[0]
    o = ours[ours.season == pick]
    champ = s[(s.season == pick) & s.champion].team.tolist()
    c1, c2 = st.columns([1.4, 1], gap="medium")
    with c1:
        with ui.panel("Does domestic dominance carry into Europe?",
                      f"{data.season_label(pick)} · each dot is one of our clubs, coloured by its league style"):
            st.plotly_chart(charts.europe_vs_dominance(o.dropna(subset=["PC1"])), width="stretch",
                            key=f"europe-{pick}")
            r = o[["PC1", "points_per_match"]].corr().iloc[0, 1] if len(o) > 2 else float("nan")
            ui.note(f"Correlation between league attacking dominance and Champions League points per match: "
                    f"r = {r:.2f} across {len(o)} clubs. "
                    + ("Season in progress: few matches per club so far. " if not champ else "")
                    + "A small sample with different opponents, so this is descriptive, not a tested effect.")
    with c2:
        with ui.panel("By league", "Our clubs only" + (f" · winner: {html.escape(champ[0])}" if champ else "")):
            best = o.assign(stage_rank=o.stage_name.map(STAGE_ORDER.index))
            tbl = (best.groupby("league_name").agg(Clubs=("team", "size"), Played=("played", "sum"),
                                                   W=("wins", "sum"), D=("draws", "sum"), L=("losses", "sum"),
                                                   **{"Pts / match": ("points_per_match", "mean")},
                                                   stage_rank=("stage_rank", "max"))
                   .reset_index().rename(columns={"league_name": "League"}))
            tbl["Furthest"] = tbl.pop("stage_rank").map(dict(enumerate(STAGE_ORDER)))
            st.dataframe(tbl, hide_index=True, width="stretch", column_config={
                "Pts / match": st.column_config.NumberColumn(format="%.2f")})
        with ui.panel("By attacking style", "Same clubs, grouped by their league style that season"):
            v = data.ucl_vs_league()
            poss = v[(v.season == pick) & (v.stat == "possession")].set_index("team")["diff"]
            st_tbl = (o.assign(poss_change=o.team.map(poss)).groupby("cluster")
                      .agg(Clubs=("team", "size"), **{"Pts / match": ("points_per_match", "mean")},
                           **{"Possession vs league": ("poss_change", "mean")})
                      .reindex([c for c in data.CLUSTER_ORDER if c in set(o.cluster)]).reset_index()
                      .rename(columns={"cluster": "Style"}))
            st.dataframe(st_tbl, hide_index=True, width="stretch", column_config={
                "Pts / match": st.column_config.NumberColumn(format="%.2f"),
                "Possession vs league": st.column_config.NumberColumn(format="%+.1f pp")})
            ui.note("Possession vs league: percentage-point change from the same club's league average that season.")
