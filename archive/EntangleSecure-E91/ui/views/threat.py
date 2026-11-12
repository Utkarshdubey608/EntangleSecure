"""Page — Quantum threat: what Shor's and Grover's algorithms do to today's keys."""

from __future__ import annotations

import streamlit as st

from entanglesecure.quantum.threat import SUPPORTED_N, bases_for, factor_steps, first_working_base

from .. import components, nav

KEY_TABLE = [
    ("RSA-2048", "Factoring (Shor)", "Broken: polynomial time on a large fault-tolerant quantum computer", "Replace with post-quantum key exchange or signatures"),
    ("AES-128", "Brute-force search (Grover)", "Effective strength roughly halved to 64 bits", "Use AES-256"),
    ("AES-256", "Brute-force search (Grover)", "Effective strength roughly 128 bits, still considered safe", "No change needed"),
]


def render() -> None:
    components.page_header(
        "Quantum threat",
        "How a quantum computer would break RSA, and why E91 key distribution is a different kind of defence.",
    )

    st.subheader("The idea in plain words")
    st.markdown(
        "RSA's security rests on one fact: multiplying two big primes is easy, but splitting the product back into primes "
        "is hard for ordinary computers. Shor's algorithm uses a quantum computer to find the period of a function "
        "a^x mod N quickly. From that period, a classical computer gets the factors with a gcd, which is easy."
    )

    st.subheader("Worked example: Shor's algorithm on small N")
    choice = st.selectbox("Number to factor, N", SUPPORTED_N, index=0, format_func=lambda n: f"N = {n}")
    default_a = first_working_base(choice)
    a = st.selectbox("Base a (coprime to N)", bases_for(choice), index=bases_for(choice).index(default_a))

    try:
        steps = factor_steps(choice, a)
    except ValueError as exc:
        st.warning(str(exc))
        return

    st.table({"Step": [s for s, _ in steps], "Value": [v for _, v in steps]})
    components.note(
        "The period-finding step is the only quantum part of Shor's algorithm. Here it is simulated by brute force, "
        "which is fine for N = 15 or 21 but would be hopeless for a 2048-bit RSA modulus. Every other step is classical."
    )

    st.subheader("What this means for keys today")
    st.table({
        "Cryptosystem": [r[0] for r in KEY_TABLE],
        "Attack": [r[1] for r in KEY_TABLE],
        "Effect of a large quantum computer": [r[2] for r in KEY_TABLE],
        "Advice": [r[3] for r in KEY_TABLE],
    })
    components.note(
        "E91 is not a replacement for RSA signatures. Its security comes from the laws of physics (a Bell test) rather "
        "than from a hard mathematical problem, so a quantum computer does not break it. Eve is detected through the "
        "CHSH value, as on the Eavesdropping page."
    )
    nav.link(st, "eavesdropping", "See the eavesdropping check", ":material/policy:")
