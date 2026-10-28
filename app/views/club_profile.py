import html

import pandas as pd
import streamlit as st

import charts
import data
import ui

SPEED_ORDER = ["Fast", "Normal", "Standard", "Slow"]
SITUATION_ORDER = ["OpenPlay", "FromCorner", "SetPiece", "DirectFreekick", "Penalty"]
ZONE_ORDER = ["shotSixYardBox", "shotPenaltyArea", "shotOboxTotal"]
ZONE_NAMES = {"shotSixYardBox": "Six-yard box", "shotPenaltyArea": "Penalty area", "shotOboxTotal": "Outside box"}


def style_fit(silhouette: float) -> str:
    if silhouette >= 0.3:
        return "Clear fit"
    if silhouette >= 0.1:
        return "Typical"
    if silhouette >= 0:
        return "Borderline"
    return "Between styles"


def pick_club(df: pd.DataFrame) -> str:
    teams = data.club_options(df)
    default = st.query_params.get("club", "Manchester United")
    with ui.panel():
        c1, c2 = st.columns([1, 3])
        league = c1.selectbox("League", ["All leagues", *data.LEAGUE_FLAGS])
        pool = teams if league == "All leagues" else df[df.league_name == league].sort_values("team").team.tolist()
        team = c2.selectbox("Club", pool, index=pool.index(default) if default in pool else 0)
    st.query_params["club"] = team
    return team


