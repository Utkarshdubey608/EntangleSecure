"""Page 5 — Eavesdropping detection: the same experiment with and without Eve."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import streamlit as st

from entanglesecure.analysis import eve_sweep
from entanglesecure.protocol import ConfigError, EveConfig, ExperimentConfig
from entanglesecure.protocol.theory import CLASSICAL_BOUND
from entanglesecure.quantum import concurrence

from .. import charts, components, state
from ..theme import CRITICAL, S_ALICE, S_EVE, WARN

STRATEGIES = {
    "Guess Bob's directions": "bob",
    "Guess Alice's directions": "alice",
    "Key directions only": "key",
    "Custom directions": "custom",
}


@st.cache_data(show_spinner=False, max_entries=16)
def _sweep(config_json: str) -> pd.DataFrame:
    return eve_sweep(ExperimentConfig.from_json(config_json), np.linspace(0, 1, 11))


def _eve_angles(strategy: str, cfg: ExperimentConfig, custom: str) -> tuple[float, ...]:
    if strategy == "bob":
        return tuple(cfg.bob_angles_deg)
    if strategy == "alice":
        return tuple(cfg.alice_angles_deg)
    if strategy == "key":
        return tuple(sorted({cfg.alice_angles_deg[1], cfg.alice_angles_deg[2]}))
    try:
        vals = tuple(float(v) for v in custom.replace(";", ",").split(",") if v.strip())
    except ValueError as exc:
        raise ConfigError("Custom directions must be numbers separated by commas, e.g. 0, 45, 90.") from exc
    if not vals:
        raise ConfigError("Enter at least one custom direction for Eve.")
    return vals


def render() -> None:
    components.page_header(
        "Eavesdropping detection",
        "Eve sits on Bob's fibre, measures intercepted particles and sends on a fresh particle prepared in the state she saw. "
        "Run the same experiment with and without her and compare what Alice and Bob observe.",
    )
    cfg = state.config()

    with st.container(border=True):
        c1, c2, c3 = st.columns([1.2, 1.3, 1.5], gap="large")
        with c1:
            eve_on = st.toggle("Eve on the channel", value=True, key="eve_toggle",
                               help="Which of the two runs becomes the current experiment shown on the other pages.")
            q = st.slider("Fraction of pairs intercepted", 0.0, 1.0, value=float(cfg.eve.intercept_fraction) if cfg.eve.enabled else 1.0,
                          step=0.05, key="eve_q")
        with c2:
            strategy_label = st.radio("Eve's measurement directions", list(STRATEGIES), key="eve_strategy")
            custom = st.text_input("Custom directions (degrees)", value="0, 45, 90, 135", key="eve_custom",
                                   disabled=STRATEGIES[strategy_label] != "custom")
        with c3:
            pairs = st.number_input("Entangled pairs", min_value=1000, max_value=1_000_000, step=5000,
                                    value=max(int(cfg.n_pairs), 1000), key="eve_pairs")
            st.caption(f"Both runs use seed {cfg.seed}, so Alice and Bob make identical setting choices in each. Only Eve differs.")
            go_btn = st.button("Run comparison", type="primary", width="stretch", key="eve_run")

    first_visit = st.session_state.get("eve_comparison") is None
    if go_btn or first_visit:
        try:
            angles = _eve_angles(STRATEGIES[strategy_label], cfg, custom)
            base = replace(cfg, n_pairs=int(pairs), eve=EveConfig(enabled=False, intercept_fraction=q, basis_angles_deg=angles))
            with st.spinner("Running both experiments…"):
                off = state.run(base)
                on = state.run(base.with_eve(True))
            st.session_state.eve_comparison = (off, on)
            if go_btn:  # the automatic first comparison leaves the current experiment untouched
                state.set_result(on if eve_on else off, source="Eavesdropping, Eve " + ("on" if eve_on else "off"))
        except ConfigError as exc:
            st.error(f"Configuration not accepted: {exc}")

    comp = st.session_state.get("eve_comparison")
    if not comp:
        st.info("Choose Eve's strategy and press Run comparison. The secure and attacked runs appear side by side.")
        _limitations()
        return
    off, on = comp
    mo, mn = off.metrics(), on.metrics()

    st.subheader("Verdicts")
    v1, v2 = st.columns(2, gap="large")
    with v1:
        st.markdown(f'<span style="color:{S_ALICE};font-weight:500">Without Eve</span>', unsafe_allow_html=True)
        components.verdict(off)
    with v2:
        st.markdown(f'<span style="color:{S_EVE};font-weight:500">With Eve, {on.config.eve.intercept_fraction:.0%} intercepted</span>', unsafe_allow_html=True)
        components.verdict(on)

    conc_on = on.model.eve_branches[0].state if on.model.eve_branches else None
    rows = [
        ("CHSH parameter S", f"{mo['chsh_s']:.4f} ± {mo['chsh_stderr']:.4f}", f"{mn['chsh_s']:.4f} ± {mn['chsh_stderr']:.4f}"),
        ("QBER of the sifted key", _pct(mo["qber"]), _pct(mn["qber"])),
        ("Key agreement", _pct(mo["key_agreement"]), _pct(mn["key_agreement"])),
        ("Sifted key bits", f"{mo['alice_key_length']:,}", f"{mn['alice_key_length']:,}"),
        ("Final secret key bits", f"{mo['final_key_length']:,}", f"{mn['final_key_length']:,}"),
        ("Eve's guesses matching Bob's key", _pct(mo["eve_key_agreement"]), _pct(mn["eve_key_agreement"])),
        ("Pairs intercepted", "0", f"{mn['eve_intercepted_pairs']:,}"),
        ("Concurrence of a pair reaching Bob", f"{off.model.concurrence_channel:.3f}",
         f"{concurrence(conc_on):.3f} if intercepted" if conc_on is not None else "—"),
        ("Security status", mo["security_status"].lower(), mn["security_status"].lower()),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Metric", "Without Eve", "With Eve"]), hide_index=True, width="stretch", height=38 + 35 * len(rows))

    st.subheader("Bell parameter")
    st.plotly_chart(
        charts.chsh_scale([("without Eve", mo["chsh_s"], mo["chsh_stderr"], S_ALICE), ("with Eve", mn["chsh_s"], mn["chsh_stderr"], S_EVE)], height=240),
        config=charts.PLOT_CONFIG, key="eve_scale",
    )
    g1, g2 = st.columns([3, 2], gap="large")
    with g1:
        st.plotly_chart(charts.chsh_terms([("without Eve", off, S_ALICE), ("with Eve", on, S_EVE)]), config=charts.PLOT_CONFIG, key="eve_terms")
        components.note(
            "After Eve's measurement each intercepted pair is a product state, so its correlation shrinks from −cos(a − b) "
            "to −cos(a − θ)·cos(b − θ) averaged over her direction θ. All four CHSH terms move toward zero together."
        )
    with g2:
        st.plotly_chart(charts.compare_bars(["without Eve", "with Eve"], [mo["qber"], mn["qber"]], [S_ALICE, S_EVE], "QBER of the sifted key", pct=True),
                        config=charts.PLOT_CONFIG, key="eve_qber")
        st.plotly_chart(
            charts.compare_bars(["without Eve", "with Eve"], [mo["eve_key_agreement"], mn["eve_key_agreement"]], [S_ALICE, S_EVE],
                                "Eve's guesses matching Bob's key", pct=True),
            config=charts.PLOT_CONFIG, key="eve_info",
        )

    st.subheader("Sifted keys under attack")
    st.caption("First 256 sifted bits of the attacked run. Underlined bits are where Bob's bit no longer matches Alice's.")
    components.bit_strings(on.keys.sifted.alice, on.keys.sifted.bob)

    st.subheader("How much interception is detectable?")
    if st.button("Sweep the interception fraction from 0 to 1", key="eve_sweep_btn"):
        with st.spinner("Running 11 experiments…"):
            st.session_state.eve_sweep = _sweep(on.config.to_json())
    sw = st.session_state.get("eve_sweep")
    if sw is not None:
        s1, s2 = st.columns(2, gap="large")
        s1.plotly_chart(charts.sweep_plot(sw, "intercept_fraction", "S", "S_stderr", "S_theory", "fraction intercepted q", "S", S_EVE,
                                          ref=[(CLASSICAL_BOUND, CRITICAL, "classical bound")]), config=charts.PLOT_CONFIG, key="eve_sw_s")
        s2.plotly_chart(charts.sweep_plot(sw, "intercept_fraction", "qber", None, "qber_theory", "fraction intercepted q", "QBER", S_EVE,
                                          ref=[(0.11, WARN, "≈ 11 % BB84-style limit")], pct=True), config=charts.PLOT_CONFIG, key="eve_sw_q")
        q_cross = sw.loc[sw.S_theory <= CLASSICAL_BOUND, "intercept_fraction"].min()
        st.caption(
            "Both S and QBER change linearly with q. "
            + (f"With this strategy S reaches the classical bound at q ≈ {q_cross:.1f}; " if pd.notna(q_cross) else "")
            + "with the Bell margin applied, the protocol aborts earlier still."
        )
    _limitations()


def _pct(v: float) -> str:
    return "—" if v is None or not np.isfinite(v) else f"{v:.2%}"


def _limitations() -> None:
    with st.expander("Limitations of this attack model"):
        st.markdown(
            "- **One individual strategy.** Eve measures single particles and resends eigenstates. She does not entangle probes "
            "with the particles, store them, or make collective or coherent measurements.\n"
            "- **Only Bob's arm is attacked.** Attacking both arms, or replacing the source, gives the same separable statistics.\n"
            "- **No hiding behind loss or noise.** A real Eve could hide errors inside channel noise or exploit detector "
            "inefficiency (the detection loophole). Here detection efficiency is applied as fair sampling.\n"
            "- **Security estimate.** The final key length uses the asymptotic device-independent bound of Acín et al. (2007) "
            "for collective attacks. It covers strategies far beyond the one simulated, but ignores finite-key corrections."
        )
