"""Session state shared by all pages. The UI never computes physics — it calls the engine here."""

from __future__ import annotations

import time
from dataclasses import replace

import streamlit as st

from entanglesecure.protocol import ConfigError, ExperimentConfig, ExperimentResult, run_experiment

HISTORY_LIMIT = 25


@st.cache_data(show_spinner=False, max_entries=48)
def _cached_run(config_json: str) -> ExperimentResult:
    return run_experiment(ExperimentConfig.from_json(config_json))


def run(config: ExperimentConfig) -> ExperimentResult:
    """Validate + run (cached by exact configuration, so identical configs return identical results)."""
    return _cached_run(config.validate().to_json())


def init() -> None:
    ss = st.session_state
    if "config" not in ss:
        ss.config = ExperimentConfig().validate()
    if "history" not in ss:
        ss.history = []
    if "result" not in ss:
        set_result(run(ss.config), source="Initial run")
    ss.setdefault("eve_comparison", None)


def config() -> ExperimentConfig:
    return st.session_state.config


def result() -> ExperimentResult:
    return st.session_state.result


def set_result(res: ExperimentResult, source: str) -> None:
    ss = st.session_state
    ss.result = res
    ss.config = res.config
    m = res.metrics()
    ss.history.insert(
        0,
        {
            "time": time.strftime("%H:%M:%S"),
            "source": source,
            "pairs": m["total_pairs"],
            "eve": "on" if m["eve_enabled"] else "off",
            "noise": res.config.depolarizing_noise,
            "S": m["chsh_s"],
            "QBER": m["qber"],
            "final_bits": m["final_key_length"],
            "status": m["security_status"],
            "seed": m["seed"],
            "config_json": res.config.to_json(),
        },
    )
    del ss.history[HISTORY_LIMIT:]


def run_and_store(cfg: ExperimentConfig, source: str) -> ExperimentResult | None:
    """Run with user-facing error handling; returns None (and shows the reason) on invalid input."""
    try:
        res = run(cfg)
    except ConfigError as exc:
        st.error(f"Configuration not accepted: {exc}")
        return None
    except Exception as exc:  # pragma: no cover - defensive: never crash the page
        st.error(f"The simulation failed unexpectedly ({type(exc).__name__}: {exc}). Try different parameters or reset.")
        return None
    set_result(res, source)
    return res


def reset() -> None:
    ss = st.session_state
    ss.config = ExperimentConfig().validate()
    ss.eve_comparison = None
    set_result(run(ss.config), source="Reset to defaults")


def with_seed(cfg: ExperimentConfig, seed: int) -> ExperimentConfig:
    return replace(cfg, seed=seed)