def render() -> None:
    df = data.clubs()
    ui.page_header("Club profile", "Season attacking report",
                   "How a club attacked across the 2025/26 season: its style, fingerprint, chance creation, shot "
                   "locations and closest stylistic peers in all three leagues.")
    team = pick_club(df)
    row = df.set_index("team").loc[team]
    ui.club_header(df[df.team == team].iloc[0])

    league_df = df[df.league_name == row.league_name]
    accent = row.color
    ui.kpis([
        ("xG per match", f"{row.xg:.2f}", f"#{row.xg_lrank} of 20 in {row.league_name}", accent),
        ("Goals per match", f"{row.goals:.2f}", f"#{row.goals_lrank} of 20 in {row.league_name}", accent),
        ("Possession", f"{row.possession:.1f}%", f"#{row.possession_lrank} of 20 in {row.league_name}", accent),
        ("Shots per match", f"{row.shots:.1f}", f"#{row.shots_lrank} of 20 in {row.league_name}", accent),
        ("Long-ball share", f"{row.long_ball_share:.1f}%", f"#{row.long_ball_share_lrank} most direct of 20", accent),
        ("Style fit", style_fit(row.silhouette), f"silhouette {row.silhouette:.2f}", data.CLUSTER_COLORS[row.cluster]),
    ])

    c1, c2 = st.columns([1.1, 1], gap="medium")
    with c1:
        with ui.panel("Attacking fingerprint", "Percentile among all 60 clubs (100 = highest in the three leagues)"):
            cluster_avg = df[df.cluster == row.cluster][[f"{f}_pct" for f in data.FEATURES]].mean().to_numpy()
            st.plotly_chart(charts.radar([
                {"name": team, "values": [row[f"{f}_pct"] for f in data.FEATURES], "color": row.color},
                {"name": f"{row.cluster} average", "values": cluster_avg, "color": data.CLUSTER_COLORS[row.cluster],
                 "fill": False, "dash": "dot"},
            ], height=420), width="stretch")
    with c2:
        with ui.panel("Attacking identity", "What sets this club apart from the other 59"):
            cm = data.cluster_model()
            ui.callout(f"{ui.cluster_badge(row.cluster)}<div style='margin-top:0.5rem'>{cm['blurbs'][row.cluster]}</div>")
            z = ((row[data.FEATURES] - df[data.FEATURES].mean()) / df[data.FEATURES].std()).astype(float).sort_values()
            picks = list(z.index[::-1][:3]) + list(z.index[:2])
            ui.traits([(data.SHORT_LABELS[f], f"{data.fmt(f, row[f])} · #{row[f + '_lrank']} of 20 in {row.league_name}",
                        z[f]) for f in picks])
            if row.cluster_h1 != row.cluster_h2:
                ui.callout(f"Style shift during the season: <b>{row.cluster_h1}</b> in matchweeks 1–19, "
                           f"<b>{row.cluster_h2}</b> in matchweeks 20–38.", warn=True)
            else:
                ui.note(f"Consistent all season: {row.cluster_h1} in both halves.")

    tm = data.team_matches()
    club_tm = tm[tm.team == team]
    st.write("")
    tabs = st.tabs([":material/timeline: Season timeline", ":material/sports_soccer: Shot map",
                    ":material/bolt: How they attack", ":material/splitscreen: First vs second half",
                    ":material/hub: Similar clubs"])

    with tabs[0]:
        with ui.panel("Match Attacking Index", "Within-league z-score of xG, shots, deep completions, box shots and "
                      "possession · bars coloured by result · dashed line marks mid-season"):
            st.plotly_chart(charts.timeline(club_tm, row.color), width="stretch")
        with ui.panel("Chance creation vs concession", "Five-match rolling average"):
            st.plotly_chart(charts.xg_flow(club_tm, row.color), width="stretch")

    with tabs[1]:
        s = data.shots()
        s = s[s.team == team]
        with ui.panel():
            all_sit = sorted(s.situation.dropna().unique())
            situations = st.pills("Situation", all_sit, selection_mode="multi", default=all_sit) or all_sit
            c2, c3 = st.columns([1, 2])
            venue = c2.segmented_control("Venue", ["All", "Home", "Away"], default="All") or "All"
            mw = c3.slider("Matchweeks", 1, 38, (1, 38))
        f = s[s.situation.isin(situations) & s.matchweek.between(*mw)]
        if venue != "All":
            f = f[f.is_home == (venue == "Home")]
        ui.kpis([("Shots", f"{len(f)}", "in selection", row.color),
                 ("Goals", f"{int((f.result == 'Goal').sum())}", "own goals excluded", row.color),
                 ("Shot xG", f"{f.xg.sum():.1f}", "sum of individual shots", row.color),
                 ("xG per shot", f"{f.xg.mean():.3f}" if len(f) else "–", "average chance quality", row.color),
                 ("In the box", f"{f.in_box.mean():.0%}" if len(f) else "–",
                  f"all-club average {df.box_shot_share.mean():.0f}%", row.color)])
        c1, c2 = st.columns([1.35, 1], gap="medium")
        with c1:
            with ui.panel("Shot map", "Marker size = xG · gold stars are goals"):
                st.plotly_chart(charts.shot_map(f, row.color), width="stretch")
                ui.note("Shot data: Understat. Shot xG is the sum of individual shots. Match and season xG elsewhere use "
                        "Understat's match figure, which counts a rebound sequence as one chance (at most 1.0 xG), so "
                        "it can be slightly lower.")
        with c2:
            with ui.panel("Top shooters", "For the current selection"):
                if len(f):
                    top = (f.groupby("player").agg(Shots=("xg", "size"), Goals=("result", lambda r: (r == "Goal").sum()),
                                                   xG=("xg", "sum")).sort_values("xG", ascending=False).head(10)
                           .reset_index().rename(columns={"player": "Player"}))
                    top["G − xG"] = top.Goals - top.xG
                    st.dataframe(top, hide_index=True, width="stretch", height=410, column_config={
                        "xG": st.column_config.ProgressColumn("xG", format="%.1f", min_value=0,
                                                              max_value=float(top.xG.max())),
                        "G − xG": st.column_config.NumberColumn(format="%+.1f")})
                else:
                    ui.note("No shots match the current filters.")

    with tabs[2]:
        br = data.breakdowns()
        br = br[br.team == team]
        c1, c2, c3 = st.columns(3, gap="small")
        fast_rank = int(df.fast_attack_shots.rank(ascending=False, method="min")[df.team == team].iloc[0])
        with c1:
            with ui.panel("Attack speed", f"Fast attacks ≈ counter-attacks · #{fast_rank} of 60 for fast-attack shots"):
                st.plotly_chart(charts.breakdown_bars(br[br.block == "attackSpeed"], SPEED_ORDER, row.color), width="stretch")
        with c2:
            with ui.panel("Shot situation", "Where the chances came from"):
                sit = br[br.block == "situation"]
                st.plotly_chart(charts.breakdown_bars(sit, [c for c in SITUATION_ORDER if c in set(sit.category)], row.color),
                                width="stretch")
        with c3:
            with ui.panel("Shot zone", "Distance of attempts from goal"):
                zone = br[(br.block == "shotZone") & br.category.isin(ZONE_ORDER)].assign(
                    category=lambda d: d.category.map(ZONE_NAMES))
                st.plotly_chart(charts.breakdown_bars(zone, [ZONE_NAMES[z] for z in ZONE_ORDER], row.color), width="stretch")
        with ui.panel("Feature comparison", f"{team} against its league and its style group"):
            comp = pd.DataFrame({
                "Metric": [data.SHORT_LABELS[f] for f in data.FEATURES],
                team: [data.fmt(f, row[f]) for f in data.FEATURES],
                f"{row.league_name} avg": [data.fmt(f, league_df[f].mean()) for f in data.FEATURES],
                f"{row.cluster} avg": [data.fmt(f, df[df.cluster == row.cluster][f].mean()) for f in data.FEATURES],
                "League rank": [row[f + "_lrank"] for f in data.FEATURES],
                "Percentile (all 60)": [row[f + "_pct"] for f in data.FEATURES],
            })
            st.dataframe(comp, hide_index=True, width="stretch", column_config={
                "League rank": st.column_config.NumberColumn(format="#%d"),
                "Percentile (all 60)": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100)})

    with tabs[3]:
        h = data.halves()
        h = h[h.team == team].set_index("half")
        feats = [f for f in data.FEATURES if f in h.columns]
        c1, c2 = st.columns([1.1, 1], gap="medium")
        with c1:
            with ui.panel("First half vs second half", "Percentiles among all 60 clubs in the same half · counter-attacks "
                          "are season-level only (shown at 50)"):
                all_h = data.halves()
                pct = {half: [data.percent_rank(all_h[all_h.half == half][f], h.loc[half, f]) if f in feats else 50
                              for f in data.FEATURES] for half in ("H1", "H2")}
                st.plotly_chart(charts.radar([
                    {"name": "Matchweeks 1–19", "values": pct["H1"], "color": "#94A3B8", "fill": False},
                    {"name": "Matchweeks 20–38", "values": pct["H2"], "color": row.color}], height=420), width="stretch")
        with c2:
            with ui.panel("Change by metric", f"Style: {row.cluster_h1} → {row.cluster_h2}"):
                tbl = pd.DataFrame({"Metric": [data.SHORT_LABELS[f] for f in feats],
                                    "MW 1–19": [data.fmt(f, h.loc["H1", f]) for f in feats],
                                    "MW 20–38": [data.fmt(f, h.loc["H2", f]) for f in feats],
                                    "Change": [h.loc["H2", f] - h.loc["H1", f] for f in feats]})
                st.dataframe(tbl, hide_index=True, width="stretch", height=455,
                             column_config={"Change": st.column_config.NumberColumn(format="%+.2f")})

    with tabs[4]:
        sim = data.similar()
        sim = sim[sim.team == team].merge(df[["team", "cluster", "logo", "color"]], left_on="similar_team", right_on="team",
                                          suffixes=("", "_s"))
        ui.note("Closest attacking profiles across all three leagues, by distance on the 13 standardised features. "
                "Useful for scouting comparable systems or likely-compatible opponents.")
        st.write("")
        cols = st.columns(5, gap="small")
        for col, r in zip(cols, sim.itertuples()):
            col.markdown(f'''<div class="card vs-card"><img src="{r.logo}">
                <h4 style="font-size:0.95rem">{html.escape(r.similar_team)}</h4>
                <div class="note" style="margin-bottom:0.4rem">{data.LEAGUES[r.similar_league]}</div>
                <div style="font-size:1.6rem;font-weight:800;color:var(--text-strong)">{r.similarity:.0f}<span class="note"> / 100</span></div>
                <div style="margin-top:0.4rem">{ui.cluster_badge(r.cluster)}</div></div>''', unsafe_allow_html=True)
        st.write("")
        with ui.panel("Fingerprint overlay"):
            pick = st.selectbox("Compare with", sim.similar_team.tolist())
            other = df.set_index("team").loc[pick]
            st.plotly_chart(charts.radar([
                {"name": team, "values": [row[f"{f}_pct"] for f in data.FEATURES], "color": row.color},
                {"name": pick, "values": [other[f"{f}_pct"] for f in data.FEATURES], "color": "#E2E8F0", "fill": False}],
                height=420), width="stretch")
    ui.footer()
