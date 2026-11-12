"""Classical post-processing of Shor's algorithm for small N.

The quantum step of Shor's algorithm is period finding: it finds the order r of a
modulo N (the smallest r with a^r ≡ 1 mod N). Here that step is simulated by brute
force, which is only feasible because N is tiny. Everything after it is classical:
if r is even and a^(r/2) ≢ −1 (mod N), gcd(a^(r/2) ± 1, N) gives the factors.
"""

from __future__ import annotations

from math import gcd

SUPPORTED_N = (15, 21)
MAX_N = 10_000


def _is_odd_composite(n: int) -> bool:
    if n < 9 or n % 2 == 0:
        return False
    return any(n % d == 0 for d in range(3, int(n**0.5) + 1, 2))


def order_mod(a: int, n: int) -> int:
    """Smallest r > 0 with a^r ≡ 1 (mod n); brute force stands in for the quantum period finding."""
    value = a % n
    r = 1
    while value != 1:
        value = (value * a) % n
        r += 1
    return r


def factor_steps(n: int, a: int) -> list[tuple[str, str]]:
    """Step-by-step Shor post-processing for N with base a; returns (step, value) rows for display."""
    if not isinstance(n, int) or isinstance(n, bool) or not _is_odd_composite(n) or n > MAX_N:
        raise ValueError(f"N must be an odd composite number no larger than {MAX_N:,}.")
    if not 1 < a < n or gcd(a, n) != 1:
        raise ValueError(f"The base a must satisfy 1 < a < N and gcd(a, N) = 1; got a = {a}.")

    steps: list[tuple[str, str]] = [("Choose N", str(n)), ("Choose base a", str(a))]
    g = gcd(a, n)
    steps.append(("gcd(a, N)", str(g)))

    r = order_mod(a, n)
    steps.append(("Period r (quantum step, simulated)", str(r)))
    if r % 2 == 1:
        steps.append(("Result", f"r = {r} is odd, retry with another base"))
        return steps

    half = pow(a, r // 2, n)
    steps.append((f"a^(r/2) mod N", str(half)))
    if half == n - 1:
        steps.append(("Result", "a^(r/2) ≡ −1 (mod N), retry with another base"))
        return steps

    f1, f2 = gcd(half - 1, n), gcd(half + 1, n)
    steps.append(("gcd(a^(r/2) − 1, N)", str(f1)))
    steps.append(("gcd(a^(r/2) + 1, N)", str(f2)))
    factors = sorted({f for f in (f1, f2) if 1 < f < n})
    steps.append(("Factors", " × ".join(str(f) for f in factors)))
    return steps


def factors_of(n: int, a: int) -> tuple[int, ...] | None:
    """The non-trivial factors found for base a, or None if this base does not work."""
    steps = factor_steps(n, a)
    label, value = steps[-1]
    if label != "Factors":
        return None
    return tuple(int(x) for x in value.split(" × "))


def bases_for(n: int) -> list[int]:
    return [a for a in range(2, n) if gcd(a, n) == 1]


def first_working_base(n: int) -> int:
    for a in bases_for(n):
        if factors_of(n, a) is not None:
            return a
    raise ValueError(f"No working base found for N = {n}.")
