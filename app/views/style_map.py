import html

import streamlit as st

import charts
import data
import ui


def render() -> None:
    df = data.clubs()
    cm = data.cluster_model()
    ui.hero("2025/26 · Premier League · La Liga · Serie A",
            "Attacking Philosophies of Europe's Top Three Leagues",
            "Unsupervised machine learning groups all 60 clubs by <b>how</b> they attack, using possession, "
            "passing directness, chance creation, xG, counter-attacks and box presence, with no labels given in advance.")
    ui.kpis([
        ("Clubs", "60", "20 per league"),
        ("Matches", "1,140", "full 2025/26 season"),
        ("Shots analysed", f"{len(data.shots()):,}", "with location and xG"),
        ("Attacking styles", str(df.cluster.nunique()), "discovered by K-means"),
        ("Variance explained", f"{cm['explained_variance'].sum():.0%}", f"by {cm['n_components']} principal components"),
    ])

    ui.section("The style map")
    c1, c2 = st.columns([3, 1])
    with c2:
        leagues = st.pills("Leagues", list(data.LEAGUE_FLAGS), selection_mode="multi",
                           default=list(data.LEAGUE_FLAGS)) or list(data.LEAGUE_FLAGS)
        highlight = st.multiselect("Highlight clubs", data.club_options(df), placeholder="Pick clubs to spotlight")
        st.markdown('<div class="note">Markers: ● Premier League · ◆ La Liga · ■ Serie A.<br>'
                    "Clubs close together attack in similar ways. Distance along the horizontal axis "
                    "reflects attacking dominance, the main source of difference (58% of variance).</div>",
                    unsafe_allow_html=True)
    with c1:
        st.plotly_chart(charts.style_map(df[df.league_name.isin(leagues)], highlight,
                                         tuple(cm["explained_variance"][:2])), width="stretch")

    ui.section("The four attacking philosophies")
    prof = data.profiles()
    z = prof[prof.kind == "z"].set_index("cluster")
    cols = st.columns(4)
    for col, cluster in zip(cols, data.CLUSTER_ORDER):
        members = df[df.cluster == cluster].sort_values("PC1", ascending=False)
        top = z.loc[cluster, data.FEATURES].sort_values(ascending=False)
        chips = "".join(f'<span class="chip">▲ {data.SHORT_LABELS[f]}</span>' for f in top.index[:3] if top[f] > 0.2)
        chips += "".join(f'<span class="chip">▼ {data.SHORT_LABELS[f]}</span>' for f in top.index[-2:] if top[f] < -0.2)
        color = data.CLUSTER_COLORS[cluster]
        col.markdown(
            f'''<div class="card" style="border-top: 4px solid {color}">
            <h4>{data.CLUSTER_ICONS[cluster]} {cluster}</h4>
            <div class="note" style="margin-bottom:0.5rem">{len(members)} clubs ·
            {", ".join(f"{(members.league_name == lg).sum()} {lg}" for lg in data.LEAGUE_FLAGS)}</div>
            <p>{cm["blurbs"][cluster]}</p><div>{chips}</div>
            <div class="members">{", ".join(html.escape(t) for t in members.team)}</div></div>''',
            unsafe_allow_html=True)

    uniq = df[df.dbscan_outlier].sort_values("uniqueness", ascending=False)
    ui.section("★ Statistically unique clubs")
    ui.callout("These clubs sit in sparse regions of the style space. DBSCAN marks them as outliers in most of "
               "24 parameter settings, so their attacking profile has no close peers in any of the three leagues.")
    cols = st.columns(len(uniq))
    for col, row in zip(cols, uniq.itertuples()):
        z_row = (df.set_index("team").loc[row.team, data.FEATURES] - df[data.FEATURES].mean()) / df[data.FEATURES].std()
        extreme = z_row.abs().sort_values(ascending=False).index[:2]
        why = " · ".join(f"{data.SHORT_LABELS[f]} {'+' if z_row[f] > 0 else '−'}{abs(z_row[f]):.1f} SD" for f in extreme)
        col.markdown(f'''<div class="card" style="text-align:center"><img src="{row.logo}" width="52">
            <h4 style="margin-top:0.4rem">{html.escape(row.team)}</h4>
            <div class="note">{row.league_name} · {row.cluster}</div>
            <p style="margin-top:0.4rem">{why}</p>
            <div class="note">outlier in {row.uniqueness:.0%} of settings</div></div>''', unsafe_allow_html=True)
    ui.footer()
