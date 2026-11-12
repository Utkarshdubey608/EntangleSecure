"""Shor's algorithm against a toy RSA-encrypted ballot.

The modulus is deliberately tiny so the quantum step (finding the period r of a^x mod N)
can be simulated classically by brute force. Everything around it is exactly the
classical part of Shor's algorithm, which is what turns that period into the private key.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

TOY_PRIMES = (41, 43, 47, 53, 59, 61, 67, 71, 73, 79)
PUBLIC_EXPONENT = 17


@dataclass
class ToyRSA:
    p: int
    q: int
    e: int = PUBLIC_EXPONENT

    @property
    def n(self) -> int:
        return self.p * self.q

    @property
    def phi(self) -> int:
        return (self.p - 1) * (self.q - 1)

    @property
    def d(self) -> int:
        return pow(self.e, -1, self.phi)

    def encrypt(self, m: int) -> int:
        return pow(m, self.e, self.n)


def make_toy_rsa(rng: random.Random) -> ToyRSA:
    while True:
        p, q = rng.sample(TOY_PRIMES, 2)
        if math.gcd(PUBLIC_EXPONENT, (p - 1) * (q - 1)) == 1:
            return ToyRSA(p, q)


def multiplicative_order(a: int, n: int) -> int:
    """Smallest r > 0 with a^r ≡ 1 (mod n). This is the step a quantum computer does with the QFT."""
    if math.gcd(a, n) != 1:
        raise ValueError("a must be coprime to n")
    value, r = a % n, 1
    while value != 1:
        value = (value * a) % n
        r += 1
    return r


def factor_with_period(n: int, rng: random.Random, max_tries: int = 200) -> tuple[int, int, int, list[dict]]:
    """Return (p, q, a, steps) using Shor's reduction from factoring to order finding."""
    steps: list[dict] = []
    bases = list(range(2, n - 1))
    rng.shuffle(bases)
    for a in bases[:max_tries]:
        g = math.gcd(a, n)
        if g != 1:
            continue
        r = multiplicative_order(a, n)
        half = pow(a, r // 2, n) if r % 2 == 0 else None
        if half is None or half == n - 1:
            steps.append({"title": f"Base a = {a} rejected", "detail": f"Period r = {r} is {'odd' if r % 2 else 'even but a^(r/2) ≡ −1 (mod N)'}, so try another base."})
            continue
        p, q = math.gcd(half - 1, n), math.gcd(half + 1, n)
        if 1 < p < n and 1 < q < n:
            steps += [
                {"title": "Pick a random base", "detail": f"a = {a}, gcd({a}, {n}) = 1 so a shares no factor with N."},
                {"title": "Quantum period finding (simulated)", "detail": f"Find the smallest r with {a}^r ≡ 1 (mod {n}). A quantum computer gets r from the quantum Fourier transform in polynomial time; for this tiny N it is brute-forced classically. Result: r = {r}."},
                {"title": "Check the period is usable", "detail": f"r = {r} is even and {a}^{r // 2} mod {n} = {half} ≠ {n - 1}, so it splits N."},
                {"title": "Extract the factors with gcd", "detail": f"gcd({half} − 1, {n}) = {p} and gcd({half} + 1, {n}) = {q}. N = {p} × {q}."},
            ]
            return min(p, q), max(p, q), a, steps
    raise RuntimeError("No usable base found")
