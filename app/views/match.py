"""Match centre: opened from a Matchday fixture (?event=<ESPN id>&code=<ESPN league code>).

Past matches: both line-ups with goal / assist / card icons, key events, team stats, Understat xG race and
highlights. Upcoming matches: probable XIs, attacking-edge reasons, recent form and a season comparison."""
import html

import pandas as pd
import streamlit as st

import charts
import data
import live
import matchcentre as mc
import ui

CODE_NAMES = {v: k for k, v in live.LEAGUE_CODES.items()}


def render() -> None:
    event, code = st.query_params.get("event"), st.query_params.get("code", "eng.1")
    if not event:
        ui.page_header("Matchday", "Match centre", "Open a match from the Matchday page.")
        ui.note("Choose a fixture on the Matchday page to open its match centre.")
        return
    s = mc.summary(code, event)
    if not s:
        ui.callout("This match could not be loaded from ESPN right now. Try again shortly.", warn=True)
        return
    h = mc.header(s)
    home, away = h["home"], h["away"]
    scoreboard(h, CODE_NAMES.get(code, ""))
    if h["state"] == "pre":
        pre_match(s, h)
    else:
        post_match(s, h, event)
    ui.footer()


def scoreboard(h: dict, comp: str) -> None:
    home, away = h["home"], h["away"]
    local = h["date"].tz_convert(live.LOCAL_TZ) if pd.notna(h["date"]) else None
    when = local.strftime("%A %d %B %Y · %H:%M MYT") if local is not None else ""
    mid = (f'<div class="sc-score">{home["score"]} – {away["score"]}</div><div class="sc-status">{html.escape(h["status"])}</div>'
           if h["state"] != "pre" else f'<div class="sc-score">{local:%H:%M}</div><div class="sc-status">Kick-off (MYT)</div>')
    logo = lambda t: f'<img src="{html.escape(t["logo"])}" alt="">' if t.get("logo") else ""  # noqa: E731
    st.markdown(f'''<div class="sc">
      <div class="sc-meta">{html.escape(comp)} · {html.escape(when)}{" · " + html.escape(h["venue"]) if h["venue"] else ""}</div>
      <div class="sc-row">
        <div class="sc-team home">{html.escape(home["team"])}{logo(home)}</div>
        <div class="sc-mid">{mid}</div>
        <div class="sc-team">{logo(away)}{html.escape(away["team"])}</div>
      </div></div>''', unsafe_allow_html=True)


def events_list(ev: pd.DataFrame, home_espn: str) -> None:
    if ev.empty:
        ui.note("No key events recorded.")
        return
    rows = []
    for r in ev.itertuples():
        who = r.who[0] if r.who else ""
        extra = ""
        if r.type in ("Goal", "Penalty - Scored") and len(r.who) > 1:
            extra = f'<span class="ev-sub">👟 {html.escape(r.who[1])}</span>'
        elif r.type == "Substitution" and len(r.who) > 1:
            extra = f'<span class="ev-sub">off: {html.escape(r.who[1])}</span>'
        side = "home" if r.team == home_espn else "away"
        rows.append(f'<div class="ev {side}"><span class="ev-min">{html.escape(r.minute)}</span>'
                    f'<span class="ev-ico">{r.icon}</span><span class="ev-who">{html.escape(who)}</span>{extra}</div>')
    st.markdown(f'<div class="evs">{"".join(rows)}</div>', unsafe_allow_html=True)


def bench_list(df: pd.DataFrame) -> str:
    subs = df[~df.starter]
    items = [f"{html.escape(r.player)} {r.badges}".strip() for r in subs.itertuples() if r.subbed_in] or ["none"]
    unused = [html.escape(r.player) for r in subs.itertuples() if not r.subbed_in]
    return f"<b>Came on:</b> {', '.join(items)}" + (f"<br><b>Unused:</b> {', '.join(unused)}" if unused else "")


