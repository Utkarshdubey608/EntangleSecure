"""Step-by-step quantum state of a single recorded pair (for visualisation).

The joint outcome of each round was sampled from the Born distribution of the
pair's state; here the same probability is decomposed sequentially (Alice
first, then Bob conditioned on Alice's collapse), which is mathematically
identical, P(x, y) = P(x) · P(y | x).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..quantum import bloch_vector, concurrence, measure_qubit, partial_trace
from .experiment import ExperimentResult


@dataclass
class PairTrace:
    index: int
    alice_angle_deg: float
    bob_angle_deg: float
    intercepted: bool
    eve_angle_deg: float | None
    eve_outcome: int
    concurrence_before: float
    p_alice: dict[int, float]  # P(x) along Alice's direction
    alice_outcome: int
    bob_bloch_after: np.ndarray  # (x, y, z) of Bob's particle after Alice's collapse
    p_bob_given_alice: dict[int, float]  # P(y | x) along Bob's direction
    bob_outcome: int
    joint_probability: float  # P(x, y) of the outcome that actually occurred
    detected: bool


def trace_pair(res: ExperimentResult, index: int) -> PairTrace:
    if not 0 <= index < len(res.rounds):
        raise IndexError(f"pair index must be in [0, {len(res.rounds) - 1}]")
    r = res.rounds
    cfg = res.config
    a = float(cfg.alice_angles_deg[r.alice_setting[index]])
    b = float(cfg.bob_angles_deg[r.bob_setting[index]])
    hit = bool(r.intercepted[index])
    rho = res.model.rho_channel
    eve_angle = None
    if hit:
        k = int(r.eve_angle_index[index])
        e = int(r.eve_outcome[index])
        branch = next(br for br in res.model.eve_branches if br.angle_index == k and br.outcome == e)
        rho = branch.state
        eve_angle = float(cfg.eve.basis_angles_deg[k])

    detected = bool(r.detected[index])
    x = int(r.alice_outcome[index]) if detected else 1
    y = int(r.bob_outcome[index]) if detected else 1
    p_a = {o: measure_qubit(rho, 0, np.radians(a), o)[0] for o in (1, -1)}
    _, post = measure_qubit(rho, 0, np.radians(a), x)
    p_b = {o: measure_qubit(post, 1, np.radians(b), o)[0] for o in (1, -1)}
    return PairTrace(
        index=index,
        alice_angle_deg=a,
        bob_angle_deg=b,
        intercepted=hit,
        eve_angle_deg=eve_angle,
        eve_outcome=int(r.eve_outcome[index]),
        concurrence_before=concurrence(rho),
        p_alice=p_a,
        alice_outcome=x,
        bob_bloch_after=bloch_vector(partial_trace(post, 1)),
        p_bob_given_alice=p_b,
        bob_outcome=y,
        joint_probability=p_a[x] * p_b[y],
        detected=detected,
    )
