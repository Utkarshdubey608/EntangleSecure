"""Page 1 — Overview dashboard."""

from __future__ import annotations

import secrets
from dataclasses import replace

import pandas as pd
import streamlit as st

from .. import animations, charts, components, nav, state
from ..theme import S_ALICE, S_EVE


def render() -> None:
    res = state.result()
    cfg = res.config
    m = res.metrics()

    left, right = st.columns([5, 2], vertical_alignment="bottom")
    with left:
        components.page_header(
            "EntangleSecure",
            "A simulation of entanglement-based quantum key distribution (Ekert 1991). Alice and Bob share Bell-singlet "
            "pairs, test the CHSH inequality to rule out an eavesdropper, and distil a secret key from the rest.",
        )
    with right:
        st.html(f'<div style="text-align:right;margin-bottom:1.7rem">{components.status_badge(m["security_status"])}</div>')

    with st.container(border=True):
        animations.channel_hero(res)
    components.note(
        f"Replaying the first pairs of the current experiment ({cfg.n_pairs:,} pairs, seed {cfg.seed}"
        + (f", Eve intercepting {cfg.eve.intercept_fraction:.0%}" if cfg.eve.enabled else "")
        + "). Dials show each party's three measurement directions; the highlighted needle is the one chosen for that pair."
    )

    components.stat_strip(components.headline_stats(res))

    st.subheader("Is the channel secure?")
    c1, c2 = st.columns([3, 2], gap="large", vertical_alignment="center")
    with c1:
        entries = [("this run", m["chsh_s"], m["chsh_stderr"], S_EVE if cfg.eve.enabled else S_ALICE)]
        st.plotly_chart(charts.chsh_scale(entries, height=190), config=charts.PLOT_CONFIG, key="ov_scale")
    with c2:
        components.verdict(res)
        st.write("")
        b1, b2 = st.columns(2)
        if b1.button("Run with a new seed", type="primary", width="stretch", help="Same configuration, fresh random seed"):
            state.run_and_store(replace(cfg, seed=secrets.randbelow(2**31)), source="Overview, new seed")
            st.rerun()
        if b2.button("Toggle Eve and rerun", width="stretch"):
            state.run_and_store(cfg.with_eve(not cfg.eve.enabled), source="Overview, toggle Eve")
            st.rerun()
        nav.link(st, "laboratory", "Configure the experiment in the laboratory", ":material/tune:")

    st.subheader("Recent activity")
    hist = pd.DataFrame(st.session_state.history)
    view = hist[["time", "source", "pairs", "eve", "noise", "S", "QBER", "final_bits", "status", "seed"]].copy()
    st.dataframe(
        view,
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(view), 260),
        column_config={
            "time": st.column_config.TextColumn("Time"),
            "source": st.column_config.TextColumn("Trigger"),
            "pairs": st.column_config.NumberColumn("Pairs", format="%d"),
            "eve": st.column_config.TextColumn("Eve"),
            "noise": st.column_config.NumberColumn("Noise p", format="%.3f"),
            "S": st.column_config.NumberColumn("S", format="%.3f"),
            "QBER": st.column_config.NumberColumn("QBER", format="percent"),
            "final_bits": st.column_config.NumberColumn("Key bits", format="%d"),
            "status": st.column_config.TextColumn("Status"),
            "seed": st.column_config.NumberColumn("Seed", format="%d"),
        },
    )

    st.subheader("How the protocol works")
    s1, s2, s3 = st.columns(3, gap="medium")
    with s1:
        components.panel(
            "Shared entanglement",
            "<p>Each pair is in the singlet state |ψ⁻⟩. Measured along the same direction, the two particles always give "
            "opposite results, yet each result on its own is perfectly random.</p>",
        )
    with s2:
        components.panel(
            "Bell test as a tamper seal",
            "<p>Four setting combinations estimate S. Only genuine entanglement exceeds S = 2. An interceptor who measures "
            "the particles turns them into ordinary correlated objects and pushes S down to 2 or below.</p>",
        )
    with s3:
        components.panel(
            "Key from matching settings",
            "<p>Pairs measured along identical directions (2 of 9 combinations) become key bits. They are checked for errors, "
            "corrected with Cascade, and compressed by privacy amplification.</p>",
        )
