import html

import pandas as pd
import streamlit as st

import charts
import data
import live
import ui


def _side(col, row, label: str) -> None:
    col.markdown(f'''<div class="card vs-card" style="border-top:3px solid {row.color};height:100%">
        <div class="note" style="text-transform:uppercase;letter-spacing:0.08em;font-weight:600">{label}</div>
        <img src="{row.logo}"><h4 style="font-size:1.2rem">{html.escape(row.team)}</h4>
        <div class="note" style="margin-bottom:0.6rem">{row.league_name} · {ui.ordinal(row.position)} · {row.Pts} pts</div>
        {ui.cluster_badge(row.cluster)}</div>''', unsafe_allow_html=True)


def _distinct(c1: str, c2: str) -> bool:
    rgb = lambda c: [int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]  # noqa: E731
    return sum((x - y) ** 2 for x, y in zip(rgb(c1), rgb(c2))) ** 0.5 > 110


def render() -> None:
    df = data.clubs()
    ui.page_header("Head-to-head", "Which side attacks more?",
                   "Compare any two clubs, including across leagues, and estimate which is more likely to show the "
                   "more attacking style when they meet. This is a style estimate, not a result prediction.")
    teams = data.club_options(df)
    default_a = st.query_params.get("a", "Manchester United")
    with ui.panel():
        c1, c2, c3 = st.columns([2, 2, 1.6])
        a = c1.selectbox("Club A", teams, index=teams.index(default_a) if default_a in teams else 0)
        others = [t for t in teams if t != a]
        b = c2.selectbox("Club B", others, index=others.index("Liverpool") if "Liverpool" in others else 0)
        venue_label = c3.segmented_control("Venue", ["A home", "B home", "Neutral"], default="A home") or "A home"
    venue = {"A home": "A", "B home": "B", "Neutral": "N"}[venue_label]
    venue_text = {"A": f"{a} at home", "B": f"{b} at home", "N": "neutral venue"}[venue]
    st.query_params["a"] = a

    ra, rb = df.set_index("team").loc[a], df.set_index("team").loc[b]
    color_b = rb.color if _distinct(ra.color, rb.color) else "#111418"

    left, mid, right = st.columns([1, 1.7, 1], gap="medium")
    _side(left, df[df.team == a].iloc[0], "Club A")
    _side(right, df[df.team == b].iloc[0], "Club B")
    with mid:
        with ui.panel():
            pred = data.predict_more_attacking(a, b, venue)
            p = pred["prob"]
            fav, fav_p = (a, p) if p >= 0.5 else (b, 1 - p)
            strength = "Strong" if fav_p >= 0.70 else "Moderate" if fav_p >= 0.58 else "Slight"
            st.markdown(f'<div class="prob-head"><div class="k">More attacking style · {venue_text}</div>'
                        f'<div class="v">{html.escape(fav)} {fav_p:.0%}</div>'
                        f'<div class="note">{strength} edge</div></div>', unsafe_allow_html=True)
            st.plotly_chart(charts.gauge_bar(p, ra.abbr, rb.abbr, ra.color, color_b), width="stretch",
                            config={"displayModeBar": False})
            st.markdown('<div class="panel-sub" style="margin-top:0.2rem">What drives the estimate</div>',
                        unsafe_allow_html=True)
            st.plotly_chart(charts.contributions(pred["themes"], ra.abbr, rb.abbr, ra.color, color_b), width="stretch",
                            config={"displayModeBar": False})

    if ra.league_name != rb.league_name:
        ui.callout("Cross-league comparison: the model was trained on league matches and its inputs are standardised "
                   "within each league, so this compares each club's attacking dominance <i>within its own league</i>. "
                   "It is not a forecast of a real fixture.", warn=True)
    ui.callout("Logistic regression (AUC 0.81 on held-out matches) using each club's season-long and last-five-match "
               "attacking profile plus venue. It estimates attacking style only and does <b>not</b> predict the winner "
               "or the score.")

    c1, c2 = st.columns([1, 1.1], gap="medium")
    with c1:
        with ui.panel("Attacking fingerprints", "Percentile among all 60 clubs"):
            st.plotly_chart(charts.radar([
                {"name": a, "values": [ra[f"{f}_pct"] for f in data.FEATURES], "color": ra.color},
                {"name": b, "values": [rb[f"{f}_pct"] for f in data.FEATURES], "color": color_b}], height=440),
                width="stretch")
    with c2:
        with ui.panel("Stat by stat", "Percentile bars · hover for the raw value"):
            st.plotly_chart(charts.diverging_bars(
                pd.Series({f: ra[f"{f}_pct"] for f in data.FEATURES}), pd.Series({f: rb[f"{f}_pct"] for f in data.FEATURES}),
                a, b, ra.color, color_b, ra, rb), width="stretch")

    tm = data.team_matches()
    c1, c2 = st.columns(2, gap="medium")
    for col, team in ((c1, a), (c2, b)):
        if not data.EXTENSIONS:
            with col:
                season_last_five(tm, team)
            continue
        last = live.recent_results(team)
        with col:
            with ui.panel(f"{team}: last five matches", "League matches, live from ESPN · xG and Attacking Index "
                          "once the weekly refresh has added the match"):
                if last.empty:
                    ui.note("Recent results are unavailable right now (no connection to ESPN).")
                    continue
                ours = data.history_matches(team)
                ours = ours.assign(event_id=ours.event_id.astype("Int64").astype(str)).set_index("event_id")
                st.dataframe(pd.DataFrame({
                    "Date": last.date.dt.tz_convert(live.LOCAL_TZ).dt.strftime("%d %b"),
                    "Competition": last.competition, "Opponent": last.opponent,
                    "H/A": last.home.map({True: "H", False: "A"}),
                    "Result": [f"{r} {g}-{c}" for r, g, c in zip(last.result, last.goals, last.goals_against)],
                    "xG": pd.to_numeric(last.event_id.map(ours.xg), errors="coerce"),
                    "Attacking Index": pd.to_numeric(last.event_id.map(ours.attacking_index), errors="coerce")}),
                    hide_index=True, placeholder="–", width="stretch",
                    column_config={"xG": st.column_config.NumberColumn(format="%.2f"),
                                   "Attacking Index": st.column_config.NumberColumn(format="%+.2f")})

    meetings = tm[(tm.team == a) & (tm.opponent == b)]
    if len(meetings):
        opp = tm[(tm.team == b) & (tm.opponent == a)].set_index("game_id")
        rows = []
        for m in meetings.itertuples():
            o = opp.loc[m.game_id]
            rows.append({"Date": m.date.date(), "Venue": f"{a if m.is_home else b} home",
                         "Score": f"{a} {m.goals}-{m.goals_against} {b}", f"{ra.abbr} xG": m.xg, f"{rb.abbr} xG": o.xg,
                         f"{ra.abbr} possession": m.possessionPct / 100,
                         "More attacking": a if m.attacking_index > o.attacking_index else b})
        with ui.panel("Their 2025/26 meetings"):
            st.dataframe(pd.DataFrame(rows), hide_index=True, placeholder="–", width="stretch", column_config={
                f"{ra.abbr} xG": st.column_config.NumberColumn(format="%.2f"),
                f"{rb.abbr} xG": st.column_config.NumberColumn(format="%.2f"),
                f"{ra.abbr} possession": st.column_config.NumberColumn(format="percent")})
    ui.footer()


def season_last_five(tm: pd.DataFrame, team: str) -> None:
    """The club's last five league matches of 2025/26, with xG and the match Attacking Index (thesis data)."""
    last = tm[tm.team == team].sort_values("matchweek").tail(5)
    with ui.panel(f"{team}: last five matches of 2025/26",
                  f"Average Attacking Index {last.attacking_index.mean():+.2f} "
                  f"(season {tm[tm.team == team].attacking_index.mean():+.2f})"):
        st.dataframe(pd.DataFrame({
            "MW": last.matchweek, "Opponent": last.opponent, "H/A": last.is_home.map({True: "H", False: "A"}),
            "Result": [f"{r} {g}-{c}" for r, g, c in zip(last.result, last.goals, last.goals_against)],
            "xG": last.xg, "Attacking Index": last.attacking_index}), hide_index=True, placeholder="–", width="stretch",
            column_config={"xG": st.column_config.NumberColumn(format="%.2f"),
                           "Attacking Index": st.column_config.NumberColumn(format="%+.2f")})
