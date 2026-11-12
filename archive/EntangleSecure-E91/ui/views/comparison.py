"""Page — BB84 vs E91: the same channel question answered by two protocols."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from entanglesecure.protocol.bb84 import BB84_QBER_LIMIT, BB84Config, run_bb84

from .. import charts, components, state
from ..theme import CRITICAL, GOOD, S_ALICE, S_BOB, WARN


def render() -> None:
    res = state.result()
    cfg = res.config
    m = res.metrics()

    components.page_header(
        "BB84 vs E91",
        "Two ways to create a shared secret key with quantum physics. BB84 sends single photons and checks errors. "
        "E91 shares entangled pairs and checks a Bell inequality. Both use the same kind of eavesdropper test.",
    )

    st.subheader("Settings")
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        eve = st.toggle("Intercept-resend Eve on BB84", value=cfg.eve.enabled,
                        help="Eve measures each photon in a random basis and resends it.")
    with c2:
        noise = st.slider("Channel error on BB84", 0.0, 0.3, 0.0, 0.01, format="%.2f",
                          help="Probability that a photon's bit is flipped in transit.")
    with c3:
        st.caption(f"Both protocols use {cfg.n_pairs:,} transmitted qubits and seed {cfg.seed}.")

    bb = run_bb84(BB84Config(n_photons=cfg.n_pairs, eve_enabled=eve, channel_error=noise, seed=cfg.seed))

    st.subheader("Side by side")
    left, right = st.columns(2, gap="large")
    with left:
        st.html(f'<div style="color:{S_ALICE};font-weight:600">BB84 (single photons)</div>')
        components.stat_strip([
            ("Sifted bits", f"{bb.sifted_length:,}", f"{bb.sifted_fraction:.0%} of photons"),
            ("QBER", f"{components.fmt(bb.qber, 2, pct=True) if bb.sifted_length else '—'}<small>%</small>",
             f"limit {BB84_QBER_LIMIT:.0%}"),
            ("Secret key", f"{bb.secret_key_length:,}<small>bits</small>", f"{bb.key_rate_per_photon:.4f} bits per photon"),
        ])
    with right:
        st.html(f'<div style="color:{S_BOB};font-weight:600">E91 (entangled pairs)</div>')
        components.stat_strip([
            ("Sifted bits", f"{m['alice_key_length']:,}", f"{m['detected_rounds']:,} detected pairs"),
            ("QBER", f'{components.fmt(m["qber"], 2, pct=True)}<small>%</small>', f"status {m['security_status'].lower()}"),
            ("Secret key", f'{m["final_key_length"]:,}<small>bits</small>', f"{m['secure_yield_per_pair']:.4f} bits per pair"),
        ])

    c_qber, c_key = st.columns(2, gap="large")
    with c_qber:
        st.plotly_chart(
            charts.compare_bars(["BB84", "E91"], [bb.qber if bb.sifted_length else 0.0, m["qber"]], [S_ALICE, S_BOB],
                                "Error rate on sifted bits", pct=True),
            config=charts.PLOT_CONFIG, key="cmp_qber",
        )
    with c_key:
        st.plotly_chart(
            charts.compare_bars(["BB84", "E91"], [bb.key_rate_per_photon * 1000, m["secure_yield_per_pair"] * 1000],
                                [S_ALICE, S_BOB], "Secret bits per 1,000 transmitted", height=260),
            config=charts.PLOT_CONFIG, key="cmp_key",
        )

    st.subheader("What each protocol needs")
    table = pd.DataFrame(
        {
            "": ["Quantum resource", "Who prepares the quantum state", "How Eve is detected", "Error limit (rule of thumb)",
                 "Hard to build because"],
            "BB84": ["Single photons in random bases", "Alice, one photon at a time",
                     "Eve's measurements disturb photons, which raises the error rate",
                     f"about {BB84_QBER_LIMIT:.0%} QBER", "Reliable single-photon sources and detectors"],
            "E91": ["Entangled photon pairs (singlets)", "A source that sends one photon to each party",
                    "Bell inequality test (CHSH). Eve breaks the violation",
                    "CHSH value must stay above 2", "Distributing entanglement over distance"],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")

    if bb.secure:
        verdict_color, verdict = GOOD, "BB84 distilled a secret key."
    elif bb.secret_key_length == 0:
        verdict_color, verdict = CRITICAL, "BB84 produced no secret key. The error rate is too high or the key is too short."
    else:
        verdict_color, verdict = WARN, "BB84 key rate is above zero, but the error rate is close to the limit."
    st.html(f'<div style="color:{verdict_color}">{components.esc(verdict)}</div>')
    components.note("The BB84 numbers are a simulation with the same photon count and seed as the E91 run. "
                    "The secret key rate uses the one-way estimate 1 − 2·h(QBER), with h the binary entropy.")
