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
:root {
  --bg: #0A0F1C; --surface: #111827; --surface-2: #162033; --border: #1F2937; --border-strong: #2B3648;
  --text: #E5E9F2; --text-strong: #F8FAFC; --muted: #8A94A8; --faint: #5B6578; --accent: #3B82F6; --accent-2: #38BDF8;
}
html, body, [class*="css"] { font-feature-settings: "tnum" 1, "cv11" 1; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1400px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
h1, h2, h3, h4 { letter-spacing: -0.015em; }
hr { border-color: var(--border) !important; }

/* Sidebar */
[data-testid="stSidebar"] { border-right: 1px solid var(--border); }
[data-testid="stSidebarNav"] a { border-radius: 8px; }
[data-testid="stSidebarNav"] a span { font-size: 0.9rem; }
[data-testid="stSidebarNavSeparator"] { border-color: var(--border); }
.side-meta { color: var(--muted); font-size: 0.78rem; line-height: 1.55; }
.side-meta b { color: var(--text); font-weight: 600; }
.side-pill { display:inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; border:1px solid var(--border-strong);
  color: var(--text); font-size: 0.72rem; font-weight: 600; margin: 0 0.25rem 0.35rem 0; background: var(--surface-2); }

/* Page header */
.page-head { display:flex; align-items:flex-end; justify-content:space-between; gap:1rem;
  padding: 0.2rem 0 1.1rem 0; margin-bottom: 1.2rem; border-bottom: 1px solid var(--border); }
.page-head .eyebrow { color: var(--accent-2); font-size: 0.72rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }
.page-head h1 { font-size: 1.75rem; font-weight: 800; color: var(--text-strong); margin: 0.25rem 0 0.3rem 0; padding: 0; line-height: 1.2; }
.page-head p { color: var(--muted); font-size: 0.93rem; margin: 0; max-width: 820px; line-height: 1.5; }
.page-head .meta { text-align:right; color: var(--muted); font-size: 0.78rem; white-space: nowrap; }
.page-head .meta b { color: var(--text); }

/* KPI cards */
.kpi-row { display:grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr)); gap: 0.75rem; margin-bottom: 1.1rem; }
@media (max-width: 1100px) { .kpi-row { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kpi { position:relative; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 0.85rem 1rem 0.8rem 1rem; overflow:hidden; }
.kpi::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background: var(--kpi-accent, var(--accent)); }
.kpi .label { color: var(--muted); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; }
.kpi .value { color: var(--text-strong); font-size: 1.55rem; font-weight: 750; line-height: 1.25; margin-top: 0.2rem; }
.kpi .sub { color: var(--faint); font-size: 0.76rem; margin-top: 0.1rem; }

/* Panels (st.container(border=True, key="panel-…")) */
[class*="st-key-panel-"] { background: var(--surface); border-color: var(--border) !important; border-radius: 14px !important; }
.panel-head { margin: -0.1rem 0 0.4rem 0; }
.panel-title { color: var(--text-strong); font-size: 1rem; font-weight: 700; }
.panel-sub { color: var(--muted); font-size: 0.8rem; margin-top: 0.1rem; }

/* Cards */
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 1rem 1.1rem; height: 100%; }
.card h4 { margin: 0 0 0.35rem 0; font-size: 1rem; color: var(--text-strong); font-weight: 700; }
.card p { color: var(--muted); font-size: 0.85rem; margin: 0 0 0.6rem 0; line-height: 1.5; }
.card .members { color: #C3CAD8; font-size: 0.8rem; line-height: 1.55; }
.style-card { border-top: 3px solid var(--c); }
.style-card .count { font-size: 1.9rem; font-weight: 800; color: var(--c); line-height: 1; }
.style-card .count span { font-size: 0.8rem; color: var(--muted); font-weight: 600; margin-left: 0.3rem; }
.mini-club { display:flex; align-items:center; gap:0.55rem; }
.mini-club img { width: 36px; height: 36px; object-fit: contain; }

/* Chips and badges */
.chip { display:inline-block; padding: 0.16rem 0.55rem; border-radius: 6px; font-size: 0.72rem; font-weight: 600;
  margin: 0 0.3rem 0.3rem 0; border: 1px solid var(--border-strong); color: #C3CAD8; background: var(--surface-2); }
.chip.up { color:#4ADE80; border-color: rgba(74,222,128,0.35); background: rgba(74,222,128,0.07); }
.chip.down { color:#F87171; border-color: rgba(248,113,113,0.35); background: rgba(248,113,113,0.07); }
.badge { display:inline-flex; align-items:center; gap:0.4rem; padding: 0.24rem 0.7rem; border-radius: 999px; font-size: 0.78rem; font-weight: 650; }
.badge .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }

/* Club header */
.club-head { display:grid; grid-template-columns: auto 1fr auto; gap: 1.2rem; align-items:center; padding: 1.1rem 1.3rem;
  border-radius: 16px; background: linear-gradient(100deg, var(--club-tint) 0%, var(--surface) 42%); border: 1px solid var(--border); margin-bottom: 1rem; }
.club-head img { width: 78px; height: 78px; object-fit: contain; filter: drop-shadow(0 6px 14px rgba(0,0,0,0.45)); }
.club-head .name { font-size: 1.75rem; font-weight: 800; color: var(--text-strong); line-height: 1.1; }
.club-head .meta { color: var(--muted); font-size: 0.88rem; margin: 0.3rem 0 0.55rem 0; }
.club-head .stats { display:grid; grid-template-columns: repeat(3, auto); gap: 0 1.6rem; text-align:right; }
.club-head .stats .v { font-size: 1.45rem; font-weight: 800; color: var(--text-strong); line-height: 1.2; }
.club-head .stats .l { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; }

/* Trait list */
.trait { display:flex; align-items:baseline; justify-content:space-between; gap: 0.6rem; padding: 0.45rem 0; border-bottom: 1px solid var(--border); }
.trait:last-child { border-bottom: none; }
.trait .n { font-weight: 650; color: var(--text); font-size: 0.9rem; }
.trait .d { color: var(--muted); font-size: 0.78rem; text-align:right; }
.trait .z { font-weight: 700; font-size: 0.85rem; min-width: 64px; text-align: right; }

/* Misc */
.note { color: var(--faint); font-size: 0.78rem; line-height: 1.5; }
.callout { border: 1px solid var(--border); border-left: 3px solid var(--accent); background: rgba(59,130,246,0.06);
  padding: 0.7rem 0.95rem; border-radius: 10px; color: #C3CAD8; font-size: 0.86rem; margin: 0.3rem 0 0.8rem 0; line-height: 1.55; }
.callout.warn { border-left-color: #F59E0B; background: rgba(245,158,11,0.06); }
.prob-head { text-align:center; }
.prob-head .k { color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }
.prob-head .v { color: var(--text-strong); font-size: 1.6rem; font-weight: 800; margin: 0.2rem 0 0.1rem 0; }
.vs-card { text-align:center; padding: 1.1rem 0.8rem; }
.vs-card img { width: 72px; height: 72px; object-fit: contain; margin: 0.3rem 0 0.4rem 0; }
.stTabs [data-baseweb="tab-list"] { gap: 0.25rem; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { padding: 0.55rem 0.9rem; border-radius: 8px 8px 0 0; color: var(--muted); }
.stTabs [aria-selected="true"] { color: var(--text-strong) !important; background: var(--surface); }
[data-testid="stMetric"] { background: var(--surface); }
.foot { margin-top: 2.2rem; padding-top: 0.9rem; border-top: 1px solid var(--border); color: var(--faint); font-size: 0.76rem; line-height: 1.6; }
@media (max-width: 760px) {
  .page-head { flex-direction: column; align-items: flex-start; }
  .page-head .meta { text-align:left; }
  .club-head { grid-template-columns: auto 1fr; }
  .club-head .stats { grid-column: 1 / -1; text-align:left; }
}
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


def cluster_badge(cluster: str) -> str:
    c = CLUSTER_COLORS[cluster]
    return (f'<span class="badge" style="background:{c}1F;color:{c};border:1px solid {c}55">'
            f'<span class="dot"></span>{html.escape(cluster)}</span>')


def unique_badge() -> str:
    return ('<span class="badge" style="background:#FACC151A;color:#FACC15;border:1px solid #FACC1555" '
            'title="Flagged as a density outlier by DBSCAN in most settings"><span class="dot"></span>Statistically unique</span>')


def _tint(hex_color: str, alpha: float = 0.22) -> str:
    c = hex_color.lstrip("#")
    return f"rgba({int(c[0:2], 16)},{int(c[2:4], 16)},{int(c[4:6], 16)},{alpha})"


def club_header(row) -> None:
    badges = cluster_badge(row.cluster) + (" " + unique_badge() if row.dbscan_outlier else "")
    st.markdown(
        f'''<div class="club-head" style="--club-tint:{_tint(row.color)}">
        <img src="{row.logo}" alt="">
        <div><div class="name">{html.escape(row.team)}</div>
        <div class="meta">{row.league_name} · finished {ordinal(row.position)} · {row.W}W {row.D}D {row.L}L</div>
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
        color = "#4ADE80" if z > 0 else "#F87171"
        out.append(f'<div class="trait"><div><div class="n">{name}</div><div class="d" style="text-align:left">{detail}</div></div>'
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
        '<div class="foot">Data: Understat and ESPN (FBref cross-check) · Premier League, La Liga, Serie A 2025/26. '
        "Attacking profiles are a data-driven abstraction of attacking play only, not a full description of a team's "
        "tactics. Predictions are probabilistic estimates of attacking style, not match results, and are not intended "
        "for betting.</div>", unsafe_allow_html=True)
