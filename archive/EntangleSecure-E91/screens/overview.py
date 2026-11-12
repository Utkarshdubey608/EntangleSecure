"""Page script (thin wrapper so Streamlit can route to it)."""

from ui.views import overview

overview.render()
