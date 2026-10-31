"""Entry point:  streamlit run app/streamlit_app.py"""
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"
st.set_page_config(page_title="Tactical Profiles · Attacking Styles", page_icon=str(ASSETS / "logo_icon.svg"),
                   layout="wide", initial_sidebar_state="collapsed")

import ui  # noqa: E402
from views import club_profile, head_to_head, leagues, match, matchday, methodology, players, style_map  # noqa: E402

ui.inject_css()
st.logo(str(ASSETS / "logo.svg"), size="large")

import data  # noqa: E402

# The thesis system (FYP1 proposal, RO3): five pages. Extensions appear only with SHOW_EXTENSIONS on (data.py).
pages = [
    st.Page(style_map.render, title="Overview", icon=":material/scatter_plot:", url_path="overview", default=True),
    st.Page(club_profile.render, title="Clubs", icon=":material/shield:", url_path="club"),
    st.Page(head_to_head.render, title="Head-to-head", icon=":material/compare_arrows:", url_path="head-to-head"),
    st.Page(leagues.render, title="Leagues", icon=":material/public:", url_path="leagues"),
    st.Page(methodology.render, title="Methodology", icon=":material/science:", url_path="methodology"),
]
if data.EXTENSIONS:
    pages[1:1] = [st.Page(matchday.render, title="Matchday", icon=":material/stadium:", url_path="matchday")]
    pages[3:3] = [st.Page(players.render, title="Players", icon=":material/person:", url_path="players")]
    pages.append(st.Page(match.render, title="Match centre", icon=":material/sports_soccer:", url_path="match",
                         visibility="hidden"))

st.navigation(pages, position="top").run()
