"""Small HTML building blocks rendered with st.html (static, no scripts)."""

from __future__ import annotations

import html
import math
from collections.abc import Sequence

import numpy as np
import streamlit as st

from entanglesecure.protocol import ExperimentResult
from entanglesecure.protocol.theory import TSIRELSON_BOUND

from .theme import CRITICAL, GOOD, STATUS_COLORS, WARN

STATUS_TEXT = {
    "SECURE": ("Secure", "Bell inequality violated beyond the statistical margin and a secret key was distilled."),
    "COMPROMISED": ("Eavesdropping suspected", "Correlations no longer violate the Bell inequality. The key was discarded."),
    "INCONCLUSIVE": ("Inconclusive", "Bell test passed, but too few bits remained to distil a secret key."),
}


def esc(x) -> str:
    return html.escape(str(x))


def fmt(v, digits: int = 3, pct: bool = False) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    if pct:
        return f"{v * 100:.{digits}f}"
    if isinstance(v, (int, np.integer)):
        return f"{v:,}"
    return f"{v:.{digits}f}"


def page_header(title: str, description: str) -> None:
    st.html(f'<div class="es-header"><h1>{esc(title)}</h1><p>{esc(description)}</p></div>')


def stat_strip(stats: Sequence[tuple[str, str, str]]) -> None:
    """stats: (label, value_html, sub_text). value_html may contain <small> units."""
    cells = "".join(
        f'<div class="es-stat"><div class="label">{esc(label)}</div><div class="value">{value}</div>'
        f'<div class="sub">{esc(sub)}</div></div>'
        for label, value, sub in stats
    )
    st.html(f'<div class="es-strip">{cells}</div>')


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, WARN)
    label = STATUS_TEXT.get(status, (status, ""))[0]
    return (
        f'<span class="es-badge" style="color:{color};border-color:{color}55;background:{color}12">'
        f'<span class="dot"></span>{esc(label)}</span>'
    )


def verdict(res: ExperimentResult) -> None:
    status = res.security_status
    color = STATUS_COLORS.get(status, WARN)
    icon = {"SECURE": "✓", "COMPROMISED": "!", "INCONCLUSIVE": "?"}.get(status, "?")
    title, text = STATUS_TEXT.get(status, (status, ""))
    if res.keys.abort_reason:
        text = res.keys.abort_reason
    st.html(
        f'<div class="es-verdict" style="border-color:{color}55;background:{color}0f">'
        f'<div class="icon" style="color:{color}">{icon}</div>'
        f'<div><h4 style="color:{color}">{esc(title)}</h4><p>{esc(text)}</p></div></div>'
    )


def note(text: str) -> None:
    st.html(f'<div class="es-note">{text}</div>')


def formula(lines_html: str) -> None:
    st.html(f'<div class="es-formula">{lines_html}</div>')


def panel(title: str, body_html: str) -> None:
    st.html(f'<div class="es-panel"><h3>{esc(title)}</h3>{body_html}</div>')


def bit_strings(alice: np.ndarray, bob: np.ndarray, limit: int = 256, labels=("Alice", "Bob")) -> None:
    """Side-by-side bit strings with Bob's disagreeing bits highlighted."""
    a = alice[:limit]
    b = bob[:limit]
    a_txt = "".join(str(int(x)) for x in a)
    b_txt = "".join(f'<span class="err">{int(y)}</span>' if x != y else str(int(y)) for x, y in zip(a, b))
    more = f" … (+{alice.size - limit:,} bits)" if alice.size > limit else ""
    st.html(
        f'<div class="es-bits"><span class="who">{esc(labels[0])}</span>{a_txt}{more}<br><br>'
        f'<span class="who">{esc(labels[1])} — mismatches underlined</span>{b_txt}{more}</div>'
    )


def funnel(stages: Sequence[tuple[str, int]]) -> None:
    top = max((v for _, v in stages), default=1) or 1
    rows = "".join(
        f'<div class="row"><span>{esc(name)}</span><div class="track"><div class="bar" style="width:{max(v / top * 100, 0.6):.2f}%"></div></div>'
        f'<span class="n">{v:,}</span></div>'
        for name, v in stages
    )
    st.html(f'<div class="es-funnel">{rows}</div>')


def s_value_html(s: float, err: float) -> str:
    if not math.isfinite(s):
        return "—"
    return f"{s:.3f}<small>± {err:.3f}</small>"


def headline_stats(res: ExperimentResult) -> list[tuple[str, str, str]]:
    m = res.metrics()
    s_color = GOOD if res.bell.violation_confirmed else CRITICAL
    return [
        ("Entangled pairs", fmt(m["total_pairs"]), f"{m['detected_rounds']:,} detected"),
        ("CHSH parameter S", f'<span style="color:{s_color}">{s_value_html(m["chsh_s"], m["chsh_stderr"])}</span>',
         f"classical bound 2, quantum {TSIRELSON_BOUND:.3f}"),
        ("Key agreement", f'{fmt(m["key_agreement"], 2, pct=True)}<small>%</small>', f"{m['alice_key_length']:,} sifted bits"),
        ("QBER", f'{fmt(m["qber"], 2, pct=True)}<small>%</small>', f"theory {fmt(m['qber_theory'], 2, pct=True)} %"),
        ("Final secret key", f'{m["final_key_length"]:,}<small>bits</small>', f"{m['secure_yield_per_pair']:.4f} bits per pair"),
    ]


def sidebar_run_summary(res: ExperimentResult) -> None:
    m = res.metrics()
    eve = "on" if m["eve_enabled"] else "off"
    st.html(
        '<div class="es-side-run">'
        f'<div style="margin-bottom:8px">{status_badge(m["security_status"])}</div>'
        f'<div class="row"><span>Pairs</span><b>{m["total_pairs"]:,}</b></div>'
        f'<div class="row"><span>S</span><b>{fmt(m["chsh_s"])}</b></div>'
        f'<div class="row"><span>QBER</span><b>{fmt(m["qber"], 2, pct=True)} %</b></div>'
        f'<div class="row"><span>Eve</span><b>{eve}</b></div>'
        f'<div class="row"><span>Seed</span><b>{m["seed"]}</b></div>'
        "</div>"
    )
