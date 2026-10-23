"""Shared visual components: CSS, hero, KPI cards, club header, badges."""
import html

import streamlit as st

from data import CLUSTER_COLORS, CLUSTER_ICONS, LEAGUE_FLAGS

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 2.2rem; max-width: 1350px; }
h1, h2, h3 { letter-spacing: -0.02em; }
[data-testid="stSidebar"] { background: #0d1426; border-right: 1px solid #1e293b; }

.hero { padding: 1.6rem 1.8rem; border-radius: 18px; margin-bottom: 1.2rem;
  background: radial-gradient(1200px 300px at 10% -20%, rgba(56,189,248,0.25), transparent),
              radial-gradient(800px 260px at 95% 0%, rgba(167,139,250,0.22), transparent), #111a2e;
  border: 1px solid #1e293b; }
.hero .eyebrow { color: #38bdf8; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.14em; text-transform: uppercase; }
.hero h1 { margin: 0.25rem 0 0.4rem 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; }
.hero p { color: #94a3b8; margin: 0; font-size: 1rem; max-width: 900px; }

.kpi { background: #111a2e; border: 1px solid #1e293b; border-radius: 14px; padding: 0.9rem 1rem; height: 100%; }
.kpi .label { color: #94a3b8; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi .value { color: #f8fafc; font-size: 1.6rem; font-weight: 800; line-height: 1.25; }
.kpi .sub { color: #64748b; font-size: 0.78rem; }

.card { background: #111a2e; border: 1px solid #1e293b; border-radius: 16px; padding: 1.1rem 1.2rem; height: 100%; }
.card h4 { margin: 0 0 0.35rem 0; font-size: 1.05rem; color: #f1f5f9; }
.card p { color: #94a3b8; font-size: 0.86rem; margin: 0 0 0.6rem 0; }
.card .members { color: #cbd5e1; font-size: 0.8rem; line-height: 1.5; }

.chip { display: inline-block; padding: 0.18rem 0.6rem; border-radius: 999px; font-size: 0.74rem; font-weight: 600;
  margin: 0 0.3rem 0.3rem 0; border: 1px solid #334155; color: #cbd5e1; background: #0f172a; }
.badge { display: inline-block; padding: 0.28rem 0.75rem; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }

.club-head { display: flex; align-items: center; gap: 1.1rem; padding: 1.1rem 1.3rem; border-radius: 18px;
  background: #111a2e; border: 1px solid #1e293b; margin-bottom: 1rem; }
.club-head img { width: 76px; height: 76px; object-fit: contain; filter: drop-shadow(0 4px 12px rgba(0,0,0,0.5)); }
.club-head .name { font-size: 1.8rem; font-weight: 800; color: #f8fafc; line-height: 1.1; }
.club-head .meta { color: #94a3b8; font-size: 0.9rem; margin-top: 0.2rem; }
.club-head .right { margin-left: auto; text-align: right; }

.note { color: #64748b; font-size: 0.8rem; }
.callout { border-left: 3px solid #38bdf8; background: rgba(56,189,248,0.07); padding: 0.75rem 1rem;
  border-radius: 0 10px 10px 0; color: #cbd5e1; font-size: 0.88rem; margin: 0.4rem 0 0.8rem 0; }
.callout.warn { border-color: #f59e0b; background: rgba(245,158,11,0.07); }
.section-title { font-size: 1.15rem; font-weight: 700; color: #f1f5f9; margin: 1.2rem 0 0.4rem 0; }
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; }
.stTabs [data-baseweb="tab"] { background: #111a2e; border-radius: 10px 10px 0 0; padding: 0.5rem 1rem; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(eyebrow: str, title: str, text: str) -> None:
    st.markdown(f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{text}</p></div>',
                unsafe_allow_html=True)


def kpis(items: list[tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, sub) in zip(cols, items):
        col.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div>'
                     f'<div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def cluster_badge(cluster: str) -> str:
    c = CLUSTER_COLORS[cluster]
    return (f'<span class="badge" style="background:{c}22;color:{c};border:1px solid {c}66">'
            f'{CLUSTER_ICONS[cluster]} {html.escape(cluster)}</span>')


def unique_badge() -> str:
    return ('<span class="badge" style="background:#facc1522;color:#facc15;border:1px solid #facc1566" '
            'title="Flagged as a density outlier by DBSCAN in most settings">★ Statistically unique</span>')


def club_header(row) -> None:
    badges = cluster_badge(row.cluster) + (" " + unique_badge() if row.dbscan_outlier else "")
    st.markdown(
        f'''<div class="club-head" style="border-left: 6px solid {row.color}">
        <img src="{row.logo}" alt="">
        <div><div class="name">{html.escape(row.team)}</div>
        <div class="meta">{LEAGUE_FLAGS[row.league_name]} {row.league_name} · finished {ordinal(row.position)} ·
        {row.W}W {row.D}D {row.L}L · {row.Pts} pts · GD {row.GF - row.GA:+d}</div>
        <div style="margin-top:0.5rem">{badges}</div></div>
        <div class="right"><div class="kpi" style="border:none;background:transparent;padding:0">
        <div class="label">Season xG</div><div class="value">{row.xG_total:.1f}</div>
        <div class="sub">{row.GF} goals scored</div></div></div></div>''',
        unsafe_allow_html=True)


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def callout(text: str, warn: bool = False) -> None:
    st.markdown(f'<div class="callout{" warn" if warn else ""}">{text}</div>', unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        '<div class="note" style="margin-top:2rem;border-top:1px solid #1e293b;padding-top:0.8rem">'
        "Data: Understat, ESPN, FBref (cross-check) · 2025/26 season. Attacking profiles are a data-driven "
        "abstraction of attacking play only, not a full description of a team's tactics. Predictions are "
        "probabilistic estimates of attacking style, not match results, and are not intended for betting."
        "</div>", unsafe_allow_html=True)
