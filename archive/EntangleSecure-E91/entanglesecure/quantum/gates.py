"""Single- and two-qubit gates as dense NumPy matrices.

Two-qubit operators act on the basis |q0 q1> with q0 (Alice) as the most
significant (left) tensor factor, i.e. |q0 q1> = |q0> ⊗ |q1>.
"""

from __future__ import annotations

from functools import reduce

import numpy as np

I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)
H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)

# CNOT with control q0 and target q1 in the |q0 q1> ordering.
CNOT = np.array(
    [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0],
    ],
    dtype=complex,
)


def kron(*ops: np.ndarray) -> np.ndarray:
    """Tensor product of operators in the given (left = most significant) order."""
    return reduce(np.kron, ops)


def ry(theta: float) -> np.ndarray:
    """Rotation about the y axis of the Bloch sphere: exp(-i θ Y / 2)."""
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def on_qubit(op: np.ndarray, qubit: int) -> np.ndarray:
    """Embed a single-qubit operator in the two-qubit space."""
    if qubit == 0:
        return kron(op, I2)
    if qubit == 1:
        return kron(I2, op)
    raise ValueError(f"qubit must be 0 or 1, got {qubit}")
