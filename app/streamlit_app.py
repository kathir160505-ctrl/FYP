"""Entry point:  streamlit run app/streamlit_app.py"""
import streamlit as st

st.set_page_config(page_title="Attacking Philosophies · 2025/26", page_icon="⚽", layout="wide")

import ui  # noqa: E402
from views import club_profile, head_to_head, leagues, methodology, style_map  # noqa: E402

ui.inject_css()

pages = [
    st.Page(style_map.render, title="Style Map", icon="🗺️", url_path="style-map", default=True),
    st.Page(club_profile.render, title="Club Profile", icon="🛡️", url_path="club"),
    st.Page(head_to_head.render, title="Head-to-Head", icon="⚔️", url_path="head-to-head"),
    st.Page(leagues.render, title="League Comparison", icon="🌍", url_path="leagues"),
    st.Page(methodology.render, title="Methodology", icon="🔬", url_path="methodology"),
]

with st.sidebar:
    st.markdown("### ⚽ Attacking Philosophies")
    st.markdown('<div class="note">Unsupervised clustering of attacking styles<br>'
                "Premier League · La Liga · Serie A · 2025/26</div>", unsafe_allow_html=True)

st.navigation(pages).run()

with st.sidebar:
    st.markdown("---")
    st.markdown('<div class="note">Final Year Project · Bachelor of Operations Research with Data Science<br>'
                "Data: Understat, ESPN, FBref</div>", unsafe_allow_html=True)
