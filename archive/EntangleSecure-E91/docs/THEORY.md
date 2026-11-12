# Theory and simulation methods

## 1. Conventions

* Qubit basis |0⟩, |1⟩ are eigenstates of Z. Two-qubit kets are |q₀ q₁⟩ = |q₀⟩ ⊗ |q₁⟩, with q₀ for Alice and q₁ for Bob.
* A measurement direction θ is the Bloch vector **n**(θ) = (sin θ, 0, cos θ), measured from +z toward +x.
* Observable: σ(θ) = **n**·**σ** = cos θ Z + sin θ X.
* Eigenstates:
  * |+θ⟩ = cos(θ/2)|0⟩ + sin(θ/2)|1⟩, with eigenvalue +1 and key bit 0.
  * |−θ⟩ = −sin(θ/2)|0⟩ + cos(θ/2)|1⟩, with eigenvalue −1 and key bit 1.
* Measuring along θ means applying R_y(−θ) = exp(+iθY/2) and then measuring Z, because R_y(−θ)|±θ⟩ = |0⟩, |1⟩.
* **Photons.** A polarisation measurement at polariser angle φ corresponds to θ = 2φ. Ekert's spin directions 0°, 45°, 90° therefore become polariser angles 0°, 22.5°, 45°.

## 2. The singlet and its statistics

Preparation from |00⟩:

| Gate | State |
|------|-------|
| — | \|00⟩ |
| X ⊗ X | \|11⟩ |
| H ⊗ I | (\|0⟩ − \|1⟩)\|1⟩/√2 = (\|01⟩ − \|11⟩)/√2 |
| CNOT(0→1) | (\|01⟩ − \|10⟩)/√2 = \|ψ⁻⟩ |

The singlet is rotationally invariant: (U⊗U)|ψ⁻⟩ = det(U)|ψ⁻⟩. Hence σ(θ)⊗σ(θ)|ψ⁻⟩ = −|ψ⁻⟩ for every θ, and two identical directions always give opposite outcomes.

Joint distribution:

P(x, y | a, b) = Tr[(Π_x^a ⊗ Π_y^b) |ψ⁻⟩⟨ψ⁻|] = (1 − x·y·cos(a − b)) / 4,

with marginals P(x) = P(y) = ½. Each party alone sees a fair coin, so no signalling is possible. The correlation is

E(a,b) = Σ xy·P(x,y) = −cos(a − b).

Concurrence C(ψ⁻) = 1 (maximal entanglement).

## 3. Protocol rounds

Alice draws i ∈ {0,1,2} and Bob draws j ∈ {0,1,2}, uniformly and independently. With A = (0°, 45°, 90°) and B = (45°, 90°, 135°):

|   | B0 = 45° | B1 = 90° | B2 = 135° |
|---|---------|---------|----------|
| **A0 = 0°** | CHSH, E = −1/√2 | discard, E = 0 | CHSH, E = +1/√2 |
| **A1 = 45°** | **key**, E = −1 | discard, E = −1/√2 | discard, E = 0 |
| **A2 = 90°** | CHSH, E = −1/√2 | **key**, E = −1 | CHSH, E = −1/√2 |

After the settings are announced publicly:

* **Key rounds (2/9).** Both outcomes are mapped to bits. Bob inverts his bit because the singlet is anti-correlated; the rule is "flip if cos(a − b) > 0".
* **CHSH rounds (4/9).** These are used for the Bell test and are not used for the key.
* **Discarded rounds (3/9).** These are announced and dropped.
* **Lost rounds.** If either detector misses (each with probability 1 − η), the round is dropped. This is the fair-sampling assumption.

## 4. CHSH test

S = |E(a,b) + E(a,b′) + E(a′,b) − E(a′,b′)|.

**Local realism.** Suppose outcomes are pre-assigned values A(a), A(a′), B(b), B(b′) ∈ {±1}. Then

A(a)[B(b) + B(b′)] + A(a′)[B(b) − B(b′)] = ±2.

One bracket is always 0 and the other ±2. Averaging over hidden variables therefore gives |S| ≤ 2. (`tests/test_chsh.py` checks all 16 deterministic strategies.)

**Quantum bound.** Tsirelson's bound is S ≤ 2√2. With a = A2 = 90°, a′ = A0 = 0°, b = B0 = 45° and b′ = B2 = 135°:

S = |(−1/√2) + (−1/√2) + (−1/√2) − (+1/√2)| = 4/√2 = 2√2.

This is identical to Ekert's form S = E(a₁,b₁) − E(a₁,b₃) + E(a₃,b₁) + E(a₃,b₃) = −2√2.

**Choosing the sign placement.** Each of the four placements of the minus sign defines a valid CHSH inequality. The code chooses the placement that maximises |S| for an ideal singlet at the configured angles. This choice is made a priori, without looking at the data, so the estimator carries no selection bias.

**Statistics.** Each correlator is the mean of a ±1 variable with variance 1 − E². So:

* σ_E = √((1 − E²)/N).
* The four correlators are estimated from disjoint rounds, so σ_S = √(Σ σ_E²).
* Significance is (S − 2)/σ_S.
* The security decision uses S_low = S − zσ_S, with z = 2 by default.

## 5. Channel noise

Depolarizing channel on each particle: D_p(ρ) = (1 − p)ρ + p·I/2, with Kraus operators √(1 − 3p/4)·I and √(p/4)·{X, Y, Z}.

Applying it to both particles of the singlet gives the Werner state ρ = V|ψ⁻⟩⟨ψ⁻| + (1 − V)·I/4, with V = (1 − p)². Then:

