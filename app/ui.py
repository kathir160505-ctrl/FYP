"""Shared visual components: design tokens (CSS), page header, KPI cards, panels, badges, club header."""
import html
import re
from contextlib import contextmanager
from itertools import count

import streamlit as st

from data import CLUSTER_COLORS

_panel_ids = count()

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&display=swap');
:root {
  --bg: #F2F3F5; --surface: #FFFFFF; --surface-2: #F7F8FA; --border: #E1E4E8; --border-strong: #CDD2D9;
  --ink: #0B0D10; --text: #1F2329; --muted: #5B6472; --faint: #8A93A0; --accent: #D50000;
  --up: #15803D; --down: #B91C1C; --cond: 'Barlow Condensed', 'Arial Narrow', sans-serif;
}
html, body, [class*="css"] { font-feature-settings: "tnum" 1; }
.block-container { padding-top: 4.6rem; padding-bottom: 3rem; max-width: 1360px; }
[data-testid="stHeader"] { background: var(--surface); border-bottom: 1px solid var(--border); }
[data-testid="stDecoration"] { display: none; }
h1, h2, h3, h4 { letter-spacing: 0; color: var(--ink); }

/* Top navigation */
[data-testid="stTopNavLink"] p, [data-testid="stTopNavLink"] span { font-weight: 600; }

/* Page header */
.page-head { display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; padding: 0.4rem 0 0.9rem 0;
  margin-bottom: 1.1rem; border-bottom: 3px solid var(--ink); }
.page-head .eyebrow { color: var(--accent); font-size: 0.74rem; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase; }
.page-head h1 { font-family: var(--cond); font-size: 2.35rem; font-weight: 800; color: var(--ink); margin: 0.1rem 0 0.25rem 0;
  padding: 0; line-height: 1.05; text-transform: uppercase; }
.page-head p { color: var(--muted); font-size: 0.93rem; margin: 0; max-width: 820px; line-height: 1.5; }
.page-head .meta { text-align:right; color: var(--muted); font-size: 0.8rem; white-space: nowrap; line-height: 1.5; }
.page-head .meta b { color: var(--ink); }

