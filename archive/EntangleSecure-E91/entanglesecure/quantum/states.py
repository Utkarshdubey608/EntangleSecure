"""State preparation and state diagnostics for the two-qubit system."""

from __future__ import annotations

import numpy as np

from .gates import CNOT, I2, H, X, Y, Z, kron

KET_00 = np.array([1, 0, 0, 0], dtype=complex)

# Ordered list of (gate label, operator) applied to |00> to obtain |ψ⁻>.
SINGLET_CIRCUIT: tuple[tuple[str, np.ndarray], ...] = (
    ("X ⊗ X", kron(X, X)),
    ("H ⊗ I", kron(H, I2)),
    ("CNOT(0→1)", CNOT),
)


def prepare_singlet_statevector() -> np.ndarray:
    """Run the preparation circuit X⊗X → H⊗I → CNOT on |00>.

    |00> → |11> → (|0>-|1>)|1>/√2 → (|01> - |10>)/√2 = |ψ⁻>.
    """
    psi = KET_00.copy()
    for _, gate in SINGLET_CIRCUIT:
        psi = gate @ psi
    return psi


def singlet_circuit_trace() -> list[tuple[str, np.ndarray]]:
    """Statevector after each gate of the preparation circuit (for visualisation)."""
    psi = KET_00.copy()
    trace = [("|00⟩", psi.copy())]
    for label, gate in SINGLET_CIRCUIT:
        psi = gate @ psi
        trace.append((label, psi.copy()))
    return trace


def density_matrix(psi: np.ndarray) -> np.ndarray:
    """|ψ><ψ| for a normalised state vector."""
    psi = np.asarray(psi, dtype=complex).reshape(-1)
    return np.outer(psi, psi.conj())


def is_valid_density_matrix(rho: np.ndarray, atol: float = 1e-10) -> bool:
    """Hermitian, unit trace, positive semidefinite."""
    if not np.allclose(rho, rho.conj().T, atol=atol):
        return False
    if not np.isclose(np.trace(rho).real, 1.0, atol=atol):
        return False
    return bool(np.linalg.eigvalsh(rho).min() >= -atol)


def purity(rho: np.ndarray) -> float:
    """Tr(ρ²): 1 for pure states, 1/4 for the maximally mixed two-qubit state."""
    return float(np.trace(rho @ rho).real)


def partial_trace(rho: np.ndarray, keep: int) -> np.ndarray:
    """Reduced single-qubit density matrix of qubit ``keep`` (0 or 1)."""
    r = rho.reshape(2, 2, 2, 2)  # indices: a, b, a', b'
    if keep == 0:
        return np.einsum("ijkj->ik", r)
    if keep == 1:
        return np.einsum("ijil->jl", r)
    raise ValueError(f"keep must be 0 or 1, got {keep}")


def bloch_vector(rho_1q: np.ndarray) -> np.ndarray:
    """(⟨X⟩, ⟨Y⟩, ⟨Z⟩) of a single-qubit density matrix."""
    return np.array([np.trace(rho_1q @ P).real for P in (X, Y, Z)])


def concurrence(rho: np.ndarray) -> float:
    """Wootters concurrence of a two-qubit state (0 = separable, 1 = maximally entangled)."""
    yy = kron(Y, Y)
    rho_tilde = yy @ rho.conj() @ yy
    eigvals = np.linalg.eigvals(rho @ rho_tilde)
    lambdas = np.sort(np.sqrt(np.clip(eigvals.real, 0, None)))[::-1]
    return float(max(0.0, lambdas[0] - lambdas[1] - lambdas[2] - lambdas[3]))


def fidelity_with_pure(rho: np.ndarray, psi: np.ndarray) -> float:
    """<ψ|ρ|ψ>."""
    return float(np.real(psi.conj() @ rho @ psi))
