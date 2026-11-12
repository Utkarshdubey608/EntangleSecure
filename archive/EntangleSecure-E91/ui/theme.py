"""Design tokens, global CSS and the Plotly template.

Palette roles
* UI accents: cyan (Alice / quantum), violet (Bob / entanglement), blue (channel).
* Chart marks: validated dark-mode categorical set (dataviz validator, surface #0B1220):
  #0EA5C6 · #8B6CF0 · #C98410 — all checks pass.
* Status colours are reserved for security states and always ship with a text label.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

BG = "#070B16"
SURFACE = "#0B1220"
RAISED = "#101A2D"
LINE = "#1C2740"
LINE_STRONG = "#2A3856"
INK = "#E7EDF7"
INK_2 = "#A3B0C7"
MUTED = "#6B7A96"

CYAN = "#22D3EE"
VIOLET = "#A78BFA"
BLUE = "#4C8DFF"

# Chart series (validated)
S_ALICE = "#0EA5C6"
S_BOB = "#8B6CF0"
S_EVE = "#C98410"
THEORY = "#A3B0C7"

GOOD = "#34D399"
WARN = "#FBBF24"
CRITICAL = "#F87171"

FONT_SANS = "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif"
FONT_MONO = "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace"

STATUS_COLORS = {"SECURE": GOOD, "COMPROMISED": CRITICAL, "INCONCLUSIVE": WARN}

GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

:root {{
  --bg: {BG}; --surface: {SURFACE}; --raised: {RAISED}; --line: {LINE}; --line-strong: {LINE_STRONG};
  --ink: {INK}; --ink-2: {INK_2}; --muted: {MUTED};
  --cyan: {CYAN}; --violet: {VIOLET}; --blue: {BLUE};
  --good: {GOOD}; --warn: {WARN}; --critical: {CRITICAL}; --eve: {S_EVE};
  --sans: {FONT_SANS}; --mono: {FONT_MONO};
}}

html, body, .stApp, [data-testid="stAppViewContainer"] {{
  background: var(--bg) !important; color: var(--ink); font-family: var(--sans);
}}
.stApp {{
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(76,141,255,0.07), transparent 60%),
    radial-gradient(900px 420px at -10% 0%, rgba(34,211,238,0.05), transparent 60%),
    var(--bg) !important;
}}
[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stDecoration"], #MainMenu, footer, [data-testid="stStatusWidget"] {{ display: none !important; }}
.block-container {{ padding-top: 2.2rem !important; padding-bottom: 4rem !important; max-width: 1320px; }}

h1, h2, h3, h4, h5, p, li, label, input, textarea, button, td, th {{ font-family: var(--sans); }}
h1 {{ font-weight: 500 !important; letter-spacing: -0.02em; }}
h2, h3 {{ font-weight: 500 !important; letter-spacing: -0.01em; color: var(--ink) !important; }}
p, li {{ color: var(--ink-2); line-height: 1.6; }}
code, kbd, pre {{ font-family: var(--mono) !important; }}
a {{ color: var(--cyan) !important; }}
:focus-visible {{ outline: 2px solid var(--cyan) !important; outline-offset: 2px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: #080D19 !important; border-right: 1px solid var(--line); }}
[data-testid="stSidebar"] [data-testid="stLogo"] {{ height: 2.1rem; }}
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {{ border-radius: 8px !important; }}
[data-testid="stSidebarNavLink"] span {{ color: var(--ink-2) !important; font-size: 0.92rem; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: rgba(34,211,238,0.08) !important; }}
[data-testid="stSidebarNavLink"][aria-current="page"] span {{ color: var(--ink) !important; }}
[data-testid="stSidebarNavLink"]:hover {{ background: rgba(255,255,255,0.04) !important; }}

/* Widgets */
[data-testid="stWidgetLabel"] p, .stSlider label p {{ color: var(--ink-2) !important; font-size: 0.86rem !important; }}
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="base-input"], .stNumberInput input, .stTextInput input {{
  background: var(--surface) !important; border-color: var(--line) !important; color: var(--ink) !important;
}}
.stNumberInput button {{ background: var(--raised) !important; border-color: var(--line) !important; }}
[data-testid="stSlider"] [role="slider"] {{ background: var(--cyan) !important; box-shadow: 0 0 0 4px rgba(34,211,238,0.15) !important; }}
[data-testid="stSliderThumbValue"] {{ color: var(--cyan) !important; font-family: var(--mono); font-size: 0.78rem; }}
[data-testid="stTickBarMin"], [data-testid="stTickBarMax"] {{ color: var(--muted) !important; font-size: 0.75rem; }}

.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] > button {{
  border-radius: 8px !important; border: 1px solid var(--line-strong) !important; background: var(--raised) !important;
  color: var(--ink) !important; font-weight: 500 !important; transition: border-color .15s ease, background .15s ease;
}}
.stButton button:hover, .stDownloadButton button:hover, [data-testid="stFormSubmitButton"] > button:hover {{
  border-color: var(--cyan) !important; background: #13213a !important;
}}
.stButton button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {{
  background: linear-gradient(180deg, #19c3dd, #0ea5c6) !important; color: #03121a !important; border: 0 !important; font-weight: 600 !important;
}}
.stButton button[kind="primary"] p, [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] p,
.stDownloadButton button[kind="primary"] p {{ color: #03121a !important; font-weight: 600 !important; }}
.stDownloadButton button[kind="primary"] {{ background: linear-gradient(180deg, #19c3dd, #0ea5c6) !important; border: 0 !important; }}
.stButton button[kind="primary"]:hover, .stDownloadButton button[kind="primary"]:hover {{ filter: brightness(1.08); }}

[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ border-color: var(--line) !important; }}
div[data-testid="stContainer"], [data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px; }}
[data-testid="stExpander"] details {{ background: var(--surface); border: 1px solid var(--line) !important; border-radius: 10px; }}
[data-testid="stExpander"] summary p {{ color: var(--ink) !important; font-weight: 500; }}

.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{ color: var(--ink-2); padding: 8px 14px; }}
.stTabs [aria-selected="true"] {{ color: var(--ink) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--cyan) !important; }}

[data-testid="stDataFrame"] {{ border: 1px solid var(--line); border-radius: 10px; }}
[data-testid="stAlert"] {{ border-radius: 10px; }}
hr {{ border-color: var(--line) !important; }}

/* ---------- custom components ---------- */
.es-header {{ margin: 0 0 1.6rem 0; }}
.es-header h1 {{ font-size: 2.05rem; line-height: 1.15; color: var(--ink); margin: 0 0 .45rem 0; padding: 0; }}
.es-header p {{ max-width: 72ch; margin: 0; font-size: 1rem; }}

.es-panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; }}
.es-panel h3 {{ font-size: 1rem; margin: 0 0 .6rem 0; }}

.es-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); background: var(--surface);
  border: 1px solid var(--line); border-radius: 12px; overflow: hidden; margin-bottom: 1.2rem; }}
.es-stat {{ padding: 16px 18px; border-right: 1px solid var(--line); min-width: 0; }}
.es-stat:last-child {{ border-right: 0; }}
.es-stat .label {{ color: var(--muted); font-size: .8rem; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.es-stat .value {{ color: var(--ink); font-size: 1.55rem; font-weight: 500; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; line-height: 1.15; }}
.es-stat .value small {{ font-size: .85rem; color: var(--ink-2); font-weight: 400; margin-left: 2px; }}
.es-stat .sub {{ color: var(--ink-2); font-size: .78rem; margin-top: 4px; font-variant-numeric: tabular-nums; }}
@media (max-width: 760px) {{ .es-stat {{ border-right: 0; border-bottom: 1px solid var(--line); }} }}

.es-badge {{ display: inline-flex; align-items: center; gap: 7px; padding: 4px 11px 4px 9px; border-radius: 999px;
  font-size: .8rem; font-weight: 500; border: 1px solid; white-space: nowrap; }}
.es-badge .dot {{ width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 10px currentColor; }}

.es-verdict {{ display: flex; gap: 16px; align-items: flex-start; border-radius: 12px; padding: 16px 18px; border: 1px solid; }}
.es-verdict .icon {{ font-size: 1.4rem; line-height: 1; margin-top: 2px; }}
.es-verdict h4 {{ margin: 0 0 4px 0; font-size: 1rem; font-weight: 600; }}
.es-verdict p {{ margin: 0; font-size: .9rem; }}

.es-formula {{ font-family: var(--mono); color: var(--ink); background: #081022; border: 1px solid var(--line);
  border-radius: 10px; padding: 14px 16px; font-size: .92rem; line-height: 1.75; overflow-x: auto; white-space: pre; }}
.es-formula .c {{ color: var(--muted); }}
.es-formula .a {{ color: var(--cyan); }}
.es-formula .b {{ color: var(--violet); }}
.es-formula .r {{ color: var(--warn); }}

.es-bits {{ font-family: var(--mono); font-size: .82rem; line-height: 1.6; word-break: break-all; color: var(--ink-2);
  background: #081022; border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }}
.es-bits .err {{ color: var(--critical); text-decoration: underline; }}
.es-bits .who {{ color: var(--muted); font-family: var(--sans); font-size: .76rem; display: block; margin-bottom: 2px; }}

.es-note {{ color: var(--ink-2); font-size: .86rem; line-height: 1.55; border-left: 2px solid var(--line-strong); padding: 2px 0 2px 12px; margin: .4rem 0 1rem 0; }}

.es-side-run {{ border: 1px solid var(--line); border-radius: 10px; padding: 12px 13px; background: var(--surface); font-size: .82rem; color: var(--ink-2); }}
.es-side-run b {{ color: var(--ink); font-weight: 500; }}
.es-side-run .row {{ display: flex; justify-content: space-between; padding: 2px 0; font-variant-numeric: tabular-nums; }}
.es-brand {{ display: flex; align-items: center; gap: 10px; padding: 4px 2px 14px 2px; }}
.es-brand .name {{ color: var(--ink); font-weight: 600; font-size: 1.02rem; letter-spacing: -0.01em; }}
.es-brand .sub {{ color: var(--muted); font-size: .75rem; }}

.es-funnel {{ display: flex; flex-direction: column; gap: 8px; }}
.es-funnel .row {{ display: grid; grid-template-columns: 190px 1fr 90px; align-items: center; gap: 12px; font-size: .86rem; }}
.es-funnel .bar {{ height: 10px; border-radius: 4px; background: linear-gradient(90deg, #0ea5c6, #8b6cf0); }}
.es-funnel .track {{ background: #0d1830; border-radius: 4px; }}
.es-funnel .n {{ text-align: right; color: var(--ink); font-variant-numeric: tabular-nums; }}
@media (max-width: 760px) {{ .es-funnel .row {{ grid-template-columns: 1fr 70px; }} .es-funnel .track {{ grid-column: 1 / -1; }} }}

@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
</style>
"""


def _register_plotly_template() -> None:
    axis = dict(
        gridcolor="rgba(163,176,199,0.08)",
        zerolinecolor="rgba(163,176,199,0.22)",
        linecolor=LINE_STRONG,
        tickfont=dict(color=INK_2, size=11),
        title=dict(font=dict(color=INK_2, size=12)),
        showline=False,
        ticks="",
    )
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_SANS, color=INK, size=12),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=[S_ALICE, S_BOB, S_EVE, THEORY],
            xaxis=axis,
            yaxis=axis,
            margin=dict(l=48, r=18, t=36, b=42),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=INK_2, size=11), orientation="h", yanchor="bottom", y=1.02, x=0),
            hoverlabel=dict(bgcolor=RAISED, bordercolor=LINE_STRONG, font=dict(family=FONT_SANS, color=INK, size=12)),
            title=dict(font=dict(size=14, color=INK), x=0, xanchor="left"),
            bargap=0.28,
        )
    )
    pio.templates["entanglesecure"] = template
    pio.templates.default = "entanglesecure"


_register_plotly_template()
