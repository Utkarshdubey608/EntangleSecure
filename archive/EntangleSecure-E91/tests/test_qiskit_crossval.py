"""Optional cross-validation against Qiskit (skipped when Qiskit is not installed).

pip install -r requirements-dev.txt
"""

import numpy as np
import pytest

qiskit = pytest.importorskip("qiskit")
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.quantum_info import DensityMatrix, Statevector  # noqa: E402

from entanglesecure.quantum import density_matrix, joint_probabilities, prepare_singlet_statevector  # noqa: E402

ANGLES = np.radians([0, 45, 90, 135, 30])


def _qiskit_singlet() -> QuantumCircuit:
    qc = QuantumCircuit(2)
    qc.x([0, 1])
    qc.h(0)
    qc.cx(0, 1)
    return qc


def _to_our_order(vec: np.ndarray) -> np.ndarray:
    """Qiskit is little-endian (qubit 0 rightmost); we use |q0 q1>."""
    return vec.reshape(2, 2).T.reshape(4)


def test_singlet_state_matches_qiskit():
    sv = Statevector.from_instruction(_qiskit_singlet()).data
    np.testing.assert_allclose(_to_our_order(sv), prepare_singlet_statevector(), atol=1e-12)


def test_measurement_probabilities_match_qiskit():
    rho = density_matrix(prepare_singlet_statevector())
    for a in ANGLES:
        for b in ANGLES:
            qc = _qiskit_singlet()
            qc.ry(-a, 0)
            qc.ry(-b, 1)
            probs = DensityMatrix.from_instruction(qc).probabilities_dict()
            ours = joint_probabilities(rho, a, b)
            # Qiskit key 'q1q0'; outcome bit 0 ↔ +1.
            for i in range(2):
                for j in range(2):
                    assert ours[i, j] == pytest.approx(probs.get(f"{j}{i}", 0.0), abs=1e-12)
