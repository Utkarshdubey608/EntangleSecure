"""Page 2 — Quantum laboratory: configure, run and inspect an experiment."""

from __future__ import annotations

import secrets
from dataclasses import replace

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from entanglesecure.protocol import EKERT_ALICE_DEG, EKERT_BOB_DEG, ExperimentConfig
from entanglesecure.protocol.config import MAX_PAIRS, MIN_PAIRS
from entanglesecure.protocol.trace import trace_pair

from .. import charts, components, state
from ..theme import INK, INK_2, MUTED, S_ALICE, S_BOB

PRESETS = {
    "Ekert 1991": dict(alice=EKERT_ALICE_DEG, bob=EKERT_BOB_DEG, noise=0.0, eta=1.0),
    "Noisy fibre": dict(alice=EKERT_ALICE_DEG, bob=EKERT_BOB_DEG, noise=0.04, eta=0.85),
    "Tilted A1": dict(alice=(0.0, 60.0, 90.0), bob=EKERT_BOB_DEG, noise=0.0, eta=1.0),
}


def _load_widgets(cfg: ExperimentConfig) -> None:
    ss = st.session_state
    ss.lab_n = cfg.n_pairs
    for i in range(3):
        ss[f"lab_A{i}"] = float(cfg.alice_angles_deg[i])
        ss[f"lab_B{i}"] = float(cfg.bob_angles_deg[i])
    ss.lab_noise = float(cfg.depolarizing_noise)
    ss.lab_eta = float(cfg.detection_efficiency)
    ss.lab_seed = int(cfg.seed)
    ss.lab_est = float(cfg.estimation_fraction)
    ss.lab_z = float(cfg.bell_confidence_sigma)
    ss.lab_passes = int(cfg.cascade_passes)
    ss.lab_eve = bool(cfg.eve.enabled)
    ss.lab_q = float(cfg.eve.intercept_fraction)
    ss.lab_synced = cfg.to_json()


def _apply_preset(name: str) -> None:
    p = PRESETS[name]
    ss = st.session_state
    for i in range(3):
        ss[f"lab_A{i}"] = float(p["alice"][i])
        ss[f"lab_B{i}"] = float(p["bob"][i])
    ss.lab_noise, ss.lab_eta = p["noise"], p["eta"]


def _new_seed() -> None:
    st.session_state.lab_seed = secrets.randbelow(2**31)


def _reset() -> None:
    state.reset()
    _load_widgets(state.config())


def _config_from_widgets(base: ExperimentConfig) -> ExperimentConfig:
    ss = st.session_state
    return replace(
        base,
        n_pairs=int(ss.lab_n),
        alice_angles_deg=tuple(ss[f"lab_A{i}"] for i in range(3)),
        bob_angles_deg=tuple(ss[f"lab_B{i}"] for i in range(3)),
        depolarizing_noise=ss.lab_noise,
        detection_efficiency=ss.lab_eta,
        seed=int(ss.lab_seed),
        estimation_fraction=ss.lab_est,
        bell_confidence_sigma=ss.lab_z,
        cascade_passes=int(ss.lab_passes),
        eve=replace(base.eve, enabled=bool(ss.lab_eve), intercept_fraction=ss.lab_q),
    )


