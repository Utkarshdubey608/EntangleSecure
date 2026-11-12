"""EntangleSecure — Streamlit entry point.

Run with:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="EntangleSecure · E91 QKD", page_icon="⚛️", layout="wide", initial_sidebar_state="auto")

from ui import components, nav, state, theme  # noqa: E402

st.html(theme.GLOBAL_CSS)
state.init()

nav.PAGES.update(
    overview=st.Page("screens/overview.py", title="Overview", icon=":material/hub:", url_path="overview", default=True),
    laboratory=st.Page("screens/laboratory.py", title="Quantum laboratory", icon=":material/science:", url_path="laboratory"),
    protocol=st.Page("screens/protocol.py", title="E91 protocol", icon=":material/route:", url_path="protocol"),
    eavesdropping=st.Page("screens/eavesdropping.py", title="Eavesdropping detection", icon=":material/policy:", url_path="eavesdropping"),
    reports=st.Page("screens/reports.py", title="Results and reports", icon=":material/description:", url_path="reports"),
    threat=st.Page("screens/threat.py", title="Quantum threat", icon=":material/shield_lock:", url_path="threat"),
    comparison=st.Page("screens/comparison.py", title="BB84 vs E91", icon=":material/compare_arrows:", url_path="comparison"),
    messaging=st.Page("screens/messaging.py", title="Secure message", icon=":material/lock:", url_path="messaging"),
)
pages = list(nav.PAGES.values())

st.logo("assets/logo.svg", size="large", icon_image="assets/icon.svg")

current_page = st.navigation(pages, position="top")
with st.sidebar:
    st.caption("Current experiment")
    summary_slot = st.empty()

current_page.run()

# Filled after the page ran, so it reflects a run triggered on this rerun.
with summary_slot.container():
    components.sidebar_run_summary(state.result())
