"""Match centre: opened from a Matchday fixture (?event=<ESPN id>&code=<ESPN league code>).

Past matches: both line-ups with goal / assist / card icons, substitutes, key events, team stats, Understat xG race,
highlights, team news and related articles. Upcoming matches: confirmed or probable line-ups, team news,
attacking-edge reasons, recent form and a season comparison."""
import html

import pandas as pd
import streamlit as st

import charts
import data
import live
import matchcentre as mc
import pitch
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
    # Live, or kicking off within the hour: refresh score, minute, events, line-ups and stats every 30 seconds.
    soon = h["state"] == "pre" and pd.notna(h["date"]) and h["date"] - pd.Timestamp.now(tz="UTC") < pd.Timedelta(hours=1)
    live_now = h["state"] == "in" or soon
    st.fragment(lambda: match_body(code, event), run_every=30 if live_now else None)()
    ui.footer()


def match_body(code: str, event: str) -> None:
    s = mc.summary(code, event)
    h = mc.header(s)
    ev = mc.key_events(s, h["home"]["espn"])
    scoreboard(h, CODE_NAMES.get(code, ""), ev)
    if h["state"] == "in":
        ui.note(f'<span class="live">Live</span> Updates every 30 seconds · last update '
                f'{pd.Timestamp.now(tz=live.LOCAL_TZ):%H:%M:%S} MYT')
    if h["state"] == "pre":
        pre_match(s, h)
    else:
        post_match(s, h, ev, event)


def scoreboard(h: dict, comp: str, ev: pd.DataFrame) -> None:
    home, away = h["home"], h["away"]
    local = h["date"].tz_convert(live.LOCAL_TZ) if pd.notna(h["date"]) else None
    when = local.strftime("%A %d %B %Y · %H:%M MYT") if local is not None else ""
    if h["state"] != "pre":
        mid = f'<div class="sc-score">{home["score"]} – {away["score"]}</div><div class="sc-status">{html.escape(h["status"])}</div>'
    else:
        mid = f'<div class="sc-score">{local:%H:%M}</div><div class="sc-status">Kick-off (MYT)</div>'
    logo = lambda t: f'<img src="{html.escape(t["logo"])}" alt="">' if t.get("logo") else ""  # noqa: E731
    goals = ""
    if h["state"] != "pre" and len(ev):
        goals = (f'<div class="sc-scorers"><div>{pitch.scorers(ev, "home")}</div><div class="mid"></div>'
                 f'<div>{pitch.scorers(ev, "away")}</div></div>')
    st.markdown(f'''<div class="sc">
      <div class="sc-meta">{html.escape(comp)} · {html.escape(when)}{" · " + html.escape(h["venue"]) if h["venue"] else ""}</div>
      <div class="sc-row">
        <div class="sc-team home">{html.escape(home["team"])}{logo(home)}</div>
        <div class="sc-mid">{mid}</div>
        <div class="sc-team">{logo(away)}{html.escape(away["team"])}</div>
      </div>{goals}</div>''', unsafe_allow_html=True)


LEGEND = ('<div class="muted" style="display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:.5rem">'
          f'<span>{pitch.icon("goal", 13)} Goal</span><span>{pitch.icon("assist", 13)} Assist</span>'
          f'<span>{pitch.icon("yellow", 13)} Yellow</span><span>{pitch.icon("red", 13)} Red</span>'
          f'<span>{pitch.icon("sub_out", 13)} Subbed off</span><span>{pitch.icon("sub_in", 13)} Came on</span></div>')