/* KPI cards */
.kpi-row { display:grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr)); gap: 0.65rem; margin-bottom: 1rem; }
@media (max-width: 1100px) { .kpi-row { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kpi { position:relative; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 0.8rem 0.95rem 0.75rem 0.95rem;
  border-top: 3px solid var(--kpi-accent, var(--ink)); }
.kpi .label { color: var(--muted); font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
.kpi .value { font-family: var(--cond); color: var(--ink); font-size: 2rem; font-weight: 800; line-height: 1.1; margin-top: 0.15rem; }
.kpi .sub { color: var(--faint); font-size: 0.75rem; margin-top: 0.05rem; }

/* Panels (st.container(border=True, key="panel-…")) */
[class*="st-key-panel-"] { background: var(--surface); border-color: var(--border) !important; border-radius: 8px !important; }
.panel-head { margin: -0.15rem 0 0.45rem 0; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
.panel-title { font-family: var(--cond); color: var(--ink); font-size: 1.2rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.01em; }
.panel-sub { color: var(--muted); font-size: 0.8rem; margin-top: 0.05rem; }
.section-title { font-family: var(--cond); font-size: 1.45rem; font-weight: 800; text-transform: uppercase; color: var(--ink);
  margin: 1rem 0 0.6rem 0; display:flex; align-items:center; gap: 0.5rem; }
.section-title::before { content:""; width: 5px; height: 1.2rem; background: var(--accent); display:inline-block; }

/* Cards */
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 0.95rem 1.05rem; height: 100%; }
.card h4 { font-family: var(--cond); margin: 0 0 0.3rem 0; font-size: 1.25rem; color: var(--ink); font-weight: 800; text-transform: uppercase; line-height: 1.1; }
.card p { color: var(--muted); font-size: 0.85rem; margin: 0 0 0.6rem 0; line-height: 1.5; }
.style-card { border-top: 4px solid var(--c); }
.style-card .count { font-family: var(--cond); font-size: 2.6rem; font-weight: 800; color: var(--c); line-height: 1; }
.style-card .count span { font-family: Inter, sans-serif; font-size: 0.78rem; color: var(--muted); font-weight: 600; margin-left: 0.35rem; }
.mini-club { display:flex; align-items:center; gap:0.6rem; }
.mini-club img { width: 38px; height: 38px; object-fit: contain; }

/* Chips and badges */
.chip { display:inline-block; padding: 0.14rem 0.5rem; border-radius: 4px; font-size: 0.72rem; font-weight: 700;
  margin: 0 0.3rem 0.3rem 0; border: 1px solid var(--border); color: var(--text); background: var(--surface-2); }
.chip.up { color: var(--up); border-color: #BBE5C8; background: #EFFAF2; }
.chip.down { color: var(--down); border-color: #F3C7C7; background: #FDF2F2; }
.badge { display:inline-flex; align-items:center; gap:0.4rem; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.76rem; font-weight: 700; }
.badge .dot { width: 8px; height: 8px; border-radius: 2px; background: currentColor; }
.live { display:inline-flex; align-items:center; gap:0.35rem; color: var(--accent); font-weight: 800; font-size: 0.72rem;
  letter-spacing: 0.1em; text-transform: uppercase; }
.live::before { content:""; width:8px; height:8px; border-radius:50%; background: var(--accent); animation: pulse 1.6s infinite; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.35; } 100% { opacity: 1; } }

/* Club header */
.club-head { display:grid; grid-template-columns: auto 1fr auto; gap: 1.2rem; align-items:center; padding: 1.1rem 1.3rem;
  border-radius: 8px; background: var(--surface); border: 1px solid var(--border); border-top: 6px solid var(--club); margin-bottom: 1rem; }
.club-head img { width: 82px; height: 82px; object-fit: contain; }
.club-head .name { font-family: var(--cond); font-size: 2.4rem; font-weight: 800; color: var(--ink); line-height: 1; text-transform: uppercase; }
.club-head .meta { color: var(--muted); font-size: 0.88rem; margin: 0.35rem 0 0.55rem 0; }
.club-head .stats { display:grid; grid-template-columns: repeat(3, auto); gap: 0 1.8rem; text-align:right; }
.club-head .stats .v { font-family: var(--cond); font-size: 2.1rem; font-weight: 800; color: var(--ink); line-height: 1.05; }
.club-head .stats .l { font-size: 0.68rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; }

/* Trait list */
.trait { display:flex; align-items:center; justify-content:space-between; gap: 0.6rem; padding: 0.5rem 0; border-bottom: 1px solid var(--border); }
.trait:last-child { border-bottom: none; }
.trait .n { font-weight: 700; color: var(--ink); font-size: 0.9rem; }
.trait .d { color: var(--muted); font-size: 0.78rem; }
.trait .z { font-family: var(--cond); font-weight: 800; font-size: 1.15rem; min-width: 70px; text-align: right; }

/* Matchday: fixtures and news */
.day-head { font-family: var(--cond); font-weight: 800; font-size: 1.05rem; text-transform: uppercase; color: var(--ink);
  background: var(--surface-2); border: 1px solid var(--border); border-bottom: none; padding: 0.45rem 0.8rem; border-radius: 6px 6px 0 0; margin-top: 0.7rem; }
.fx { display:grid; grid-template-columns: 74px 1fr 92px 1fr 190px; align-items:center; gap: 0.6rem; background: var(--surface);
  border: 1px solid var(--border); border-top: none; padding: 0.6rem 0.8rem; }
.fx:last-child { border-radius: 0 0 6px 6px; }
.fx .lg { font-size: 0.68rem; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.fx .tm { display:flex; align-items:center; gap: 0.5rem; font-weight: 700; color: var(--ink); font-size: 0.92rem; }
.fx .tm.home { justify-content: flex-end; text-align: right; }
.fx .tm img { width: 26px; height: 26px; object-fit: contain; }
.fx .mid { text-align:center; font-family: var(--cond); font-weight: 800; font-size: 1.35rem; color: var(--ink); }
.fx .mid.time { font-size: 1.05rem; color: var(--text); background: var(--surface-2); border-radius: 4px; padding: 0.15rem 0; }
.fx .edge .bar { display:flex; height: 8px; border-radius: 2px; overflow:hidden; background: var(--surface-2); }
.fx .edge .lbl { display:flex; justify-content:space-between; font-size: 0.72rem; font-weight: 700; color: var(--text); margin-top: 0.25rem; }
.fx .edge .cap { font-size: 0.64rem; color: var(--faint); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; margin-bottom: 0.2rem; }
.news { display:grid; grid-template-columns: 96px 1fr; gap: 0.75rem; padding: 0.7rem 0; border-bottom: 1px solid var(--border); }
.news:last-child { border-bottom: none; }
.news img { width: 96px; height: 64px; object-fit: cover; border-radius: 4px; background: var(--surface-2); }
.news a { color: var(--ink); text-decoration: none; font-weight: 700; font-size: 0.9rem; line-height: 1.3; }
.news a:hover { color: var(--accent); }
.news .when { color: var(--faint); font-size: 0.72rem; margin-top: 0.25rem; font-weight: 600; }
.news .tag { color: var(--accent); font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; }
.news.lead { grid-template-columns: 1fr; }
.news.lead img { width: 100%; height: 190px; }
.news.lead a { font-family: var(--cond); font-size: 1.45rem; font-weight: 800; text-transform: uppercase; line-height: 1.1; }
.news.lead .desc { color: var(--muted); font-size: 0.84rem; margin-top: 0.3rem; line-height: 1.45; }
@media (max-width: 760px) {
  .fx { grid-template-columns: 1fr 70px 1fr; }
  .fx .lg, .fx .edge { grid-column: 1 / -1; }
}

/* Misc */
.note { color: var(--faint); font-size: 0.78rem; line-height: 1.5; }
.callout { border: 1px solid var(--border); border-left: 4px solid var(--ink); background: var(--surface-2);
  padding: 0.7rem 0.95rem; border-radius: 4px; color: var(--text); font-size: 0.86rem; margin: 0.3rem 0 0.8rem 0; line-height: 1.55; }
.callout.warn { border-left-color: #D97706; background: #FFFBEB; }
.prob-head { text-align:center; }
.prob-head .k { color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; }
.prob-head .v { font-family: var(--cond); color: var(--ink); font-size: 2.1rem; font-weight: 800; margin: 0.15rem 0 0.05rem 0; text-transform: uppercase; }
.vs-card { text-align:center; padding: 1rem 0.8rem; }
.vs-card img { width: 72px; height: 72px; object-fit: contain; margin: 0.3rem 0 0.4rem 0; }
.stTabs [data-baseweb="tab-list"] { gap: 0.2rem; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { padding: 0.55rem 0.9rem; color: var(--muted); font-weight: 600; }
.stTabs [aria-selected="true"] { color: var(--ink) !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--accent) !important; height: 3px; }
.foot { margin-top: 2.2rem; padding-top: 0.9rem; border-top: 1px solid var(--border-strong); color: var(--faint); font-size: 0.76rem; line-height: 1.6; }
@media (max-width: 760px) {
  .page-head { flex-direction: column; align-items: flex-start; }
  .page-head .meta { text-align:left; }
  .club-head { grid-template-columns: auto 1fr; }
  .club-head .stats { grid-column: 1 / -1; text-align:left; }
}
a.fx { text-decoration: none !important; color: inherit; cursor: pointer; transition: background .12s; }
a.fx:hover { background: #FFF5F5; }
a.fx:hover .mc { color: var(--accent); }
.fx .mc { font-size: 0.64rem; color: var(--faint); font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
/* Match centre */
.sc { background: var(--surface); border: 1px solid var(--border); border-top: 3px solid var(--accent); border-radius: 8px;
  padding: 0.9rem 1.2rem 1.1rem; margin-bottom: 0.9rem; }
.sc-meta { text-align:center; color: var(--muted); font-size: 0.82rem; margin-bottom: 0.5rem; }
.sc-row { display:grid; grid-template-columns: 1fr auto 1fr; align-items:center; gap: 1.4rem; }
.sc-team { display:flex; align-items:center; gap: 0.8rem; font-family: var(--cond); font-weight: 800; font-size: 2rem;
  text-transform: uppercase; color: var(--ink); line-height: 1; }
.sc-team.home { justify-content: flex-end; text-align: right; }
.sc-team img { width: 64px; height: 64px; object-fit: contain; }
.sc-mid { text-align: center; min-width: 140px; }
.sc-score { font-family: var(--cond); font-weight: 800; font-size: 3rem; color: var(--ink); line-height: 1; }
.sc-status { color: var(--muted); font-size: 0.8rem; font-weight: 600; margin-top: .25rem; }
.evs { display:flex; flex-direction:column; gap: 0.3rem; }
.ev { display:flex; align-items:center; gap: 0.5rem; font-size: 0.86rem; padding: 0.3rem 0.5rem; border-radius: 4px; background: var(--surface-2); }
.ev.away { flex-direction: row-reverse; text-align: right; }
.ev-min { font-weight: 800; color: var(--muted); min-width: 2.8rem; font-variant-numeric: tabular-nums; }
.ev.away .ev-min { text-align: right; }
.ev-who { font-weight: 700; color: var(--ink); }
.ev-sub { color: var(--muted); font-size: 0.8rem; }
.form-row { display:flex; align-items:center; gap: .35rem; margin: .3rem 0; }
.form-row b { min-width: 9.5rem; }
.fchip { display:inline-flex; width: 1.6rem; height: 1.6rem; align-items:center; justify-content:center; border-radius: 4px;
  color: #fff; font-weight: 800; font-size: .78rem; cursor: default; }
.fchip.W { background: #16A34A; } .fchip.D { background: #9CA3AF; } .fchip.L { background: #DC2626; }
.vids { display:flex; flex-direction:column; gap: .45rem; }
.vids a { font-weight: 700; color: var(--accent); text-decoration: none; }
/* Match centre: pitch */
.pitch { position: relative; width: 100%; max-width: 620px; margin: 0 auto; aspect-ratio: 68 / 100; border-radius: 6px;
  background: repeating-linear-gradient(180deg, #2E7D4F 0 7.14%, #2A7449 7.14% 14.28%); overflow: hidden; }
.pitch-lines { position: absolute; inset: 3%; border: 2px solid rgba(255,255,255,.7); }
.pitch-lines i { position: absolute; display: block; border: 2px solid rgba(255,255,255,.7); }
.pitch-lines .half { left: 0; right: 0; top: 50%; height: 0; border-width: 2px 0 0 0; }
.pitch-lines .circle { left: 50%; top: 50%; width: 26%; aspect-ratio: 1; border-radius: 50%; transform: translate(-50%, -50%); }
.pitch-lines .spot { left: 50%; top: 50%; width: 5px; height: 5px; border-radius: 50%; background: rgba(255,255,255,.8);
  border: none; transform: translate(-50%, -50%); }
.pitch-lines .box { left: 20%; width: 60%; height: 16%; }
.pitch-lines .six { left: 36%; width: 28%; height: 5.5%; }
.pitch-lines .top { top: -2px; border-top: none; } .pitch-lines .bottom { bottom: -2px; border-bottom: none; }
.pl { position: absolute; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center;
  width: 112px; cursor: default; }
.pl-num { position: relative; width: 34px; height: 34px; border-radius: 50%; border: 2px solid #fff; color: #fff;
  display: flex; align-items: center; justify-content: center; font: 800 15px var(--cond); box-shadow: 0 1px 3px rgba(0,0,0,.35); }
.pl-ev { position: absolute; left: 30px; top: -9px; display: flex; gap: 1px; background: #fff; border-radius: 9px;
  padding: 1px 3px; box-shadow: 0 1px 2px rgba(0,0,0,.3); }
.pl-off { position: absolute; right: 30px; top: -9px; display: flex; align-items: center; gap: 1px; background: #fff;
  border-radius: 9px; padding: 1px 4px 1px 2px; font: 700 10px Inter, sans-serif; color: #B91C1C;
  box-shadow: 0 1px 2px rgba(0,0,0,.3); white-space: nowrap; }
.pl-name { margin-top: 3px; padding: 1px 6px; border-radius: 3px; background: rgba(8, 20, 14, .72); color: #fff;
  font: 600 11.5px Inter, sans-serif; white-space: nowrap; max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
.ico { flex: none; vertical-align: -2px; }
/* Match centre: benches */
.bench { padding: .65rem 0 .2rem; border-top: 1px solid var(--border); margin-top: .6rem; }
.bench-head { display: flex; align-items: center; gap: .45rem; margin-bottom: .45rem; font-size: .9rem; }
.bench-head img { width: 20px; height: 20px; object-fit: contain; }
.bench-head span { color: var(--muted); font-size: .8rem; }
.sub-row { display: flex; flex-wrap: wrap; gap: .35rem; }
.sub-chip { display: inline-flex; align-items: center; gap: .3rem; background: var(--surface-2); border: 1px solid var(--border);
  border-radius: 14px; padding: .18rem .6rem .18rem .4rem; font-size: .82rem; color: var(--ink); }
.sub-chip b { color: #15803D; font-weight: 700; }
.unused { margin-top: .45rem; color: var(--muted); font-size: .8rem; line-height: 1.5; }
.unused span { font-weight: 700; color: var(--text); text-transform: uppercase; font-size: .7rem; letter-spacing: .05em; margin-right: .3rem; }
.muted { color: var(--muted); font-size: .85rem; }
/* Match centre: stats */
.stats { display: flex; flex-direction: column; gap: .55rem; }
.st-top { display: grid; grid-template-columns: 70px 1fr 70px; align-items: baseline; font-size: .95rem; color: var(--text);
  font-variant-numeric: tabular-nums; }
.st-top span:first-child { text-align: left; } .st-top span:last-child { text-align: right; }
.st-top .hi { font-weight: 800; color: var(--ink); }
.st-l { text-align: center; color: var(--muted); font-size: .82rem; font-weight: 600; }
.st-bar { display: flex; gap: 3px; height: 6px; margin-top: .2rem; }
.st-bar i { display: block; height: 100%; border-radius: 3px; }
/* Match centre: timeline */
.tl-head { display: flex; justify-content: space-between; font: 800 1rem var(--cond); text-transform: uppercase;
  color: var(--ink); padding-bottom: .5rem; border-bottom: 1px solid var(--border); margin-bottom: .4rem; }
.tl-head span { display: flex; align-items: center; gap: .4rem; }
.tl-head img { width: 22px; height: 22px; object-fit: contain; }
.tl-row { display: grid; grid-template-columns: 1fr 54px 1fr; align-items: center; min-height: 34px; }
.tl-min { text-align: center; font: 700 .8rem Inter, sans-serif; color: var(--muted); font-variant-numeric: tabular-nums; }
.tl-cell { font-size: .86rem; padding: .25rem .45rem; border-radius: 5px; }
.tl-row > .tl-cell:first-child { text-align: right; } .tl-row > .tl-cell:first-child .tl-main,
.tl-row > .tl-cell:first-child .tl-sub { justify-content: flex-end; }
.tl-cell.goal { background: #F0FDF4; }
.tl-main { display: flex; align-items: center; gap: .35rem; font-weight: 700; color: var(--ink); }
.tl-sub { display: flex; align-items: center; gap: .3rem; color: var(--muted); font-size: .8rem; margin-top: 1px; }
.tl-score { font: 800 .82rem var(--cond); background: var(--ink); color: #fff; border-radius: 3px; padding: 0 .35rem; }
.tl-div { text-align: center; font: 700 .72rem Inter, sans-serif; text-transform: uppercase; letter-spacing: .08em;
  color: var(--muted); border-top: 1px dashed var(--border-strong); margin: .45rem 0 .2rem; padding-top: .3rem; }
/* Match centre: scorers and team news */
.sc-scorers { display: grid; grid-template-columns: 1fr auto 1fr; gap: 1.4rem; margin-top: .55rem; font-size: .82rem; color: var(--muted); }
.sc-scorers div:first-child { text-align: right; } .sc-scorers .mid { min-width: 140px; text-align: center; }
.tn { margin-bottom: .7rem; } .tn b { display: block; margin-bottom: .2rem; }
.tn .row { display: flex; gap: .4rem; align-items: baseline; font-size: .84rem; margin: .15rem 0; color: var(--text); }
.tn .tag { font-size: .66rem; font-weight: 800; text-transform: uppercase; letter-spacing: .05em; border-radius: 3px;
  padding: .05rem .35rem; white-space: nowrap; }
.tn .tag.inj { background: #FEE2E2; color: #991B1B; } .tn .tag.sus { background: #FEF3C7; color: #92400E; }
.tn .tag.out { background: var(--surface-2); color: var(--muted); border: 1px solid var(--border); }
a.pl { text-decoration: none !important; cursor: pointer; }
a.pl:hover .pl-num { transform: scale(1.12); box-shadow: 0 0 0 3px rgba(255,255,255,.55); }
a.pl:hover .pl-name { background: #fff; color: #0B0D10; }
.pl-num { transition: transform .12s; }
.sub-chip a, .unused a { color: inherit; text-decoration: none; border-bottom: 1px dotted var(--faint); }
.sub-chip a:hover, .unused a:hover { color: var(--accent); }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, text: str, meta: str = "") -> None:
    meta_html = f'<div class="meta">{meta}</div>' if meta else ""
    st.markdown(f'<div class="page-head"><div><div class="eyebrow">{eyebrow}</div><h1>{title}</h1>'
                f'<p>{text}</p></div>{meta_html}</div>', unsafe_allow_html=True)


def kpis(items: list[tuple]) -> None:
    """items: (label, value, sub) or (label, value, sub, accent_hex)."""
    cells = []
    for item in items:
        label, value, sub = item[:3]
        accent = f' style="--kpi-accent:{item[3]}"' if len(item) > 3 else ""
        cells.append(f'<div class="kpi"{accent}><div class="label">{label}</div><div class="value">{value}</div>'
                     f'<div class="sub">{sub}</div></div>')
    st.markdown(f'<div class="kpi-row" style="--n:{len(cells)}">{"".join(cells)}</div>', unsafe_allow_html=True)


@contextmanager
def panel(title: str = "", subtitle: str = ""):
    """A framed surface for a chart or table, with an optional title row."""
    key = f"panel-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or 'x'}-{next(_panel_ids)}"
    with st.container(border=True, key=key):
        if title:
            sub = f'<div class="panel-sub">{subtitle}</div>' if subtitle else ""
            st.markdown(f'<div class="panel-head"><div class="panel-title">{title}</div>{sub}</div>',
                        unsafe_allow_html=True)
        yield


def section(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def cluster_badge(cluster: str) -> str:
    c = CLUSTER_COLORS[cluster]
    return (f'<span class="badge" style="background:{c}14;color:{c};border:1px solid {c}40">'
            f'<span class="dot"></span>{html.escape(cluster)}</span>')


def unique_badge() -> str:
    return ('<span class="badge" style="background:#FEF3C7;color:#92400E;border:1px solid #FCD34D" '
            'title="Flagged as a density outlier by DBSCAN in most settings"><span class="dot"></span>Statistically unique</span>')


def club_header(row) -> None:
    badges = cluster_badge(row.cluster) + (" " + unique_badge() if row.dbscan_outlier else "")
    st.markdown(
        f'''<div class="club-head" style="--club:{row.color}">
        <img src="{row.logo}" alt="">
        <div><div class="name">{html.escape(row.team)}</div>
        <div class="meta">{row.league_name} 2025/26 · finished {ordinal(row.position)} · {row.W}W {row.D}D {row.L}L</div>
        <div>{badges}</div></div>
        <div class="stats">
          <div><div class="v">{row.Pts}</div><div class="l">Points</div></div>
          <div><div class="v">{row.GF - row.GA:+d}</div><div class="l">Goal diff</div></div>
          <div><div class="v">{row.xG_total:.1f}</div><div class="l">Season xG</div></div>
        </div></div>''',
        unsafe_allow_html=True)


def traits(rows: list[tuple[str, str, float]]) -> None:
    """rows: (name, detail, z-score)."""
    out = []
    for name, detail, z in rows:
        color = "var(--up)" if z > 0 else "var(--down)"
        out.append(f'<div class="trait"><div><div class="n">{name}</div><div class="d">{detail}</div></div>'
                   f'<div class="z" style="color:{color}">{z:+.1f} SD</div></div>')
    st.markdown("".join(out), unsafe_allow_html=True)


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def callout(text: str, warn: bool = False) -> None:
    st.markdown(f'<div class="callout{" warn" if warn else ""}">{text}</div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="note">{text}</div>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        '<div class="foot">Data: Understat and ESPN (FBref cross-check). Style analysis covers the 2025/26 Premier League, '
        "La Liga and Serie A seasons. Attacking profiles are a data-driven abstraction of "
        "attacking play only, not a full description of a team's tactics. Predictions are probabilistic estimates of "
        "attacking style, not match results, and are not intended for betting.</div>", unsafe_allow_html=True)


def player_header(p, crest: str | None, color: str) -> None:
    """Player identity card: Commons photo (or initials), name, club, position and key facts."""
    if isinstance(p.photo, str) and p.photo:
        face = (f'<img src="{html.escape(p.photo)}" alt="" style="width:96px;height:96px;border-radius:50%;'
                f'object-fit:cover;object-position:top;border:3px solid {color};background:#E5E7EB">')
    else:
        from data import initials
        face = (f'<div style="width:96px;height:96px;border-radius:50%;background:{color};color:#fff;display:flex;'
                f'align-items:center;justify-content:center;font:800 2.2rem var(--cond)">{initials(p["name"])}</div>')
    crest_img = f'<img src="{html.escape(crest)}" alt="" style="width:22px;height:22px;vertical-align:-5px">' if crest else ""
    facts = [f for f in (
        p.group,
        f"#{p.jersey}" if isinstance(p.jersey, str) and p.jersey else "",
        f"Age {int(p.age)}" if p.age == p.age else "",
        str(p.nation).split()[-1].upper() if isinstance(p.nation, str) else "") if f]
    st.markdown(
        f'''<div class="club-head" style="--club:{color}">{face}
        <div><div class="name">{html.escape(p["name"])}</div>
        <div class="meta">{crest_img} {html.escape(p.team)} · {html.escape(p.league_name)} {p.season_label}</div>
        <div class="meta">{" · ".join(html.escape(f) for f in facts)}</div></div>
        <div class="stats">
          <div><div class="v">{int(p.minutes):,}</div><div class="l">Minutes</div></div>
          <div><div class="v">{int(p.goals)}</div><div class="l">Goals</div></div>
          <div><div class="v">{int(p.assists)}</div><div class="l">Assists</div></div>
        </div></div>''', unsafe_allow_html=True)