def post_match(s: dict, h: dict, event: str) -> None:
    home, away = h["home"], h["away"]
    lu = mc.lineups(s)
    ev = mc.key_events(s)
    hl, ha = lu.get("home"), lu.get("away")
    c1, c2 = st.columns([1.05, 1], gap="medium")
    with c1:
        with ui.panel("Line-ups", "⚽ goal · 👟 assist · 🟨 🟥 cards · ▼ subbed off · hover a player"):
            if hl is None or hl.empty:
                ui.note("Line-ups are not available for this match yet.")
            else:
                st.plotly_chart(charts.match_pitch(hl[hl.starter], ha[ha.starter] if ha is not None else None,
                                                   home["color"], away["color"]),
                                width="stretch", config={"displayModeBar": False}, key=f"mp-{event}")
                st.markdown(f'<div class="note"><b>{html.escape(home["team"])}</b> ({html.escape(str(hl.formation.iloc[0]))}, '
                            f'bottom) · {bench_list(hl)}</div>', unsafe_allow_html=True)
                if ha is not None and len(ha):
                    st.markdown(f'<div class="note" style="margin-top:.4rem"><b>{html.escape(away["team"])}</b> '
                                f'({html.escape(str(ha.formation.iloc[0]))}, top) · {bench_list(ha)}</div>',
                                unsafe_allow_html=True)
    with c2:
        with ui.panel("Highlights"):
            highlight_block(s, h)
        with ui.panel("Key events"):
            events_list(ev, home["espn"])

    stats = mc.team_stats(s)
    tm, shots = mc.understat_match(event)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with ui.panel("Match stats", f"{home['team']} (left) vs {away['team']} (right) · ESPN"):
            if stats.empty:
                ui.note("Team stats are not available.")
            else:
                st.plotly_chart(charts.match_stats(stats, home["team"], away["team"], home["color"],
                                                   away["color"]),
                                width="stretch", config={"displayModeBar": False}, key=f"ms-{event}")
    with c2:
        with ui.panel("Expected goals race", "Understat shot xG, cumulative · stars are goals"):
            if shots.empty:
                ui.note("Understat covers the three leagues only; xG appears once the weekly refresh has added "
                        "this match (Champions League matches have no xG).")
            else:
                xg = tm.set_index("team").xg
                st.plotly_chart(charts.xg_race(shots, home["team"], away["team"], home["color"],
                                               away["color"]),
                                width="stretch", key=f"xg-{event}")
                ai = tm.set_index("team").attacking_index
                more = ai.idxmax() if ai.notna().all() else None
                ui.note(f"Match xG {home['team']} {xg.get(home['team'], float('nan')):.2f} – "
                        f"{xg.get(away['team'], float('nan')):.2f} {away['team']}"
                        + (f" · More attacking side by our Attacking Index: <b>{html.escape(more)}</b>" if more else ""))


def highlight_block(s: dict, h: dict) -> None:
    home, away = h["home"]["team"], h["away"]["team"]
    if h["state"] == "in":
        ui.note("Highlights appear after the final whistle.")
        return
    vid = mc.highlights(home, away, h["date"].strftime("%Y-%m-%dT%H:%M:%SZ"))
    if vid:
        st.video(f"https://www.youtube.com/watch?v={vid['id']}")
        ui.note(f"{html.escape(vid['title'])} · {html.escape(vid['channel'])} on YouTube")
        return
    links = [f'<a href="{html.escape(mc.youtube_search_url(home, away, h["date"]))}" target="_blank" rel="noopener">'
             "▶ Find the highlights on YouTube</a>"]
    links += [f'<a href="{html.escape(v["url"])}" target="_blank" rel="noopener">▶ ESPN: {html.escape(v["headline"])}</a>'
              for v in mc.espn_videos(s)[:2]]
    st.markdown('<div class="vids">' + "".join(links) + "</div>", unsafe_allow_html=True)
    if not mc.youtube_key():
        ui.note("Add a free YouTube Data API key (YOUTUBE_API_KEY in .streamlit/secrets.toml) to play the official "
                "highlights here.")