def post_match(s: dict, h: dict, ev: pd.DataFrame, event: str) -> None:
    home, away = h["home"], h["away"]
    lu = mc.lineups(s)
    hl, ha = lu.get("home"), lu.get("away")
    c1, c2 = st.columns([1.05, 1], gap="medium")
    with c1:
        with ui.panel("Line-ups", f"{home['team']} at the bottom, {away['team']} at the top · hover a player"):
            if hl is None or hl.empty:
                ui.note("Line-ups are not available for this match yet.")
            else:
                st.markdown(LEGEND + pitch.pitch(hl[hl.starter], ha[ha.starter] if ha is not None else None,
                                                 home["color"], away["color"]), unsafe_allow_html=True)
                benches = pitch.bench(hl, home["team"], hl.formation.iloc[0], home.get("logo"), home["color"])
                if ha is not None and len(ha):
                    benches += pitch.bench(ha, away["team"], ha.formation.iloc[0], away.get("logo"), away["color"])
                st.markdown(benches, unsafe_allow_html=True)
    with c2:
        with ui.panel("Highlights"):
            highlight_block(s, h)
        with ui.panel("Key events"):
            st.markdown(pitch.timeline(ev, home, away), unsafe_allow_html=True)

    stats = mc.team_stats(s)
    tm, shots = mc.understat_match(event)
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        with ui.panel("Match stats", "ESPN"):
            if stats.empty:
                ui.note("Team stats are not available.")
            else:
                st.markdown(f'<div class="tl-head"><span>{pitch._crest(home)}{html.escape(home["team"])}</span>'
                            f'<span>{html.escape(away["team"])}{pitch._crest(away)}</span></div>'
                            + pitch.stats_rows(stats, home["color"], away["color"]), unsafe_allow_html=True)
    with c2:
        with ui.panel("Expected goals race", "Understat shot xG, cumulative · stars are goals"):
            if shots.empty:
                ui.note("Understat covers the three leagues only; xG appears once the weekly refresh has added "
                        "this match (Champions League matches have no xG).")
            else:
                xg = tm.set_index("team").xg
                st.plotly_chart(charts.xg_race(shots, home["team"], away["team"], home["color"], away["color"]),
                                width="stretch", key=f"xg-{event}")
                ai = tm.set_index("team").attacking_index
                more = ai.idxmax() if ai.notna().all() else None
                ui.note(f"Match xG {html.escape(home['team'])} {xg.get(home['team'], float('nan')):.2f} – "
                        f"{xg.get(away['team'], float('nan')):.2f} {html.escape(away['team'])}"
                        + (f" · More attacking side by our Attacking Index: <b>{html.escape(more)}</b>" if more else ""))
        with ui.panel("Team news", "Absences from this match sheet"):
            for side, t, sheet in (("home", home, hl), ("away", away, ha)):
                on = set(sheet.athlete_id) if sheet is not None and len(sheet) else set()
                injured = ev[(ev.kind == "sub") & ev.injury & (ev.side == side)] if len(ev) else ev
                rows = [("inj", "Went off injured", f"{r.other} ({r.minute})") for r in injured.itertuples()]
                missing = mc.squad_absentees(t["team"], on) if on else []
                if missing:
                    rows.append(("out", "Not in squad", ", ".join(missing)))
                team_news_block(t["team"], rows)
            ui.note("“Not in squad”: players with at least three league appearances this season who were not on the "
                    "team sheet. ESPN does not say why (injury, suspension, illness or selection).")
    news_block(s, home["team"], away["team"])


def team_news_block(team: str, rows: list[tuple[str, str, str]]) -> None:
    body = "".join(f'<div class="row"><span class="tag {k}">{html.escape(label)}</span><span>{html.escape(text)}</span></div>'
                   for k, label, text in rows) or '<div class="row muted">No absences or injuries recorded.</div>'
    st.markdown(f'<div class="tn"><b>{html.escape(team)}</b>{body}</div>', unsafe_allow_html=True)


def news_block(s: dict, home: str, away: str) -> None:
    items = mc.related_news(s, home, away)
    if not items:
        return
    with ui.panel("News", "The ESPN match report and stories about both clubs"):
        out = []
        for a in items:
            img = f'<img src="{html.escape(a["image"])}" alt="">' if a.get("image") else '<img alt="">'
            tag = '<span class="tag">Match report</span> · ' if a["report"] else ""
            when = live.time_ago(a["published"]) if pd.notna(a["published"]) else ""
            out.append(f'<div class="news">{img}<div><a href="{html.escape(a["link"])}" target="_blank" rel="noopener">'
                       f'{html.escape(a["headline"])}</a><div class="when">{tag}ESPN · {when}</div></div></div>')
        st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:.2rem .9rem">'
                    + "".join(out) + "</div>", unsafe_allow_html=True)


