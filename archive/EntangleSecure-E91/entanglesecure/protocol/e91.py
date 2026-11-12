"""Quantum stage of E91: entangled source, distribution, (attack), measurement.

Every pair passes through the same physical pipeline
    |ψ⁻> source → depolarizing channels → [Eve: measure-resend on Bob's arm] → Alice & Bob measure
so the Born-rule distribution of every possible branch can be computed once
from the density matrix and then sampled shot by shot — exactly what a
shot-based quantum simulator does. No outcome probability is written by hand.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..quantum import (
    concurrence,
    density_matrix,
    depolarize_both,
    fidelity_with_pure,
    joint_probabilities,
    prepare_singlet_statevector,
)
from .config import ExperimentConfig
from .eve import EveBranch, intercept_resend_branches
from .roles import ROLE_LOST, ROLE_MATRIX, ROLE_NAMES

# Independent random streams so that e.g. toggling Eve keeps Alice's and Bob's setting choices.
STREAM_SETTINGS, STREAM_EVE, STREAM_OUTCOMES, STREAM_LOSS, STREAM_CLASSICAL = range(5)
N_STREAMS = 5

OUTCOME_PAIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))  # flattened index of the 2×2 joint table


def rng_streams(seed: int) -> list[np.random.Generator]:
    return [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(N_STREAMS)]


@dataclass
class QuantumModel:
    """Exact states and Born-rule tables for one configuration."""

    psi_singlet: np.ndarray
    rho_source: np.ndarray
    rho_channel: np.ndarray
    eve_branches: list[EveBranch]
    # joint[branch, i, j, k]: P(outcome pair k | settings i, j); branch 0 = not intercepted,
    # branch 1 + 2·angle_index + (0 if e = +1 else 1) = intercepted with Eve outcome e.
    joint: np.ndarray
    eve_outcome_probs: np.ndarray  # [angle_index, 0/1] = p(e = +1 / −1)

    @property
    def concurrence_source(self) -> float:
        return concurrence(self.rho_source)

    @property
    def concurrence_channel(self) -> float:
        return concurrence(self.rho_channel)

    @property
    def fidelity_channel(self) -> float:
        return fidelity_with_pure(self.rho_channel, self.psi_singlet)


def build_quantum_model(config: ExperimentConfig) -> QuantumModel:
    alice = np.radians(config.alice_angles_deg)
    bob = np.radians(config.bob_angles_deg)
    psi = prepare_singlet_statevector()
    rho_source = density_matrix(psi)
    rho_channel = depolarize_both(rho_source, config.depolarizing_noise)

    eve_rad = np.radians(config.eve.basis_angles_deg)
    branches = intercept_resend_branches(rho_channel, eve_rad) if config.eve.enabled else []
    states = [rho_channel] + [b.state for b in branches]

    joint = np.empty((len(states), 3, 3, 4))
    for s, rho in enumerate(states):
        for i, a in enumerate(alice):
            for j, b in enumerate(bob):
                joint[s, i, j] = joint_probabilities(rho, a, b).reshape(4)

    eve_p = np.array([[br.probability for br in branches[2 * k : 2 * k + 2]] for k in range(len(eve_rad))]) if branches else np.zeros((0, 2))
    return QuantumModel(psi, rho_source, rho_channel, branches, joint, eve_p)


@dataclass
class RoundData:
    """One row per entangled pair, stored column-wise."""

    alice_setting: np.ndarray  # int8 in {0,1,2}
    bob_setting: np.ndarray
    alice_outcome: np.ndarray  # int8 ±1 (0 if not detected)
    bob_outcome: np.ndarray
    detected: np.ndarray  # bool: both detectors clicked
    role: np.ndarray  # int8, see roles.ROLE_*
    intercepted: np.ndarray  # bool
    eve_angle_index: np.ndarray  # int8, −1 if not intercepted
    eve_outcome: np.ndarray  # int8 ±1, 0 if not intercepted

    def __len__(self) -> int:
        return int(self.alice_setting.size)

    def subset(self, mask: np.ndarray) -> RoundData:
        return RoundData(**{k: v[mask] for k, v in self.__dict__.items()})

    def head(self, n: int) -> RoundData:
        return RoundData(**{k: v[:n] for k, v in self.__dict__.items()})

    def to_frame(self, config: ExperimentConfig) -> pd.DataFrame:
        alice_deg = np.asarray(config.alice_angles_deg)
        bob_deg = np.asarray(config.bob_angles_deg)
        eve_deg = np.asarray(config.eve.basis_angles_deg, dtype=float)
        eve_angle = np.full(len(self), np.nan)
        hit = self.eve_angle_index >= 0
        eve_angle[hit] = eve_deg[self.eve_angle_index[hit]]
        return pd.DataFrame(
            {
                "round": np.arange(1, len(self) + 1),
                "alice_setting": [f"A{i}" for i in self.alice_setting],
                "alice_angle_deg": alice_deg[self.alice_setting],
                "bob_setting": [f"B{j}" for j in self.bob_setting],
                "bob_angle_deg": bob_deg[self.bob_setting],
                "alice_outcome": self.alice_outcome,
                "bob_outcome": self.bob_outcome,
                "detected": self.detected,
                "role": [ROLE_NAMES[int(r)] for r in self.role],
                "eve_intercepted": self.intercepted,
                "eve_angle_deg": eve_angle,
                "eve_outcome": self.eve_outcome,
            }
        )


def sample_rounds(config: ExperimentConfig, model: QuantumModel) -> RoundData:
    """Draw one measurement shot per entangled pair from the Born-rule tables."""
    n = config.n_pairs
    streams = rng_streams(config.seed)
    settings_rng, eve_rng = streams[STREAM_SETTINGS], streams[STREAM_EVE]
    outcome_rng, loss_rng = streams[STREAM_OUTCOMES], streams[STREAM_LOSS]

    a_set = settings_rng.integers(0, 3, size=n).astype(np.int8)
    b_set = settings_rng.integers(0, 3, size=n).astype(np.int8)

    branch = np.zeros(n, dtype=np.int64)
    intercepted = np.zeros(n, dtype=bool)
    eve_angle = np.full(n, -1, dtype=np.int8)
    eve_out = np.zeros(n, dtype=np.int8)
    if config.eve.enabled:
        n_angles = len(config.eve.basis_angles_deg)
        attack_u = eve_rng.random(n)
        angle_idx = eve_rng.integers(0, n_angles, size=n)
        outcome_u = eve_rng.random(n)
        intercepted = attack_u < config.eve.intercept_fraction
        e_plus = outcome_u < model.eve_outcome_probs[angle_idx, 0]
        eve_angle = np.where(intercepted, angle_idx, -1).astype(np.int8)
        eve_out = np.where(intercepted, np.where(e_plus, 1, -1), 0).astype(np.int8)
        branch = np.where(intercepted, 1 + 2 * angle_idx + (~e_plus).astype(np.int64), 0)

    # Joint (x, y) outcome by inverse-CDF sampling of the per-round Born distribution.
    probs = model.joint[branch, a_set, b_set]  # (n, 4)
    cdf = np.cumsum(probs, axis=1)
    u = outcome_rng.random(n)
    k = (u[:, None] >= cdf[:, :3]).sum(axis=1)
    pairs = np.asarray(OUTCOME_PAIRS, dtype=np.int8)
    a_out, b_out = pairs[k, 0], pairs[k, 1]

    eta = config.detection_efficiency
    detected = (loss_rng.random(n) < eta) & (loss_rng.random(n) < eta) if eta < 1.0 else np.ones(n, dtype=bool)
    a_out = np.where(detected, a_out, 0).astype(np.int8)
    b_out = np.where(detected, b_out, 0).astype(np.int8)

    role = ROLE_MATRIX[a_set, b_set].copy()
    role[~detected] = ROLE_LOST

    return RoundData(a_set, b_set, a_out, b_out, detected, role, intercepted, eve_angle, eve_out)
