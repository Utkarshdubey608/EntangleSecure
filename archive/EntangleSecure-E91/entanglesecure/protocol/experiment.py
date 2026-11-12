"""End-to-end E91 experiment: quantum stage → Bell test → key distillation → metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from . import theory
from .chsh import BellAnalysis, analyze_bell
from .config import ExperimentConfig
from .e91 import STREAM_CLASSICAL, QuantumModel, RoundData, build_quantum_model, rng_streams, sample_rounds
from .postprocessing import KeyPipeline, bits_to_hex, run_key_pipeline
from .roles import ROLE_CHSH, ROLE_DISCARD, ROLE_KEY, ROLE_LOST

SECURE, INSECURE, INCONCLUSIVE = "SECURE", "COMPROMISED", "INCONCLUSIVE"


@dataclass
class ExperimentResult:
    config: ExperimentConfig
    model: QuantumModel
    rounds: RoundData
    bell: BellAnalysis
    keys: KeyPipeline
    theory_matrix: np.ndarray
    theory_qber: float
    runtime_s: float
    timestamp: float

    @property
    def security_status(self) -> str:
        if not np.isfinite(self.bell.s_value):
            return INCONCLUSIVE
        if self.keys.aborted:
            # Distinguish "Bell test passed but too little data/key" from a failed Bell test.
            return INCONCLUSIVE if self.bell.violation_confirmed else INSECURE
        return SECURE

    def role_counts(self) -> dict[str, int]:
        r = self.rounds.role
        return {
            "key": int(np.count_nonzero(r == ROLE_KEY)),
            "chsh": int(np.count_nonzero(r == ROLE_CHSH)),
            "discard": int(np.count_nonzero(r == ROLE_DISCARD)),
            "lost": int(np.count_nonzero(r == ROLE_LOST)),
        }

    def metrics(self) -> dict[str, Any]:
        rc = self.role_counts()
        k = self.keys
        n = self.config.n_pairs
        return {
            "total_pairs": n,
            "detected_rounds": int(self.rounds.detected.sum()),
            "lost_rounds": rc["lost"],
            "key_rounds": rc["key"],
            "chsh_rounds": rc["chsh"],
            "discarded_rounds": rc["discard"],
            "alice_key_length": len(k.sifted),
            "bob_key_length": len(k.sifted),
            "key_agreement": k.agreement,
            "qber": k.sifted_qber,
            "qber_estimate": k.qber_estimate,
            "qber_theory": self.theory_qber,
            "chsh_s": self.bell.s_value,
            "chsh_stderr": self.bell.s_stderr,
            "chsh_s_lower": self.bell.s_lower,
            "chsh_theory": self.bell.s_theory,
            "chsh_significance": self.bell.significance,
            "bell_violated": self.bell.violates_classical,
            "bell_violation_confirmed": self.bell.violation_confirmed,
            "eve_info_bound": k.eve_info_bound,
            "ec_leaked_bits": k.cascade.leaked_bits if k.cascade else 0,
            "ec_residual_errors": k.cascade.residual_errors if k.cascade else None,
            "final_key_length": k.final_length,
            "final_keys_match": k.keys_match,
            "secure_yield_per_pair": k.final_length / n,
            "di_rate_per_sifted_bit": k.di_rate,
            "bbm92_rate_per_sifted_bit": k.bbm92_rate,
            "eve_enabled": self.config.eve.enabled,
            "eve_intercepted_pairs": int(self.rounds.intercepted.sum()),
            "eve_key_agreement": k.eve_agreement,
            "entanglement_concurrence": self.model.concurrence_channel,
            "security_status": self.security_status,
            "abort_reason": k.abort_reason,
            "final_key_hex": bits_to_hex(k.final_alice),
            "runtime_s": self.runtime_s,
            "seed": self.config.seed,
        }


def run_experiment(config: ExperimentConfig) -> ExperimentResult:
    """Validate the configuration and run the complete protocol."""
    config = config.validate()
    t0 = time.perf_counter()
    alice_rad = np.radians(config.alice_angles_deg)
    bob_rad = np.radians(config.bob_angles_deg)

    model = build_quantum_model(config)
    rounds = sample_rounds(config, model)
    th_matrix = theory.correlation_matrix(config)
    bell = analyze_bell(rounds, alice_rad, bob_rad, th_matrix, config.bell_confidence_sigma)
    classical_rng = rng_streams(config.seed)[STREAM_CLASSICAL]
    keys = run_key_pipeline(rounds, bell, alice_rad, bob_rad, config.estimation_fraction, config.cascade_passes, classical_rng)

    return ExperimentResult(
        config=config,
        model=model,
        rounds=rounds,
        bell=bell,
        keys=keys,
        theory_matrix=th_matrix,
        theory_qber=theory.qber(config),
        runtime_s=time.perf_counter() - t0,
        timestamp=time.time(),
    )


def run_measurement_only(config: ExperimentConfig) -> tuple[RoundData, BellAnalysis]:
    """Quantum stage + Bell analysis only (fast path for sweeps and Monte-Carlo studies)."""
    config = config.validate()
    alice_rad = np.radians(config.alice_angles_deg)
    bob_rad = np.radians(config.bob_angles_deg)
    rounds = sample_rounds(config, build_quantum_model(config))
    bell = analyze_bell(rounds, alice_rad, bob_rad, theory.correlation_matrix(config), config.bell_confidence_sigma)
    return rounds, bell