def highlight_block(s: dict, h: dict) -> None:
    home, away = h["home"]["team"], h["away"]["team"]
    if h["state"] == "in":
        ui.note("Highlights appear after the final whistle.")
        return
    vid = mc.highlights(home, away, h["date"].strftime("%Y-%m-%dT%H:%M:%SZ"))
    if vid:
        st.video(f"https://www.youtube.com/watch?v={vid['id']}")
        ui.note(f"{html.escape(vid['title'])} · {html.escape(vid['channel'])}"
                + ("" if vid.get("official") else " (not an official broadcaster channel)"))
        return
    links = [f'<a href="{html.escape(mc.youtube_search_url(home, away, h["date"]))}" target="_blank" rel="noopener">'
             "Find the highlights on YouTube ›</a>"]
    links += [f'<a href="{html.escape(v["url"])}" target="_blank" rel="noopener">ESPN video: {html.escape(v["headline"])} ›</a>'
              for v in mc.espn_videos(s)[:2]]
    if mc.youtube_key():
        ui.note("No highlights video found yet; they are usually uploaded a few hours after the final whistle, and some "
                "leagues do not publish on YouTube in every country.")
    st.markdown('<div class="vids">' + "".join(links) + "</div>", unsafe_allow_html=True)


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
            frames[side] = x.assign(jersey=x.athlete_id.map(shirts), note=[f"started {a} of the last {b} league matches"
                                                                          for a, b in zip(x.recent_starts, x.of_matches)])
    form = live.form()
    both = not form.empty and home["team"] in form.index and away["team"] in form.index
    c1, c2 = st.columns([1.05, 1], gap="medium")
    with c1:
        title = "Confirmed line-ups" if confirmed else "Probable line-ups"
        sub = ("From the ESPN team sheet" if confirmed else
               "Most-used recent formation and starters, last 5 league matches · hover a player")
        with ui.panel(title, sub):
            if frames:
                st.markdown(pitch.pitch(frames.get("home"), frames.get("away"), home["color"], away["color"],
                                        with_events=False), unsafe_allow_html=True)
                missing = [t["team"] for side, t in (("home", home), ("away", away)) if side not in frames]
                if missing:
                    ui.note(f"No probable XI for {html.escape(', '.join(missing))}: only clubs from the three leagues "
                            "are covered.")
                elif not confirmed:
                    ui.note("A data-driven guess from recent team sheets. It switches to the confirmed line-ups when "
                            "ESPN publishes them, about an hour before kick-off.")
            else:
                ui.note("Probable XIs are only available for clubs from the three leagues.")
    with c2:
        with ui.panel("Attacking edge", "Which side is likely to show the more attacking style · not a result prediction"):
            if both:
                p = data.predict_more_attacking(home["team"], away["team"], "A", form)
                st.plotly_chart(charts.gauge_bar(p["prob"], home["team"], away["team"], home["color"], away["color"]),
                                width="stretch", config={"displayModeBar": False}, key="pre-gauge")
                st.plotly_chart(charts.contributions(p["themes"], home["team"], away["team"], home["color"],
                                                     away["color"]),
                                width="stretch", config={"displayModeBar": False}, key="pre-themes")
                ui.note("Bars show what pushes the estimate towards each side (season and last-five form, home "
                        "advantage). Probabilistic, not for betting.")
            else:
                ui.note("Only available when both clubs play in the three leagues.")
        with ui.panel("Recent form", "Last five competitive matches, all competitions · oldest to newest · hover for "
                      "the score"):
            for t in (home, away):
                chips = mc.form_chips(t["team"], h["date"]) if t["team"] in live.team_ids() else []
                cells = "".join(f'<span class="fchip {r}" title="{html.escape(txt)}">{r}</span>' for r, txt in chips)
                st.markdown(f'<div class="form-row"><b>{html.escape(t["team"])}</b>{cells or "<span class=muted>–</span>"}</div>',
                            unsafe_allow_html=True)
        with ui.panel("Team news", "From each club's previous match"):
            for t in (home, away):
                prev = mc.previous_match_news(t["team"], h["date"].isoformat())
                rows = []
                if prev:
                    ctx = f"vs {prev['opponent']}, {prev['date']:%d %b}"
                    rows += [("inj", "Injury doubt", f"{n} (went off injured {ctx})") for n in prev["injured"]]
                    rows += [("sus", "Suspended", f"{n} (sent off {ctx})") for n in prev["sent_off"]]
                team_news_block(t["team"], rows)
            ui.note("Based on the previous match sheet only (players who went off injured or were sent off). "
                    "Long-term injuries and accumulated-yellow bans are not in the free data.")
    if both:
        with ui.panel("Season so far", "Per-match averages, 2026/27 league matches"):
            rows = [("Attacking Index", "attacking_index_season", "%+.2f"), ("xG", "xg_season", "%.2f"),
                    ("xG against", "xg_against_season", "%.2f"), ("Shots", "shots_season", "%.1f"),
                    ("Possession %", "possessionPct_season", "%.1f"), ("Pass accuracy %", "pass_accuracy_season", "%.1f"),
                    ("Long-ball share %", "long_ball_share_season", "%.1f"), ("Crosses", "totalCrosses_season", "%.1f")]
            st.dataframe(pd.DataFrame({"Metric": [r[0] for r in rows],
                                       home["team"]: [r[2] % form.loc[home["team"], r[1]] for r in rows],
                                       away["team"]: [r[2] % form.loc[away["team"], r[1]] for r in rows]}),
                         hide_index=True, width="stretch")
    news_block(s, home["team"], away["team"])