def render() -> None:
    components.page_header(
        "Quantum laboratory",
        "Set the source, the measurement directions and the channel, then run the experiment. Every number below is "
        "computed from the simulated measurement record.",
    )
    cfg = state.config()
    widgets_missing = any(k not in st.session_state for k in ("lab_n", "lab_A0", "lab_seed", "lab_q", "lab_passes"))
    if widgets_missing or st.session_state.get("lab_synced") != cfg.to_json():
        _load_widgets(cfg)

    controls, preview = st.columns([3, 2], gap="large")
    with controls:
        st.markdown("**Presets**")
        pc = st.columns(len(PRESETS) + 1)
        for col, name in zip(pc, PRESETS):
            col.button(name, on_click=_apply_preset, args=(name,), width="stretch")
        pc[-1].button("Reset all", on_click=_reset, width="stretch", help="Restore defaults and rerun")

        with st.form("lab_form", border=True):
            st.number_input("Entangled pairs", min_value=MIN_PAIRS, max_value=MAX_PAIRS, step=1000, key="lab_n",
                            help="Each pair is one shot of the singlet source.")
            a_col, b_col = st.columns(2)
            with a_col:
                st.markdown(f'<span style="color:{S_ALICE};font-weight:500">Alice\'s directions</span>', unsafe_allow_html=True)
                for i in range(3):
                    st.slider(f"A{i}", -180.0, 180.0, step=0.5, key=f"lab_A{i}", format="%.1f°")
            with b_col:
                st.markdown(f'<span style="color:{S_BOB};font-weight:500">Bob\'s directions</span>', unsafe_allow_html=True)
                for i in range(3):
                    st.slider(f"B{i}", -180.0, 180.0, step=0.5, key=f"lab_B{i}", format="%.1f°")
            n_col, e_col = st.columns(2)
            n_col.slider("Depolarizing noise per particle (p)", 0.0, 0.5, step=0.005, key="lab_noise", format="%.3f")
            e_col.slider("Detection efficiency (η)", 0.05, 1.0, step=0.01, key="lab_eta", format="%.2f")
            s_col, v_col = st.columns(2)
            s_col.number_input("Random seed", min_value=0, max_value=2**32 - 1, step=1, key="lab_seed")
            with v_col:
                st.toggle("Eavesdropper on Bob's channel", key="lab_eve")
                st.slider("Interception fraction", 0.0, 1.0, step=0.05, key="lab_q", format="%.2f")
            with st.expander("Classical post-processing"):
                x1, x2, x3 = st.columns(3)
                x1.slider("Bits revealed for QBER", 0.05, 0.5, step=0.05, key="lab_est", format="%.2f")
                x2.slider("Bell margin (σ)", 0.0, 5.0, step=0.5, key="lab_z", format="%.1f")
                x3.slider("Cascade passes", 1, 8, key="lab_passes")
            run = st.form_submit_button("Run experiment", type="primary", width="stretch")
        st.button("New random seed", on_click=_new_seed, help="Draws a seed; press Run to use it")

        if run:
            with st.spinner("Simulating entangled pairs…"):
                res = state.run_and_store(_config_from_widgets(cfg), source="Laboratory")
            if res is not None:
                st.session_state.lab_synced = res.config.to_json()
                st.toast(f"Experiment finished: S = {res.bell.s_value:.3f}, {res.keys.final_length:,} key bits", icon="✅")

    res = state.result()
    with preview:
        st.markdown("**Measurement directions** (Bloch sphere, x–z plane)")
        st.plotly_chart(charts.measurement_directions(res.config), config=charts.PLOT_CONFIG, key="lab_dirs")
        components.note(
            "Angles are spin directions on the Bloch sphere measured from +z toward +x. For polarised photons divide by two: "
            "a 45° direction is a 22.5° polariser."
        )
        lab = res.bell.labelling
        components.formula(
            f'<span class="c">CHSH assignment (fixed by the angles)</span>\n'
            f'a = <span class="a">A{lab.a}</span>   a′ = <span class="a">A{lab.a_prime}</span>   '
            f'b = <span class="b">B{lab.b}</span>   b′ = <span class="b">B{lab.b_prime}</span>\n'
            f'<span class="c">predicted</span>  S = {res.bell.s_theory:.4f}   QBER = {res.theory_qber:.2%}'
        )

    st.divider()
    st.subheader("Results")
    components.stat_strip(components.headline_stats(res))
    rc = res.role_counts()
    components.stat_strip(
        [
            ("Key rounds", f"{rc['key']:,}", f"{rc['key'] / res.config.n_pairs:.1%} of pairs (ideal 22.2 %)"),
            ("CHSH rounds", f"{rc['chsh']:,}", f"{rc['chsh'] / res.config.n_pairs:.1%} of pairs (ideal 44.4 %)"),
            ("Discarded rounds", f"{rc['discard']:,}", f"{rc['discard'] / res.config.n_pairs:.1%} of pairs (ideal 33.3 %)"),
            ("Lost rounds", f"{rc['lost']:,}", f"η² = {res.config.detection_efficiency ** 2:.3f} detection probability"),
            ("Concurrence", f"{res.model.concurrence_channel:.3f}", "entanglement after the channel"),
        ]
    )

    t1, t2, t3, t4 = st.tabs(["Correlations", "Outcome statistics", "Measurement record", "Single pair, step by step"])
    with t1:
        st.plotly_chart(charts.correlation_curve(res), config=charts.PLOT_CONFIG, key="lab_curve")
        h1, h2 = st.columns(2)
        h1.plotly_chart(charts.correlation_heatmap(res.bell.correlation_matrix(), res.config, "Measured E(Aᵢ, Bⱼ)"), config=charts.PLOT_CONFIG, key="lab_hm1")
        h2.plotly_chart(charts.correlation_heatmap(res.theory_matrix, res.config, "Theory E(Aᵢ, Bⱼ)"), config=charts.PLOT_CONFIG, key="lab_hm2")
    with t2:
        st.plotly_chart(charts.agreement_bars(res), config=charts.PLOT_CONFIG, key="lab_agree")
        components.note("For the singlet, P(equal outcomes) = (1 + E)/2 = (1 − cos(a − b))/2. The white ticks mark that prediction.")
    with t3:
        _record(res)
    with t4:
        _single_pair(res)


