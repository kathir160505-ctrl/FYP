import html

import pandas as pd
import streamlit as st

import charts
import data
import ui


def _side(col, row, label: str) -> None:
    col.markdown(f'''<div class="card" style="text-align:center;border-top:4px solid {row.color}">
        <div class="note">{label}</div><img src="{row.logo}" width="70" style="margin:0.4rem 0">
        <h4 style="font-size:1.25rem">{html.escape(row.team)}</h4>
        <div class="note" style="margin-bottom:0.5rem">{row.league_name} · {ui.ordinal(row.position)} · {row.Pts} pts</div>
        {ui.cluster_badge(row.cluster)}</div>''', unsafe_allow_html=True)


def render() -> None:
    df = data.clubs()
    ui.hero("Head-to-head", "Who attacks more?",
            "Compare any two clubs, including across leagues, and estimate which side is more likely to show "
            "the more attacking style in a meeting. This is a style estimate, not a result prediction.")
    teams = data.club_options(df)
    c1, c2, c3 = st.columns([2, 2, 1.4])
    a = c1.selectbox("Club A", teams, index=teams.index(st.query_params.get("a", "Manchester United"))
                     if st.query_params.get("a", "Manchester United") in teams else 0)
    b = c2.selectbox("Club B", [t for t in teams if t != a],
                     index=[t for t in teams if t != a].index("Liverpool") if a != "Liverpool" else 0)
    venue_label = c3.radio("Venue", [f"{a} at home", f"{b} at home", "Neutral"], index=0)
    venue = {f"{a} at home": "A", f"{b} at home": "B", "Neutral": "N"}[venue_label]
    st.query_params["a"] = a

    ra, rb = df.set_index("team").loc[a], df.set_index("team").loc[b]
    ra_t, rb_t = df[df.team == a].iloc[0], df[df.team == b].iloc[0]
    color_b = rb.color if _distinct(ra.color, rb.color) else "#e2e8f0"

    left, mid, right = st.columns([1, 1.6, 1])
    _side(left, ra_t, "Club A")
    _side(right, rb_t, "Club B")
    with mid:
        pred = data.predict_more_attacking(a, b, venue)
        p = pred["prob"]
        fav, fav_p = (a, p) if p >= 0.5 else (b, 1 - p)
        strength = "strong" if fav_p >= 0.70 else "moderate" if fav_p >= 0.58 else "slight"
        st.markdown(f'<div style="text-align:center;margin-top:0.6rem"><div class="note">Probability of showing '
                    f'the more attacking style</div><div style="font-size:1.45rem;font-weight:800;color:#f8fafc;'
                    f'margin:0.3rem 0">{html.escape(fav)} · {fav_p:.0%}</div>'
                    f'<div class="note">{strength} edge · {venue_label.lower()}</div></div>', unsafe_allow_html=True)
        st.plotly_chart(charts.gauge_bar(p, ra.abbr, rb.abbr, ra.color, color_b), width="stretch",
                        config={"displayModeBar": False})
        st.plotly_chart(charts.contributions(pred["themes"], ra.abbr, rb.abbr, ra.color, color_b), width="stretch",
                        config={"displayModeBar": False})

    if ra.league_name != rb.league_name:
        ui.callout("Cross-league comparison: the model was trained on league matches, and its inputs are standardised "
                   "within each league. Treat this as a comparison of each club's attacking dominance <i>within its own "
                   "league</i>, not a forecast of a real fixture.", warn=True)
    ui.callout("How to read it: the model (logistic regression, AUC 0.81 on held-out matches) uses each club's "
               "season-long and last-5-match attacking profile plus venue. The bars show which factors push the estimate "
               "towards each club. It does <b>not</b> predict the winner or the score.")

    c1, c2 = st.columns([1, 1.1])
    with c1:
        ui.section("Attacking fingerprints")
        st.plotly_chart(charts.radar([
            {"name": a, "values": [ra[f"{f}_pct"] for f in data.FEATURES], "color": ra.color},
            {"name": b, "values": [rb[f"{f}_pct"] for f in data.FEATURES], "color": color_b}]), width="stretch")
    with c2:
        ui.section("Stat by stat")
        st.plotly_chart(charts.diverging_bars(
            pd.Series({f: ra[f"{f}_pct"] for f in data.FEATURES}), pd.Series({f: rb[f"{f}_pct"] for f in data.FEATURES}),
            a, b, ra.color, color_b, ra, rb), width="stretch")

    tm = data.team_matches()
    ui.section("Recent attacking form (last 5 matches)")
    c1, c2 = st.columns(2)
    for col, team, color in ((c1, a, ra.color), (c2, b, color_b)):
        last = tm[tm.team == team].sort_values("matchweek").tail(5)
        form = " ".join({"W": "🟩", "D": "⬜", "L": "🟥"}[r] for r in last.result)
        col.markdown(f"**{team}** {form} · avg Attacking Index **{last.attacking_index.mean():+.2f}** "
                     f"(season {tm[tm.team == team].attacking_index.mean():+.2f})")
        col.dataframe(pd.DataFrame({
            "MW": last.matchweek, "Opponent": last.opponent, "Venue": last.is_home.map({True: "H", False: "A"}),
            "Score": [f"{g}-{c}" for g, c in zip(last.goals, last.goals_against)], "xG": last.xg.round(2),
            "Attacking Index": last.attacking_index.round(2)}), hide_index=True, width="stretch")

    meetings = tm[(tm.team == a) & (tm.opponent == b)]
    if len(meetings):
        ui.section("Their 2025/26 meetings")
        opp = tm[(tm.team == b) & (tm.opponent == a)].set_index("game_id")
        rows = []
        for m in meetings.itertuples():
            o = opp.loc[m.game_id]
            more = a if m.attacking_index > o.attacking_index else b
            rows.append({"Date": m.date.date(), "Venue": f"{a if m.is_home else b} home",
                         "Score": f"{a} {m.goals}-{m.goals_against} {b}", f"{a} xG": round(m.xg, 2),
                         f"{b} xG": round(o.xg, 2), f"{a} poss.": f"{m.possessionPct:.0f}%",
                         "More attacking": more})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    ui.footer()


def _distinct(c1: str, c2: str) -> bool:
    rgb = lambda c: [int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]  # noqa: E731
    return sum((x - y) ** 2 for x, y in zip(rgb(c1), rgb(c2))) ** 0.5 > 110