* E(a,b) = −V cos(a − b).
* S = 2√2·V. This drops below 2 at V = 1/√2, i.e. p ≈ 0.159.
* QBER = (1 − V)/2.
* Concurrence = max(0, (3V − 1)/2).

## 6. Intercept-resend eavesdropping

Eve intercepts a fraction q of Bob's particles. She picks θ_E uniformly from a set Θ, measures with outcome e, and resends |e, θ_E⟩.

Because Π_e is rank-1 on Bob's qubit, measure-and-resend equals the Lüders update

ρ → (I ⊗ Π_e^{θ_E}) ρ (I ⊗ Π_e^{θ_E}) / p_e.

For the singlet this leaves Alice with |−e, θ_E⟩. The pair is now a product state, and

E_attacked(a,b) = ⟨−e cos(a − θ_E)⟩⟨e cos(b − θ_E)⟩ = −cos(a − θ_E)·cos(b − θ_E).

Overall correlation:

E(a,b) = V·[(1 − q)(−cos(a − b)) + q·mean_θ(−cos(a − θ)cos(b − θ))].

Every separable state satisfies CHSH, so for q = 1 S can never exceed 2, whatever Θ is.

**Guessing among Bob's directions** (Θ = {45°, 90°, 135°}, q = 1, V = 1):

* Key setting 45°: mean cos² over Θ is (1 + ½ + 0)/3 = ½, so QBER = (1 − ½)/2 = 25 %.
* Key setting 90°: mean cos² over Θ is (½ + 1 + ½)/3 = ⅔, so QBER = (1 − ⅔)/2 = 16.7 %.
* Averaged, QBER = 20.83 % and S = √2.

S and QBER both change linearly in q. With the default 2σ margin, the protocol aborts at much smaller q, depending on N.

**Eve's knowledge.** On intercepted key rounds, Eve's guess of Bob's bit is her own outcome. It agrees with Bob with probability (1 + cos(φ − θ_E))/2.

## 7. Classical post-processing

1. **Sifting.** Keep the key rounds, map outcomes to bits, and apply Bob's flip.
2. **Parameter estimation.** Reveal a random fraction f of the sifted bits, by default 20 %. The error rate of this sample is the QBER estimate; the revealed bits are then discarded.
3. **Bell check.** If S_low ≤ 2, abort.
4. **Cascade** (Brassard & Salvail, 1993):
   * Pass 1 uses contiguous blocks of size k₁ = ⌈0.73/Q⌉, with Q floored at 0.5 %.
   * Each later pass applies a fresh public permutation and doubles the block size.
   * A block whose parity differs is bisected (BINARY) to find one error, which is then flipped.
   * The correction is cascaded: every earlier-pass block that contains the flipped bit has its parity re-checked.
   * Every parity Alice reveals counts as leaked. A 64-bit random-matrix hash then verifies equality, and its 64 bits are also counted as leaked.
5. **Privacy amplification.** A random Toeplitz matrix T over GF(2), of size ℓ×n with n + ℓ − 1 seed bits, maps the corrected key to ℓ bits: y = T·x mod 2. It is computed as a linear convolution, using FFT for large n. Toeplitz matrices form a universal₂ hash family, so the leftover-hash lemma applies.
6. **Key length.** ℓ = ⌊n·(1 − χ(S_low)) − leak_EC⌋, where χ(S) = h((1 + √((S/2)² − 1))/2).
   * χ(S) is the Acín et al. (2007) upper bound on Eve's Holevo information, for collective attacks in the device-independent setting.
   * At S = 2√2, χ = 0. At S ≤ 2, χ = 1 and no key is possible.

For comparison, the device-dependent BBM92 rate 1 − 2h(Q) is also reported. It becomes positive below Q ≈ 11 %.

## 8. Sampling method

All rounds share the same pre-measurement state (or one of 2|Θ| Eve branches), so the engine works in three steps:

1. Compute ρ exactly: circuit, then Kraus noise, then optional Lüders update.
2. For every (branch, i, j), compute the 4-entry Born distribution P(x,y) = diag[(U_a⊗U_b)ρ(U_a⊗U_b)†].
3. For every round, draw the settings, Eve's interception, direction and outcome, and then (x, y) from the matching distribution by inverse-CDF sampling.

This is exactly what shot-based simulators do: they compute the state once and sample shots. Sampling the joint outcome in one draw is equivalent to sequential collapse, P(x,y) = P(x)·P(y|x). The "single pair" view in the laboratory shows that decomposition explicitly for any recorded pair.

Independent `SeedSequence` streams are used for settings, Eve, outcomes, losses and the classical stage. A fixed seed therefore reproduces everything, and toggling Eve leaves Alice's and Bob's setting choices unchanged.

## References

* A. K. Ekert, "Quantum cryptography based on Bell's theorem," *Phys. Rev. Lett.* 67, 661 (1991).
* J. F. Clauser, M. A. Horne, A. Shimony, R. A. Holt, *Phys. Rev. Lett.* 23, 880 (1969).
* B. S. Tsirelson, *Lett. Math. Phys.* 4, 93 (1980).
* C. H. Bennett, G. Brassard, N. D. Mermin, "Quantum cryptography without Bell's theorem," *Phys. Rev. Lett.* 68, 557 (1992).
* G. Brassard, L. Salvail, "Secret-key reconciliation by public discussion," *EUROCRYPT '93*.
* A. Acín, N. Brunner, N. Gisin, S. Massar, S. Pironio, V. Scarani, "Device-independent security of quantum cryptography against collective attacks," *Phys. Rev. Lett.* 98, 230501 (2007).
* W. K. Wootters, "Entanglement of formation of an arbitrary state of two qubits," *Phys. Rev. Lett.* 80, 2245 (1998).
