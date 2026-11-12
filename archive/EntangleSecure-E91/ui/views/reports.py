"""Page 6 — Results, downloads and reproducibility."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from entanglesecure.protocol import ConfigError, ExperimentConfig
from entanglesecure.protocol.postprocessing import bits_to_hex
from entanglesecure.reporting import build_pdf_report, correlators_frame, rounds_csv, summary_csv

from .. import charts, components, state


@st.cache_data(show_spinner=False, max_entries=8)
def _pdf(config_json: str, comparison_json: str | None) -> bytes:
    res = state.run(ExperimentConfig.from_json(config_json))
    comp = state.run(ExperimentConfig.from_json(comparison_json)) if comparison_json else None
    return build_pdf_report(res, comp)


@st.cache_data(show_spinner=False, max_entries=8)
def _rounds_csv(config_json: str) -> str:
    return rounds_csv(state.run(ExperimentConfig.from_json(config_json)))


def render() -> None:
    res = state.result()
    cfg = res.config
    m = res.metrics()
    k = res.keys
    components.page_header(
        "Results and reports",
        "A complete record of the current experiment: measurement statistics, the Bell test, every stage of key "
        "distillation, and downloads that let anyone reproduce the run exactly.",
    )
    components.verdict(res)
    st.write("")
    components.stat_strip(components.headline_stats(res))

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.subheader("Key distillation")
        components.funnel(k.stages)
        st.write("")
        rows = [
            ("Sifted key length (Alice = Bob)", f"{len(k.sifted):,} bits"),
            ("QBER, whole sifted key", f"{components.fmt(k.sifted_qber, 3, pct=True)} %"),
            ("QBER estimate from revealed sample", f"{components.fmt(k.qber_estimate, 3, pct=True)} % on {k.estimation_size:,} bits"),
            ("Eve's information bound χ(S − zσ)", components.fmt(k.eve_info_bound, 4)),
            ("Device-independent rate 1 − h(Q) − χ", f"{k.di_rate:.4f} per sifted bit"),
            ("BBM92 rate 1 − 2h(Q), for comparison", f"{k.bbm92_rate:.4f} per sifted bit"),
        ]
        if k.cascade:
            c = k.cascade
            rows += [
                ("Errors before Cascade", f"{c.initial_errors:,}"),
                ("Cascade block sizes per pass", ", ".join(str(b) for b in c.block_sizes)),
                ("Corrections per pass", ", ".join(str(x) for x in c.corrections_per_pass)),
                ("Bits leaked (parities + 64-bit check)", f"{c.leaked_bits:,}"),
                ("Residual errors / hash check", f"{c.residual_errors} / {'passed' if c.verification_passed else 'failed'}"),
            ]
        rows.append(("Final keys identical", "yes" if k.keys_match else "no key"))
        st.dataframe(pd.DataFrame(rows, columns=["Quantity", "Value"]), hide_index=True, width="stretch", height=38 + 35 * len(rows))
    with right:
        st.subheader("Keys")
        st.caption("Sifted keys (first 256 bits). Underlined bits are where Bob's bit differs from Alice's.")
        components.bit_strings(k.sifted.alice, k.sifted.bob)
        st.caption("Final secret key after privacy amplification (identical for Alice and Bob)")
        if k.final_length:
            st.code(bits_to_hex(k.final_alice), language=None, wrap_lines=True)
        else:
            st.info("No final key: " + (k.abort_reason or "protocol aborted."))

    st.subheader("Bell test")
    c1, c2 = st.columns([6, 5], gap="large")
    with c1:
        df = correlators_frame(res)
        df.insert(0, "settings", df.alice_setting + df.bob_setting)
        df = df[["settings", "chsh_term", "n", "E_measured", "E_stderr", "E_theory"]]
        st.dataframe(
            df, hide_index=True, width="stretch", height=38 + 35 * len(df),
            column_config={
                "settings": "Settings",
                "n": st.column_config.NumberColumn("Rounds", format="%d"),
                "E_measured": st.column_config.NumberColumn("E measured", format="%.4f"),
                "E_stderr": st.column_config.NumberColumn("σ", format="%.4f"),
                "E_theory": st.column_config.NumberColumn("E theory", format="%.4f"),
                "chsh_term": "CHSH term",
            },
        )
    with c2:
        st.plotly_chart(charts.correlation_curve(res, height=340), config=charts.PLOT_CONFIG, key="rep_curve")

    st.subheader("Download")
    comp = st.session_state.get("eve_comparison")
    comparison = None
    if comp:
        off, on = comp
        if on.config == cfg:
            comparison = off
        elif off.config == cfg:
            comparison = on
    stamp = dt.datetime.fromtimestamp(res.timestamp).strftime("%Y%m%d-%H%M%S")
    d1, d2, d3, d4 = st.columns(4)
    with st.spinner("Preparing reports…"):
        pdf_bytes = _pdf(cfg.to_json(), comparison.config.to_json() if comparison else None)
    d1.download_button("PDF report", pdf_bytes, file_name=f"entanglesecure-report-{stamp}.pdf", mime="application/pdf",
                       width="stretch", type="primary", icon=":material/picture_as_pdf:")
    d2.download_button("Summary CSV", summary_csv(res), file_name=f"entanglesecure-summary-{stamp}.csv", mime="text/csv",
                       width="stretch", icon=":material/table:")
    d3.download_button("Rounds CSV", _rounds_csv(cfg.to_json()), file_name=f"entanglesecure-rounds-{stamp}.csv",
                       mime="text/csv", width="stretch", icon=":material/dataset:")
    d4.download_button("Configuration JSON", cfg.to_json(), file_name=f"entanglesecure-config-seed{cfg.seed}.json", mime="application/json",
                       width="stretch", icon=":material/data_object:")
    st.caption(f"Rounds CSV: one row per entangled pair ({cfg.n_pairs:,} rows) with settings, outcomes, role and Eve's actions.")
    if comparison is not None:
        st.caption("The PDF includes the with/without-Eve comparison from the eavesdropping page.")

    st.subheader("Reproduce an experiment")
    r1, r2 = st.columns(2, gap="large")
    with r1:
        st.markdown("**From a configuration file**")
        up = st.file_uploader("Upload a configuration JSON", type=["json"], key="rep_upload", label_visibility="collapsed")
        if up is not None and st.button("Run uploaded configuration", key="rep_run_upload", type="primary"):
            try:
                text = up.getvalue().decode("utf-8")
                new_cfg = ExperimentConfig.from_json(text)
            except UnicodeDecodeError:
                st.error("The file is not UTF-8 text. Upload the JSON file downloaded from this page.")
            except ConfigError as exc:
                st.error(f"Configuration not accepted: {exc}")
            else:
                if state.run_and_store(new_cfg, source="Reports, uploaded config"):
                    st.rerun()
    with r2:
        st.markdown("**From this session's history**")
        hist = st.session_state.history
        if hist:
            labels = [f"{h['time']}, {h['source']}, {h['pairs']:,} pairs, seed {h['seed']}, {h['status'].lower()}" for h in hist]
            choice = st.selectbox("Earlier run", range(len(hist)), format_func=lambda i: labels[i], key="rep_hist", label_visibility="collapsed")
            if st.button("Re-run selected configuration", key="rep_rerun"):
                if state.run_and_store(ExperimentConfig.from_json(hist[choice]["config_json"]), source="Reports, re-run from history"):
                    st.rerun()
    components.note("Runs are deterministic: the same configuration and seed reproduce every outcome, statistic and key bit.")

    with st.expander("All metrics (machine-readable)"):
        st.json({k_: (None if isinstance(v, float) and v != v else v) for k_, v in m.items() if k_ != "final_key_hex"})