def _record(res) -> None:
    n_show = min(len(res.rounds), 2000)
    df = res.rounds.head(n_show).to_frame(res.config)
    if not res.config.eve.enabled:
        df = df.drop(columns=["eve_intercepted", "eve_angle_deg", "eve_outcome"])
    st.caption(f"First {n_show:,} of {len(res.rounds):,} rounds. Download the full record on the Results page.")
    st.dataframe(
        df, hide_index=True, width="stretch", height=420,
        column_config={
            "round": st.column_config.NumberColumn("Pair", format="%d", width="small"),
            "alice_angle_deg": st.column_config.NumberColumn("Alice θ", format="%.1f°"),
            "bob_angle_deg": st.column_config.NumberColumn("Bob θ", format="%.1f°"),
            "alice_outcome": st.column_config.NumberColumn("Alice result", format="%+d"),
            "bob_outcome": st.column_config.NumberColumn("Bob result", format="%+d"),
            "eve_angle_deg": st.column_config.NumberColumn("Eve θ", format="%.1f°"),
        },
    )


def _single_pair(res) -> None:
    n = len(res.rounds)
    idx = st.number_input("Pair number", min_value=1, max_value=n, value=1, step=1, key="lab_pair") - 1
    tr = trace_pair(res, int(idx))
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        lines = [
            '<span class="c">1. state reaching the detectors</span>',
            ("Eve measured Bob's particle along " f"{tr.eve_angle_deg:g}° and got {tr.eve_outcome:+d}: product state, "
             if tr.intercepted else "singlet (with channel noise), ") + f"concurrence {tr.concurrence_before:.3f}",
            f'<span class="c">2. Alice measures along</span> <span class="a">{tr.alice_angle_deg:g}°</span>',
            f"   P(+1) = {tr.p_alice[1]:.4f}   P(−1) = {tr.p_alice[-1]:.4f}   result: <span class=\"a\">{tr.alice_outcome:+d}</span>",
            '<span class="c">3. Bob\'s particle collapses to Bloch vector</span>',
            f"   (x, y, z) = ({tr.bob_bloch_after[0]:+.3f}, {tr.bob_bloch_after[1]:+.3f}, {tr.bob_bloch_after[2]:+.3f})",
            f'<span class="c">4. Bob measures along</span> <span class="b">{tr.bob_angle_deg:g}°</span>',
            f"   P(+1 | x) = {tr.p_bob_given_alice[1]:.4f}   P(−1 | x) = {tr.p_bob_given_alice[-1]:.4f}   result: <span class=\"b\">{tr.bob_outcome:+d}</span>",
            f'<span class="c">probability of this joint outcome</span>  P(x, y) = {tr.joint_probability:.4f}',
        ]
        if not tr.detected:
            lines.append('<span class="r">this pair was not detected (lost); the outcomes above are illustrative only</span>')
        components.formula("\n".join(lines))
    with c2:
        st.plotly_chart(_bloch_circle(tr), config=charts.PLOT_CONFIG, key="lab_bloch")


def _bloch_circle(tr) -> go.Figure:
    """Bob's conditional state (x–z plane of the Bloch sphere) and his measurement direction."""
    t = np.linspace(0, 2 * np.pi, 200)
    fig = go.Figure()
    fig.add_scatter(x=np.sin(t), y=np.cos(t), mode="lines", line=dict(color="#2A3856", width=1), hoverinfo="skip", showlegend=False)
    bx, bz = tr.bob_bloch_after[0], tr.bob_bloch_after[2]
    fig.add_scatter(x=[0, bx], y=[0, bz], mode="lines+markers", name="Bob's state after Alice's result",
                    line=dict(color=S_ALICE, width=3), marker=dict(size=[0, 11], color=S_ALICE))
    th = np.radians(tr.bob_angle_deg)
    fig.add_scatter(x=[-np.sin(th), np.sin(th)], y=[-np.cos(th), np.cos(th)], mode="lines+text", name="Bob's measurement axis",
                    line=dict(color=S_BOB, width=2, dash="dash"), text=["−1", "+1"], textposition="top center", textfont=dict(color=INK))
    fig.update_layout(height=330, xaxis=dict(range=[-1.25, 1.25], title="x", zeroline=False, scaleanchor="y", tickfont=dict(color=MUTED)),
                      yaxis=dict(range=[-1.25, 1.25], title="z", zeroline=False, tickfont=dict(color=INK_2)),
                      margin=dict(l=40, r=10, t=30, b=40))
    return fig

