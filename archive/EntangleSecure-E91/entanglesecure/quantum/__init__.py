"""Exact two-qubit density-matrix simulator used by the E91 engine."""

from .channels import apply_channel, depolarize_both, depolarizing_kraus
from .measurement import (
    correlation,
    eigenstate,
    joint_probabilities,
    joint_probabilities_projective,
    measure_qubit,
    projector,
    spin_observable,
)
from .states import (
    bloch_vector,
    concurrence,
    density_matrix,
    fidelity_with_pure,
    is_valid_density_matrix,
    partial_trace,
    prepare_singlet_statevector,
    purity,
    singlet_circuit_trace,
)

__all__ = [
    "apply_channel",
    "bloch_vector",
    "concurrence",
    "correlation",
    "density_matrix",
    "depolarize_both",
    "depolarizing_kraus",
    "eigenstate",
    "fidelity_with_pure",
    "is_valid_density_matrix",
    "joint_probabilities",
    "joint_probabilities_projective",
    "measure_qubit",
    "partial_trace",
    "prepare_singlet_statevector",
    "projector",
    "purity",
    "singlet_circuit_trace",
    "spin_observable",
]
