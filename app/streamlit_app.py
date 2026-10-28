"""Entry point:  streamlit run app/streamlit_app.py"""
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"
st.set_page_config(page_title="Tactical Profiles · Attacking Styles 2025/26", page_icon=str(ASSETS / "logo_icon.svg"),
                   layout="wide", initial_sidebar_state="expanded")

import ui  # noqa: E402
from views import club_profile, head_to_head, leagues, methodology, style_map  # noqa: E402

ui.inject_css()
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "logo_icon.svg"))

pages = {
    "Explore": [
        st.Page(style_map.render, title="Overview", icon=":material/scatter_plot:", url_path="overview", default=True),
        st.Page(club_profile.render, title="Club profile", icon=":material/shield:", url_path="club"),
        st.Page(head_to_head.render, title="Head-to-head", icon=":material/compare_arrows:", url_path="head-to-head"),
    ],
    "Analysis": [
        st.Page(leagues.render, title="League comparison", icon=":material/public:", url_path="leagues"),
        st.Page(methodology.render, title="Methodology", icon=":material/science:", url_path="methodology"),
    ],
}

nav = st.navigation(pages)

with st.sidebar:
    st.markdown(
        '<div style="margin-top:0.4rem">'
        '<span class="side-pill">Premier League</span><span class="side-pill">La Liga</span>'
        '<span class="side-pill">Serie A</span></div>'
        '<div class="side-meta">Season <b>2025/26</b> · <b>60</b> clubs · <b>1,140</b> matches<br>'
        "Sources: Understat, ESPN<br><br>"
        "Final Year Project · Bachelor of Operations Research with Data Science</div>",
        unsafe_allow_html=True)

nav.run()
