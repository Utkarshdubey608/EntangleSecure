"""Role of each (Alice setting, Bob setting) combination in the E91 protocol.

With Ekert's settings A = (0°, 45°, 90°), B = (45°, 90°, 135°):
  key     : (A1, B0), (A2, B1)                — identical directions, perfect anti-correlation
  chsh    : (A0, B0), (A0, B2), (A2, B0), (A2, B2) — Bell test
  discard : (A0, B1), (A1, B1), (A1, B2)
Roles are tied to setting *indices* (as in the protocol), not to the angle values.
"""

from __future__ import annotations

import math

import numpy as np

ROLE_KEY, ROLE_CHSH, ROLE_DISCARD, ROLE_LOST = 0, 1, 2, 3
ROLE_NAMES = {ROLE_KEY: "key", ROLE_CHSH: "chsh", ROLE_DISCARD: "discard", ROLE_LOST: "lost"}

KEY_SETTINGS: tuple[tuple[int, int], ...] = ((1, 0), (2, 1))
CHSH_SETTINGS: tuple[tuple[int, int], ...] = ((0, 0), (0, 2), (2, 0), (2, 2))

ROLE_MATRIX = np.full((3, 3), ROLE_DISCARD, dtype=np.int8)
for _i, _j in KEY_SETTINGS:
    ROLE_MATRIX[_i, _j] = ROLE_KEY
for _i, _j in CHSH_SETTINGS:
    ROLE_MATRIX[_i, _j] = ROLE_CHSH


def bob_flips(theta_a: float, theta_b: float) -> bool:
    """Bob inverts his key bit when the singlet predicts anti-correlation (cos(a − b) > 0)."""
    return math.cos(theta_a - theta_b) > 0
