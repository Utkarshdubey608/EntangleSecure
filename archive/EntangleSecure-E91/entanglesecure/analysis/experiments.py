"""Multi-run studies: finite-sample fluctuations, convergence and parameter sweeps.

All results are produced by running the simulator; theory columns are attached
only as overlays for comparison.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from ..protocol import ExperimentConfig, run_measurement_only, theory
from ..protocol.chsh import analyze_bell, choose_labelling
from ..protocol.roles import ROLE_KEY, bob_flips


def derived_seeds(seed: int, count: int) -> list[int]:
    """Deterministic, statistically independent seeds for repeated trials."""
    return [int(s.generate_state(1)[0]) for s in np.random.SeedSequence([seed, 0xE91]).spawn(count)]


def sifted_qber(rounds, alice_rad: np.ndarray, bob_rad: np.ndarray) -> float:
    """True QBER of the sifted key computed straight from the round table."""
    idx = rounds.role == ROLE_KEY
    if not idx.any():
        return float("nan")
    a = rounds.alice_outcome[idx]
    b = rounds.bob_outcome[idx]
    flips = np.array([[bob_flips(x, y) for y in bob_rad] for x in alice_rad])[rounds.alice_setting[idx], rounds.bob_setting[idx]]
    expected_b = np.where(flips, -a, a)
    return float(np.mean(b != expected_b))


def chsh_distribution(config: ExperimentConfig, trials: int) -> pd.DataFrame:
    """Repeat the experiment with independent seeds; one row per trial."""
    config = config.validate()
    alice_rad, bob_rad = np.radians(config.alice_angles_deg), np.radians(config.bob_angles_deg)
    rows = []
    for k, seed in enumerate(derived_seeds(config.seed, trials)):
        rounds, bell = run_measurement_only(replace(config, seed=seed))
        rows.append(
            {
                "trial": k + 1,
                "seed": seed,
                "S": bell.s_value,
                "S_stderr": bell.s_stderr,
                "qber": sifted_qber(rounds, alice_rad, bob_rad),
                "violates": bell.violates_classical,
            }
        )
    return pd.DataFrame(rows)


def convergence(config: ExperimentConfig, checkpoints: int = 40) -> pd.DataFrame:
    """S and its error bar computed on growing prefixes of one long run (the estimator converging as N grows)."""
    config = config.validate()
    rounds, full = run_measurement_only(config)
    alice_rad, bob_rad = np.radians(config.alice_angles_deg), np.radians(config.bob_angles_deg)
    th = theory.correlation_matrix(config)
    lab = choose_labelling(alice_rad, bob_rad)
    sizes = np.unique(np.geomspace(min(100, len(rounds)), len(rounds), checkpoints).astype(int))
    rows = []
    for n in sizes:
        bell = analyze_bell(rounds.head(int(n)), alice_rad, bob_rad, th, config.bell_confidence_sigma, lab)
        rows.append({"pairs": int(n), "S": bell.s_value, "S_stderr": bell.s_stderr, "S_theory": full.s_theory})
    return pd.DataFrame(rows)


def eve_sweep(config: ExperimentConfig, fractions: np.ndarray) -> pd.DataFrame:
    """Simulate S and QBER as a function of Eve's interception fraction q."""
    config = config.validate()
    alice_rad, bob_rad = np.radians(config.alice_angles_deg), np.radians(config.bob_angles_deg)
    rows = []
    for q in fractions:
        cfg = replace(config, eve=replace(config.eve, enabled=True, intercept_fraction=float(q)))
        rounds, bell = run_measurement_only(cfg)
        rows.append(
            {
                "intercept_fraction": float(q),
                "S": bell.s_value,
                "S_stderr": bell.s_stderr,
                "S_theory": theory.chsh_value(cfg, bell.labelling),
                "qber": sifted_qber(rounds, alice_rad, bob_rad),
                "qber_theory": theory.qber(cfg),
            }
        )
    return pd.DataFrame(rows)


def noise_sweep(config: ExperimentConfig, noise_levels: np.ndarray) -> pd.DataFrame:
    """Simulate S and QBER versus local depolarizing noise (Eve off)."""
    config = config.validate().with_eve(False)
    alice_rad, bob_rad = np.radians(config.alice_angles_deg), np.radians(config.bob_angles_deg)
    rows = []
    for p in noise_levels:
        cfg = replace(config, depolarizing_noise=float(p))
        rounds, bell = run_measurement_only(cfg)
        q = sifted_qber(rounds, alice_rad, bob_rad)
        rows.append(
            {
                "noise": float(p),
                "S": bell.s_value,
                "S_stderr": bell.s_stderr,
                "S_theory": theory.chsh_value(cfg, bell.labelling),
                "qber": q,
                "qber_theory": theory.qber(cfg),
                "di_rate": theory.di_key_rate(bell.s_value, q),
            }
        )
    return pd.DataFrame(rows)

