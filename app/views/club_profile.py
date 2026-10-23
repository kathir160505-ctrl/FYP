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


def pick_club(df: pd.DataFrame) -> str:
    teams = data.club_options(df)
    default = st.query_params.get("club", "Manchester United")
    c1, c2 = st.columns([1, 3])
    league = c1.selectbox("League", ["All leagues", *data.LEAGUE_FLAGS])
    pool = teams if league == "All leagues" else df[df.league_name == league].sort_values("team").team.tolist()
    team = c2.selectbox("Club", pool, index=pool.index(default) if default in pool else 0)
    st.query_params["club"] = team
    return team


def render() -> None:
    df = data.clubs()
    team = pick_club(df)
    row = df.set_index("team").loc[team]
    row_t = df[df.team == team].iloc[0]
    ui.club_header(row_t)

    league_df = df[df.league_name == row.league_name]
    ui.kpis([
        ("xG per match", f"{row.xg:.2f}", f"#{row.xg_lrank} in {row.league_name}"),
        ("Goals per match", f"{row.goals:.2f}", f"#{row.goals_lrank} in {row.league_name}"),
        ("Possession", f"{row.possession:.1f}%", f"#{row.possession_lrank} in {row.league_name}"),
        ("Shots per match", f"{row.shots:.1f}", f"#{row.shots_lrank} in {row.league_name}"),
        ("Long-ball share", f"{row.long_ball_share:.1f}%", f"#{row.long_ball_share_lrank} most direct"),
        ("Style fit", f"{row.silhouette:.2f}", "silhouette: how typical of its cluster"),
    ])

    c1, c2 = st.columns([1.05, 1])
    with c1:
        ui.section("Attacking fingerprint")
        cluster_avg = df[df.cluster == row.cluster][[f"{f}_pct" for f in data.FEATURES]].mean().to_numpy()
        st.plotly_chart(charts.radar([
            {"name": team, "values": [row[f"{f}_pct"] for f in data.FEATURES], "color": row.color},
            {"name": f"{row.cluster} average", "values": cluster_avg, "color": data.CLUSTER_COLORS[row.cluster],
             "fill": False, "dash": "dot"},
        ]), width="stretch")
        st.markdown('<div class="note">Percentile among all 60 clubs. 100 = highest in the three leagues.</div>',
                    unsafe_allow_html=True)
    with c2:
        ui.section("Why this style?")
        cm = data.cluster_model()
        ui.callout(f"<b>{row.cluster}</b>: {cm['blurbs'][row.cluster]}")
        z = (row[data.FEATURES] - df[data.FEATURES].mean()) / df[data.FEATURES].std()
        z = z.astype(float).sort_values()
        st.markdown("**Most distinctive traits** (vs all 60 clubs)")
        for f in list(z.index[::-1][:3]) + list(z.index[:2]):
            arrow, col = ("▲", "#22c55e") if z[f] > 0 else ("▼", "#f87171")
            st.markdown(f'<span style="color:{col};font-weight:700">{arrow} {data.SHORT_LABELS[f]}</span> '
                        f'<span class="note">{data.fmt(f, row[f])} · {z[f]:+.1f} SD · '
                        f'#{row[f + "_lrank"]} of 20 in {row.league_name}</span>', unsafe_allow_html=True)
        if row.cluster_h1 != row.cluster_h2:
            ui.callout(f"Style shift during the season: <b>{row.cluster_h1}</b> in the first half → "
                       f"<b>{row.cluster_h2}</b> in the second half.", warn=True)
        else:
            st.markdown(f'<div class="note" style="margin-top:0.6rem">Consistent all season: {row.cluster_h1} '
                        "in both halves.</div>", unsafe_allow_html=True)

    tm = data.team_matches()
    club_tm = tm[tm.team == team]
    tabs = st.tabs(["📈 Season timeline", "🎯 Shot map", "⚡ How they attack", "🔁 First vs second half", "🧭 Similar clubs"])

    with tabs[0]:
        st.plotly_chart(charts.timeline(club_tm, row.color), width="stretch")
        st.markdown('<div class="note">Match Attacking Index = average within-league z-score of xG, shots, deep '
                    "completions, box shots and possession. Bars are coloured by result (green W, grey D, red L). "
                    "Dashed line marks the mid-season split.</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.xg_flow(club_tm, row.color), width="stretch")

    with tabs[1]:
        s = data.shots()
        s = s[s.team == team]
        all_sit = sorted(s.situation.dropna().unique())
        situations = st.pills("Situation", all_sit, selection_mode="multi", default=all_sit) or all_sit
        c2, c3 = st.columns([1, 2])
        venue = c2.radio("Venue", ["All", "Home", "Away"], horizontal=True)
        mw = c3.slider("Matchweeks", 1, 38, (1, 38))
        f = s[s.situation.isin(situations) & s.matchweek.between(*mw)]
        if venue != "All":
            f = f[f.is_home == (venue == "Home")]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Shots", len(f))
        m2.metric("Goals", int((f.result == "Goal").sum()))
        m3.metric("xG", f"{f.xg.sum():.1f}")
        m4.metric("xG per shot", f"{f.xg.mean():.3f}" if len(f) else "–")
        c1, c2 = st.columns([1.35, 1])
        with c1:
            st.plotly_chart(charts.shot_map(f, row.color), width="stretch")
            st.markdown('<div class="note">Marker size = xG. Gold stars are goals. Own goals excluded. '
                        "Shot data: Understat.</div>", unsafe_allow_html=True)
        with c2:
            st.markdown("**Top shooters** (selection above)")
            if len(f):
                top = (f.groupby("player").agg(Shots=("xg", "size"), Goals=("result", lambda r: (r == "Goal").sum()),
                                               xG=("xg", "sum")).sort_values("xG", ascending=False).head(10))
                top["Goals − xG"] = top.Goals - top.xG
                st.dataframe(top.round(2), width="stretch", height=390)
            in_box = f.in_box.mean() if len(f) else 0
            st.markdown(f'<div class="note">{in_box:.0%} of these shots came from inside the penalty area '
                        f'(all-club average {data.clubs().box_shot_share.mean():.0f}%).</div>', unsafe_allow_html=True)

    with tabs[2]:
        br = data.breakdowns()
        br = br[br.team == team]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Attack speed** (Understat)")
            st.plotly_chart(charts.breakdown_bars(br[br.block == "attackSpeed"], SPEED_ORDER, row.color), width="stretch")
            fast_rank = int(df.fast_attack_shots.rank(ascending=False, method="min")[df.team == team].iloc[0])
            st.markdown(f'<div class="note">Fast attacks ≈ counter-attacks: {row.fast_attack_shots:.2f} shots per match, '
                        f"#{fast_rank} of 60.</div>", unsafe_allow_html=True)
        with c2:
            st.markdown("**Shot situation**")
            sit = br[br.block == "situation"]
            st.plotly_chart(charts.breakdown_bars(sit, [c for c in SITUATION_ORDER if c in set(sit.category)], row.color),
                            width="stretch")
        with c3:
            st.markdown("**Shot zone**")
            zone = br[(br.block == "shotZone") & br.category.isin(ZONE_ORDER)].assign(category=lambda d: d.category.map(ZONE_NAMES))
            st.plotly_chart(charts.breakdown_bars(zone, [ZONE_NAMES[z] for z in ZONE_ORDER], row.color), width="stretch")
        comp = pd.DataFrame({
            "Metric": [data.SHORT_LABELS[f] for f in data.FEATURES],
            team: [data.fmt(f, row[f]) for f in data.FEATURES],
            f"{row.league_name} avg": [data.fmt(f, league_df[f].mean()) for f in data.FEATURES],
            f"{row.cluster} avg": [data.fmt(f, df[df.cluster == row.cluster][f].mean()) for f in data.FEATURES],
            "League rank": [f"#{row[f + '_lrank']}" for f in data.FEATURES],
        })
        st.dataframe(comp, hide_index=True, width="stretch")

    with tabs[3]:
        h = data.halves()
        h = h[h.team == team].set_index("half")
        feats = [f for f in data.FEATURES if f in h.columns]
        c1, c2 = st.columns([1.2, 1])
        with c1:
            all_h = data.halves()
            pct = {half: [data.percent_rank(all_h[all_h.half == half][f], h.loc[half, f]) if f in feats else 50
                          for f in data.FEATURES] for half in ("H1", "H2")}
            fig = charts.radar([{"name": "First half (MW 1–19)", "values": pct["H1"], "color": "#94a3b8", "fill": False},
                                {"name": "Second half (MW 20–38)", "values": pct["H2"], "color": row.color}])
            st.plotly_chart(fig, width="stretch")
            st.markdown('<div class="note">Percentiles among all 60 clubs in the same half. Counter-attacks are '
                        "season-level only (shown at 50).</div>", unsafe_allow_html=True)
        with c2:
            tbl = pd.DataFrame({"Metric": [data.SHORT_LABELS[f] for f in feats],
                                "First half": [data.fmt(f, h.loc["H1", f]) for f in feats],
                                "Second half": [data.fmt(f, h.loc["H2", f]) for f in feats],
                                "Change": [f"{h.loc['H2', f] - h.loc['H1', f]:+.2f}" for f in feats]})
            st.dataframe(tbl, hide_index=True, width="stretch", height=460)
            st.markdown(f"Cluster: **{row.cluster_h1}** → **{row.cluster_h2}**")

    with tabs[4]:
        sim = data.similar()
        sim = sim[sim.team == team].merge(df[["team", "cluster", "logo", "color"]], left_on="similar_team", right_on="team",
                                          suffixes=("", "_s"))
        st.markdown("Closest attacking profiles across **all three leagues**: useful for scouting comparable "
                    "systems or likely-compatible opponents.")
        cols = st.columns(5)
        for col, r in zip(cols, sim.itertuples()):
            col.markdown(f'''<div class="card" style="text-align:center"><img src="{r.logo}" width="46">
                <h4 style="margin-top:0.4rem;font-size:0.95rem">{html.escape(r.similar_team)}</h4>
                <div class="note">{data.LEAGUES[r.similar_league]}</div>
                <div style="font-size:1.5rem;font-weight:800;color:{data.CLUSTER_COLORS[r.cluster]}">{r.similarity:.0f}</div>
                <div class="note">similarity / 100</div>{ui.cluster_badge(r.cluster)}</div>''', unsafe_allow_html=True)
        pick = st.selectbox("Overlay a similar club", sim.similar_team.tolist())
        other = df.set_index("team").loc[pick]
        st.plotly_chart(charts.radar([
            {"name": team, "values": [row[f"{f}_pct"] for f in data.FEATURES], "color": row.color},
            {"name": pick, "values": [other[f"{f}_pct"] for f in data.FEATURES], "color": "#e2e8f0", "fill": False}]),
            width="stretch")
    ui.footer()
