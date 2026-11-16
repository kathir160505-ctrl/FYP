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
        <div class="note" style="margin-bottom:0.6rem">{row.league_name} · {ui.ordinal(row.position)} · {row.pts} pts
        · {int(row.matches)} matches</div>
        {ui.cluster_badge(row.cluster)}
        <p style="text-align:left;margin:0.8rem 0 0 0">{html.escape(data.style_summary(row))}</p></div>''',
                 unsafe_allow_html=True)


def _distinct(c1: str, c2: str) -> bool:
    rgb = lambda c: [int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]  # noqa: E731
    return sum((x - y) ** 2 for x, y in zip(rgb(c1), rgb(c2))) ** 0.5 > 110


def render() -> None:
    ui.page_header("Head-to-head", "Compare two clubs",
                   "Choose a season and two clubs, from the same league or different ones, to see their attacking "
                   "styles and statistics side by side and which of the two is more likely to attack more. All figures "
                   "come from the selected season. This compares attacking style only; it does not predict results.")
    # One season at a time: 2025/26, or (with the extensions) the current season, classified with the
    # unchanged 2025/26 model from that season's own top-flight matches.
    seasons = data.seasons() if data.EXTENSIONS else [data.THESIS_SEASON]
    with ui.panel():
        c0, c1, c2, c3 = st.columns([1.7, 2, 2, 1.7])
        season = c0.selectbox("Season", seasons, format_func=data.season_option, disabled=len(seasons) == 1)
        df = data.season_clubs(season)
        teams = sorted(df.team)
        default_a = st.query_params.get("a", "Manchester United")
        a = c1.selectbox("Club A", teams, index=teams.index(default_a) if default_a in teams else 0)
        others = [t for t in teams if t != a]
        b = c2.selectbox("Club B", others, index=others.index("Liverpool") if "Liverpool" in others else 0)
        venue_label = c3.segmented_control("Venue", ["A home", "B home", "Neutral"], default="A home") or "A home"
    venue = {"A home": "A", "B home": "B", "Neutral": "N"}[venue_label]
    venue_text = {"A": f"{a} at home", "B": f"{b} at home", "N": "neutral venue"}[venue]
    st.query_params["a"] = a
    label = data.season_label(season)

    ra, rb = df[df.team == a].iloc[0], df[df.team == b].iloc[0]
    color_b = rb.color if _distinct(ra.color, rb.color) else "#111418"

    left, right = st.columns(2, gap="medium")
    _side(left, ra, "Club A")
    _side(right, rb, "Club B")
    if season != data.THESIS_SEASON:
        est = {t: int(r.get("estimated_matches", 0) or 0) for t, r in ((a, ra), (b, rb))}
        est_text = (" " + " and ".join(f"{n} of {t}'s" for t, n in est.items() if n) + " matches are estimated. "
                    + data.ESTIMATE_NOTE) if any(est.values()) else ""
        ui.note(f"{label} styles use only {label} league matches, assigned by the model trained on 2025/26. Early in a "
                "season they rest on few matches and can still change from week to week." + est_text)

    st.write("")
    c1, c2 = st.columns([1, 1.1], gap="medium")
    with c1:
        with ui.panel("Attacking fingerprints", f"Percentile among the {len(df)} clubs of {label}"):
            st.plotly_chart(charts.radar([
                {"name": a, "values": [ra[f"{f}_pct"] for f in data.FEATURES], "color": ra.color},
                {"name": b, "values": [rb[f"{f}_pct"] for f in data.FEATURES], "color": color_b}], height=440),
                width="stretch")
    with c2:
        with ui.panel("Stat by stat", f"Percentile bars · hover for the raw value · {label}"):
            st.plotly_chart(charts.diverging_bars(
                pd.Series({f: ra[f"{f}_pct"] for f in data.FEATURES}), pd.Series({f: rb[f"{f}_pct"] for f in data.FEATURES}),
                a, b, ra.color, color_b, ra, rb), width="stretch")

    # The model's inputs for the same season: end-of-2025/26 profiles, or this season's profiles to date.
    form = data.team_form() if season == data.THESIS_SEASON else live.form()
    with ui.panel("Which side attacks more?", f"Estimate of the more attacking style · {venue_text} · {label} data"):
        if a not in form.index or b not in form.index:
            ui.note(f"The estimate needs at least five {label} matches for both clubs.")
        else:
            pred = data.predict_more_attacking(a, b, venue, form)
            p = pred["prob"]
            fav, fav_p = (a, p) if p >= 0.5 else (b, 1 - p)
            strength = "Strong" if fav_p >= 0.70 else "Moderate" if fav_p >= 0.58 else "Slight"
            g1, g2 = st.columns([1, 1.2], gap="medium")
            with g1:
                st.markdown(f'<div class="prob-head"><div class="k">More attacking style</div>'
                            f'<div class="v">{html.escape(fav)} {fav_p:.0%}</div>'
                            f'<div class="note">{strength} edge</div></div>', unsafe_allow_html=True)
                st.plotly_chart(charts.gauge_bar(p, ra.abbr, rb.abbr, ra.color, color_b), width="stretch",
                                config={"displayModeBar": False})
            with g2:
                st.markdown('<div class="panel-sub">What drives the estimate</div>', unsafe_allow_html=True)
                st.plotly_chart(charts.contributions(pred["themes"], ra.abbr, rb.abbr, ra.color, color_b),
                                width="stretch", config={"displayModeBar": False})
            ui.callout(html.escape(data.comparison_summary(ra, rb, pred, venue)))
    if ra.league_name != rb.league_name:
        ui.callout("Cross-league comparison: the model was trained on league matches and its inputs are standardised "
                   "within each league, so this compares each club's attacking dominance <i>within its own league</i>. "
                   "It is not a forecast of a real fixture.", warn=True)
    ui.callout(f"Logistic regression (AUC 0.81 on held-out matches) using each club's {label} season-to-date and "
               "last-five-match attacking profile plus venue. It estimates attacking style only and does <b>not</b> "
               "predict the winner or the score.")

    c1, c2 = st.columns(2, gap="medium")
    for col, team in ((c1, a), (c2, b)):
        with col:
            last_five(team, season)

    tm_a = data.history_matches(a)[lambda m: m.season == season]
    tm_b = data.history_matches(b)[lambda m: m.season == season].set_index("game_id")
    meetings = tm_a[tm_a.opponent == b]
    if len(meetings):
        rows = []
        for m in meetings.itertuples():
            o = tm_b.loc[m.game_id]
            rows.append({"Date": m.date.date(), "Venue": f"{a if m.is_home else b} home",
                         "Score": f"{a} {m.goals}-{m.goals_against} {b}", f"{ra.abbr} xG": m.xg, f"{rb.abbr} xG": o.xg,
                         f"{ra.abbr} possession": m.possessionPct / 100,
                         "More attacking": a if m.attacking_index > o.attacking_index else b})
        with ui.panel(f"Their {label} meetings"):
            st.dataframe(pd.DataFrame(rows), hide_index=True, placeholder="–", width="stretch", column_config={
                f"{ra.abbr} xG": st.column_config.NumberColumn(format="%.2f"),
                f"{rb.abbr} xG": st.column_config.NumberColumn(format="%.2f"),
                f"{ra.abbr} possession": st.column_config.NumberColumn(format="percent")})
    ui.footer()


def last_five(team: str, season: int) -> None:
    """The club's last five league matches of the selected season, with xG and the match Attacking Index."""
    played = data.history_matches(team)[lambda m: m.season == season].sort_values("date")
    last = played.tail(5)
    with ui.panel(f"{team}: last five matches of {data.season_label(season)}",
                  f"Average Attacking Index {last.attacking_index.mean():+.2f} "
                  f"(season {played.attacking_index.mean():+.2f})"):
        st.dataframe(pd.DataFrame({
            "MW": last.matchweek, "Opponent": last.opponent, "H/A": last.is_home.map({True: "H", False: "A"}),
            "Result": [f"{r} {g}-{c}" for r, g, c in zip(last.result, last.goals, last.goals_against)],
            "xG": last.xg, "Attacking Index": last.attacking_index}), hide_index=True, placeholder="–", width="stretch",
            column_config={"xG": st.column_config.NumberColumn(format="%.2f"),
                           "Attacking Index": st.column_config.NumberColumn(format="%+.2f")})
