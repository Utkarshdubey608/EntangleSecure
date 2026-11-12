"""Page 3 — Animated, step-by-step E91 protocol."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from entanglesecure.quantum import singlet_circuit_trace

from .. import animations, components, nav, state


def render() -> None:
    res = state.result()
    components.page_header(
        "The E91 protocol, step by step",
        "Eight stages from pair creation to the security verdict. The animation replays the current experiment: the "
        "settings, outcomes, Bell statistics and key lengths are the simulated values.",
    )
    animations.protocol_stepper(res)

    cfg = res.config
    components.note(
        f"Showing {cfg.n_pairs:,} pairs, seed {cfg.seed}, Eve {'on' if cfg.eve.enabled else 'off'}. Change the experiment in the "
        "laboratory or on the eavesdropping page and this walkthrough follows it."
    )
    c1, c2, _ = st.columns([1, 1, 2])
    nav.link(c1, "laboratory", "Change the experiment", ":material/tune:")
    nav.link(c2, "eavesdropping", "Add an eavesdropper", ":material/policy:")

    st.subheader("Data behind the animation")
    with st.expander("Step 1: state vector after each gate of the preparation circuit"):
        rows = [{"after": lab, **{f"amp {b}": float(np.real(a)) for b, a in zip(("|00⟩", "|01⟩", "|10⟩", "|11⟩"), psi)}} for lab, psi in singlet_circuit_trace()]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Steps 3–5: the first 64 recorded pairs"):
        st.dataframe(res.rounds.head(64).to_frame(cfg), hide_index=True, width="stretch", height=360)
    with st.expander("Step 6: CHSH correlators"):
        rows = [
            {"term": sym, "settings": f"A{c.alice_idx}B{c.bob_idx}", "sign": "+" if s > 0 else "−", "rounds": c.n,
             "E measured": c.expectation, "std. error": c.stderr, "E theory": c.theory}
            for sym, c, s in res.bell.chsh_terms()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Step 7: key distillation stages"):
        st.dataframe(pd.DataFrame(res.keys.stages, columns=["stage", "bits / pairs"]), hide_index=True, width="stretch")
