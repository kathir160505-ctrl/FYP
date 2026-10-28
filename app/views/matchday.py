import html

import pandas as pd
import streamlit as st

import data
import live
import ui

LEAGUE_SHORT = {"Premier League": "EPL", "La Liga": "LaLiga", "Serie A": "Serie A", "Champions League": "UCL"}


def _team(name: str, logo: str, side: str) -> str:
    img = f'<img src="{logo}" alt="">' if logo else ""
    label = html.escape(name)
    return f'<div class="tm {side}">{label}{img}</div>' if side == "home" else f'<div class="tm">{img}{label}</div>'


def _edge(r, form: pd.DataFrame) -> str:
    """Attacking-edge bar: P(home side shows the more attacking style), from 2026/27 form."""
    if form.empty or r.home not in form.index or r.away not in form.index:
        known = set(live.club_names().values())
        why = ("Only for clubs from the three leagues" if r.home not in known or r.away not in known
               else "Not enough data yet")
        return f'<div class="edge"><div class="cap">Attacking edge</div><div class="note">{why}</div></div>'
    p = data.predict_more_attacking(r.home, r.away, "A", form)["prob"]
    away_color = r.away_color if _distinct(r.home_color, r.away_color) else "#9CA3AF"
    return (f'<div class="edge"><div class="cap">Attacking edge</div><div class="bar">'
            f'<div style="width:{p:.0%};background:{r.home_color}"></div>'
            f'<div style="width:{1 - p:.0%};background:{away_color}"></div></div>'
            f'<div class="lbl"><span>{html.escape(r.home_abbr)} {p:.0%}</span><span>{1 - p:.0%} {html.escape(r.away_abbr)}</span></div></div>')


def _distinct(c1: str, c2: str) -> bool:
    rgb = lambda c: [int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]  # noqa: E731
    return sum((x - y) ** 2 for x, y in zip(rgb(c1), rgb(c2))) ** 0.5 > 110


def _fixture_rows(df: pd.DataFrame, form: pd.DataFrame, with_edge: bool) -> str:
    out = []
    for day, g in df.groupby(df.local.dt.date, sort=True):
        out.append(f'<div class="day-head">{pd.Timestamp(day).strftime("%A %d %B")}</div>')
        for r in g.itertuples():
            if r.state == "pre":
                mid = f'<div class="mid time">{r.local.strftime("%H:%M")}</div>'
            elif r.state == "in":
                mid = f'<div class="mid">{r.home_score} – {r.away_score}<div class="live" style="justify-content:center">{html.escape(r.status)}</div></div>'
            else:
                mid = f'<div class="mid">{r.home_score} – {r.away_score}<div class="note" style="font-family:Inter">{html.escape(r.status)}</div></div>'
            right = _edge(r, form) if with_edge else '<div class="mc">Line-ups · stats · highlights ›</div>'
            href = f"match?event={r.id}&code={live.LEAGUE_CODES[r.league]}"  # relative, so it works under a sub-path
            out.append(f'<a class="fx" href="{href}" target="_self" title="Open the match centre">'
                       f'<div class="lg">{LEAGUE_SHORT[r.league]}</div>{_team(r.home, r.home_logo, "home")}'
                       f'{mid}{_team(r.away, r.away_logo, "away")}{right}</a>')
    return "".join(out)


def _news(df: pd.DataFrame, limit: int) -> None:
    if df.empty:
        ui.note("News is unavailable right now (no connection to the ESPN feed).")
        return
    items = []
    for i, r in enumerate(df.head(limit).itertuples()):
        img = f'<img src="{r.image}" alt="">' if r.image else '<img alt="">'
        meta = f'<div class="when"><span class="tag">{LEAGUE_SHORT[r.league]}</span> · {live.time_ago(r.published)}</div>'
        link = f'<a href="{html.escape(r.link)}" target="_blank" rel="noopener">{html.escape(r.headline)}</a>'
        if i == 0:
            desc = f'<div class="desc">{html.escape(r.description[:220])}</div>' if r.description else ""
            items.append(f'<div class="news lead">{img}<div>{link}{desc}{meta}</div></div>')
        else:
            items.append(f'<div class="news">{img}<div>{link}{meta}</div></div>')
    st.markdown("".join(items), unsafe_allow_html=True)
    ui.note("Headlines and images from ESPN. Each story opens on espn.com.")


def render() -> None:
    m = live.meta()
    updated = pd.to_datetime(m.get("updated_at"), utc=True) if m else None
    meta = '<span class="live">Live</span><br>Times in MYT (UTC+8)'
    if updated is not None:
        meta += f'<br>Form data: {updated.tz_convert(live.LOCAL_TZ).strftime("%d %b, %H:%M")}'
    ui.page_header("Matchday · 2026/27", "Matchday centre",
                   "Upcoming fixtures, live scores and recent results across the three leagues and the Champions League, "
                   "with a model estimate of "
                   "which side is likely to show the more attacking style. Latest headlines on the right.", meta=meta)

    leagues = st.pills("League", ["All leagues", *live.LEAGUE_CODES], default="All leagues",
                       label_visibility="collapsed") or "All leagues"
    st.fragment(lambda: board(leagues), run_every=60)()
    ui.footer()


def board(leagues: str) -> None:
    """Fixtures, live scores, results and news; re-runs every minute (ESPN scoreboards are cached for 30 s)."""
    fx = live.fixtures()  # no spinner: this re-runs every minute and is usually served from the cache
    nw = live.news()
    if leagues != "All leagues":
        fx = fx[fx.league == leagues] if not fx.empty else fx
        nw = nw[nw.league == leagues] if not nw.empty else nw
    form = live.form()

    left, right = st.columns([2.15, 1], gap="large")
    with left:
        if fx.empty:
            ui.callout("Fixtures are unavailable right now (no connection to the ESPN feed). Try again shortly.", warn=True)
        else:
            upcoming = fx[fx.state.isin(["pre", "in"])]
            results = fx[fx.state == "post"].sort_values("kickoff", ascending=False)
            t1, t2 = st.tabs([f":material/event: Upcoming ({len(upcoming)})", f":material/scoreboard: Results ({len(results)})"])
            with t1:
                if upcoming.empty:
                    ui.note("No fixtures in the next 10 days.")
                else:
                    st.markdown(_fixture_rows(upcoming, form, with_edge=True), unsafe_allow_html=True)
                    st.write("")
                    ui.note("Click any match to open its match centre: probable line-ups, form and the attacking "
                            "edge explained.")
                    ui.callout("<b>Attacking edge</b> is the model's probability that each side shows the more attacking "
                               "style (xG, shots, deep completions, box shots and possession) in that match, based on its "
                               "2026/27 season-to-date and last-five-match profile plus home advantage. It does <b>not</b> "
                               "predict the winner or the score, and is not intended for betting. For Champions League ties between "
                               "two of our clubs it uses each side's domestic form, so treat it as a rougher guide.")
            with t2:
                if results.empty:
                    ui.note("No results in the last 7 days.")
                else:
                    recent = results.assign(local_day=results.local.dt.date)
                    st.markdown(_fixture_rows(recent.sort_values("kickoff"), form, with_edge=False),
                                unsafe_allow_html=True)
    with right:
        ui.section("Latest news")
        _news(nw, limit=9)