def pre_match(s: dict, h: dict) -> None:
    home, away = h["home"], h["away"]
    xi = data.probable_xi() if data.players_ready() else pd.DataFrame()
    lu = mc.lineups(s)  # ESPN publishes confirmed line-ups about an hour before kick-off
    confirmed = all(side in lu and len(lu[side]) for side in ("home", "away"))
    frames = {}
    for side, t in (("home", home), ("away", away)):
        if confirmed:
            frames[side] = lu[side][lu[side].starter]
        elif len(xi) and t["team"] in set(xi.team):
            x = xi[xi.team == t["team"]]
            shirts = data.players().dropna(subset=["athlete_id"]).sort_values("season").drop_duplicates(
                "athlete_id", keep="last").set_index("athlete_id").jersey
            frames[side] = x.assign(jersey=x.athlete_id.map(shirts), note=[f"Started {a} of the last {b} league matches"
                                          for a, b in zip(x.recent_starts, x.of_matches)])
    form = live.form()
    c1, c2 = st.columns([1.05, 1], gap="medium")
    with c1:
        title = "Confirmed line-ups" if confirmed else "Probable line-ups"
        sub = ("From the ESPN team sheet" if confirmed else
               "Most-used recent formation and starters (last 5 league matches) · injuries and suspensions not known")
        with ui.panel(title, sub):
            if frames:
                st.plotly_chart(charts.match_pitch(frames.get("home"), frames.get("away"), home["color"],
                                                   away["color"]),
                                width="stretch", config={"displayModeBar": False}, key="pre-pitch")
                for side, t in (("home", home), ("away", away)):
                    if side not in frames:
                        ui.note(f"No probable XI for {html.escape(t['team'])}: only clubs from the three leagues are covered.")
            else:
                ui.note("Probable XIs are only available for clubs from the three leagues.")
    with c2:
        with ui.panel("Attacking edge", "Which side is likely to show the more attacking style · not a result prediction"):
            if not form.empty and home["team"] in form.index and away["team"] in form.index:
                p = data.predict_more_attacking(home["team"], away["team"], "A", form)
                st.plotly_chart(charts.gauge_bar(p["prob"], home["team"], away["team"], home["color"],
                                                 away["color"]),
                                width="stretch", config={"displayModeBar": False}, key="pre-gauge")
                st.plotly_chart(charts.contributions(p["themes"], home["team"], away["team"], home["color"],
                                                     away["color"]),
                                width="stretch", config={"displayModeBar": False}, key="pre-themes")
                ui.note("Bars show what pushes the estimate towards each side (season and last-five form, home "
                        "advantage). Probabilistic, not for betting.")
            else:
                ui.note("Only available when both clubs play in the three leagues.")
        with ui.panel("Recent form", "Last five league matches"):
            for t in (home, away):
                chips = mc.form_chips(t["team"], h["date"]) if t["team"] in set(data.history().team) else []
                cells = "".join(f'<span class="chip {r}" title="{html.escape(txt)}">{r}</span>' for r, txt in chips)
                st.markdown(f'<div class="form-row"><b>{html.escape(t["team"])}</b>{cells or "<span class=note>–</span>"}</div>',
                            unsafe_allow_html=True)
    if not form.empty and home["team"] in form.index and away["team"] in form.index:
        with ui.panel("Season so far", "Per-match averages, 2026/27 league matches"):
            rows = [("Attacking Index", "attacking_index_season", "%+.2f"), ("xG", "xg_season", "%.2f"),
                    ("xG against", "xg_against_season", "%.2f"), ("Shots", "shots_season", "%.1f"),
                    ("Possession %", "possessionPct_season", "%.1f"), ("Pass accuracy %", "pass_accuracy_season", "%.1f"),
                    ("Long-ball share %", "long_ball_share_season", "%.1f"), ("Crosses", "totalCrosses_season", "%.1f")]
            st.dataframe(pd.DataFrame({"Metric": [r[0] for r in rows],
                                       home["team"]: [r[2] % form.loc[home["team"], r[1]] for r in rows],
                                       away["team"]: [r[2] % form.loc[away["team"], r[1]] for r in rows]}),
                         hide_index=True, width="stretch")
