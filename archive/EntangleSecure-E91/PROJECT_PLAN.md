# EntangleSecure — Project Plan

**Design and Simulation of Entanglement-Based Quantum Key Distribution Using the E91 Protocol with Bell Inequality Analysis**

Course context: Quantum Communication and Cryptography.

---

## 1. Objectives and scope

| # | Objective | Deliverable |
|---|-----------|-------------|
| O1 | Simulate the Ekert-1991 (E91) protocol end to end with physically correct quantum statistics | `entanglesecure.quantum` + `entanglesecure.protocol` packages |
| O2 | Perform a CHSH Bell test on the simulated measurement data with finite-sample error analysis | `protocol/chsh.py`, Bell Analyzer page |
| O3 | Generate raw → sifted → error-corrected → privacy-amplified keys, never claiming every round contributes | `protocol/postprocessing.py` |
| O4 | Model a physically meaningful intercept-resend eavesdropper and show its detection via the CHSH value and QBER | `protocol/eve.py`, Eavesdropping page |
| O5 | Interactive six-page research dashboard with a premium dark UI | `app.py` + `ui/` |
| O6 | Reproducible, validated, documented software | seeds, JSON configs, unit tests, docs |

**In scope:** ideal singlet source, configurable measurement directions, local depolarizing channel noise, intercept-resend attack with configurable basis set and interception fraction, sifting, parameter estimation, Cascade error correction, Toeplitz-hash privacy amplification, asymptotic key-rate estimate, CSV/PDF/JSON reports.

**Out of scope (documented as limitations):** photon loss / detector inefficiency / multi-pair emission, finite-key composable security proofs, authenticated classical channel implementation, general coherent attacks.

---

## 2. Physical model and conventions

### 2.1 Qubits and measurement directions
* Computational basis |0⟩, |1⟩ = eigenstates of Pauli Z. Qubit 0 = Alice's particle, qubit 1 = Bob's particle; two-qubit basis order |q0 q1⟩.
* A measurement **direction** θ lies in the x–z plane of the Bloch sphere: **n**(θ) = (sin θ, 0, cos θ).
* Observable: σ(θ) = cos θ · Z + sin θ · X, eigenvalues ±1.
  Eigenstates: |+θ⟩ = cos(θ/2)|0⟩ + sin(θ/2)|1⟩, |−θ⟩ = −sin(θ/2)|0⟩ + cos(θ/2)|1⟩.
* Measurement is implemented circuit-style: apply R_y(−θ) (maps |±θ⟩ → |0⟩/|1⟩) and measure Z. Tests cross-check this against direct projectors.
* These are **spin-½ directions**, exactly as in Ekert's 1991 paper. For polarisation-encoded photons the physical polariser angle is θ/2 (Bloch angle = 2 × polariser angle), so 0°/45°/90° Bloch = 0°/22.5°/45° polariser.

### 2.2 Entangled source
Bell singlet |ψ⁻⟩ = (|01⟩ − |10⟩)/√2, prepared by an explicit circuit on |00⟩:
`X⊗X → H⊗I → CNOT(0→1)` ⇒ |11⟩ → (|0⟩−|1⟩)|1⟩/√2 → (|01⟩ − |10⟩)/√2.
The state is carried as a 4×4 density matrix so that noise and Eve's measurement are exact quantum operations.

Singlet correlation: E(a,b) = ⟨σ(a)⊗σ(b)⟩ = −**n**(a)·**n**(b) = **−cos(a − b)**.

### 2.3 Settings (Ekert 1991)
| Party | index 0 | index 1 | index 2 |
|-------|---------|---------|---------|
| Alice | A0 = 0° | A1 = 45° | A2 = 90° |
| Bob   | B0 = 45° | B1 = 90° | B2 = 135° |

Each party picks a setting uniformly and independently per round. Of the 9 combinations:

| Role | Combinations | Probability | Purpose |
|------|--------------|-------------|---------|
| **Key** | (A1,B0), (A2,B1) — identical directions | 2/9 | perfectly anti-correlated ⇒ key bits (Bob flips his bit) |
| **CHSH** | (A0,B0), (A0,B2), (A2,B0), (A2,B2) | 4/9 | Bell test |
| **Discard** | (A0,B1), (A1,B1), (A1,B2) | 3/9 | neither — discarded after public discussion |

Roles are fixed by setting index (as in the protocol); angles are user-configurable. If the user misaligns the key directions, the QBER rises — a physically meaningful consequence, not an error.

### 2.4 CHSH
S = |E(a,b) + E(a,b′) + E(a′,b) − E(a′,b′)| with a, a′ ∈ {A0, A2} and b, b′ ∈ {B0, B2}.
Which correlator carries the minus sign is chosen **a priori from the configured angles** (the placement maximising the ideal-singlet |S|), never from the data, to avoid selection bias. For the default angles: a = A2 = 90°, a′ = A0 = 0°, b = B0 = 45°, b′ = B2 = 135°:
S = |−1/√2 − 1/√2 − 1/√2 − (+1/√2)| = 2√2 ≈ 2.828. (Equivalent to Ekert's S = E(a1,b1) − E(a1,b3) + E(a3,b1) + E(a3,b3) = −2√2.)

* Local realism: S ≤ 2. Tsirelson (quantum) bound: S ≤ 2√2.
* Estimator: E = (N₊₊ + N₋₋ − N₊₋ − N₋₊)/N; standard error σ_E = √((1 − E²)/N); σ_S = √(Σ σ_E²); significance (S − 2)/σ_S.

### 2.5 Noise
Local depolarising channel on each particle during distribution: D_p(ρ) = (1 − p)ρ + p·I/2 (Kraus: √(1−3p/4) I, √(p/4) X, Y, Z). The singlet becomes a Werner state of visibility V = (1 − p)²; S = 2√2·V; QBER = (1 − V)/2.

### 2.6 Eavesdropper (intercept-resend)
Eve sits on Bob's channel. On a fraction q of pairs she measures Bob's particle along a direction θ_E drawn uniformly from a configurable set (default: Bob's three directions — she guesses his setting), records outcome e, and resends the eigenstate |e, θ_E⟩. This is the Lüders instrument ρ → (I⊗P_e)ρ(I⊗P_e)/p_e, so Alice's particle is also collapsed to |−e, θ_E⟩: entanglement is destroyed and the pair becomes a product state.

Prediction: E(a,b) = V·[(1 − q)(−cos(a−b)) + q·⟨−cos(a−θ_E)cos(b−θ_E)⟩_θE]. For separable states CHSH ≤ 2 is guaranteed, so a full attack can never violate the inequality; QBER on key rounds rises (≈ 20.8 % for q = 1 with the default sets).
Eve's knowledge is reported as the agreement between her recorded outcome and Bob's sifted key bit.

Limitation: this is one specific (sub-optimal) individual attack. Optimal collective attacks are not simulated; they are accounted for analytically by the Devetak-Winter/Acín bound below.

---

## 3. Simulation methodology

1. **Exact quantum layer (NumPy linear algebra).** Build ρ_singlet from the circuit, apply Kraus channels, compute Born-rule joint distributions P(x,y | a,b) = Tr[(Π_x^a ⊗ Π_y^b) ρ] and post-measurement states for Eve. No probabilities are typed in by hand; everything comes from the density matrix.
2. **Branch tables.** Because the state of each pair is identical before measurement, the joint distribution for every (branch, setting pair) is computed once (≤ 1 + 2·|Θ_E| branches × 9 settings × 4 outcomes). This is the same thing a shot-based simulator (e.g. Qiskit Aer) does: compute the state once, then sample measurement shots.
3. **Vectorised shot sampling.** Per round: settings ~ Uniform{0,1,2}², attacked ~ Bernoulli(q), θ_E ~ Uniform(Θ_E), e ~ Born, (x,y) ~ Born for the branch. 10⁶ pairs run in well under a second.
4. **Independent RNG streams** (`numpy.random.SeedSequence(seed).spawn`) for settings, Eve, outcomes and post-processing. Toggling Eve therefore keeps the *same* setting choices — a controlled A/B comparison.
5. **Single-pair trace** for the visualisation: amplitudes of |ψ⁻⟩, Alice's measurement probabilities, the collapsed state, Bob's conditional Bloch vector — all computed from the state vector.
6. **Cross-validation.** `tests/test_qiskit_crossval.py` compares the state and probabilities with Qiskit's `Statevector`/`DensityMatrix` when Qiskit is installed (optional dev dependency).

Why not Qiskit as the runtime backend? A two-qubit system is tiny; an exact 4×4 density-matrix engine is mathematically identical, removes a ~100 MB dependency, and lets us vectorise millions of shots. Qiskit is kept as an optional validation oracle.

---

## 4. Classical post-processing

| Stage | Method | Leakage accounted |
|-------|--------|-------------------|
| Sifting | public announcement of settings; keep key-role rounds; Bob flips (anti-correlation) | settings only |
| Parameter estimation | reveal random fraction f (default 20 %) of sifted bits → QBER estimate; discard them | revealed bits removed |
| Bell check | S from CHSH rounds, conservative S_low = S − z·σ_S (default z = 2) | — |
| Error correction | **Cascade** (Brassard–Salvail): pass 1 block k₁ ≈ 0.73/Q, doubled each pass, random permutations, BINARY search, cascading back-correction, 4 passes; then a 64-bit universal-hash verification | every disclosed parity + verification bits |
| Privacy amplification | **Toeplitz-matrix universal hashing** over GF(2) (FFT convolution) | — |

Final length (asymptotic, collective attacks, device-independent bound of Acín et al., PRL 98, 230501 (2007)):

ℓ = ⌊ n_EC · (1 − h((1 + √((S_low/2)² − 1))/2)) − leak_EC − leak_verify ⌋, clipped at 0,

with h the binary entropy. If S_low ≤ 2 the bound gives zero key and the protocol **aborts**. The standard BBM92 rate 1 − 2h(Q) is reported for comparison. Finite-key corrections are not applied (documented).

---

## 5. Architecture

```
EntangleSecure/
├── app.py                         Streamlit entry point, navigation, global CSS
├── .streamlit/config.toml         dark theme base
├── entanglesecure/                ── pure Python, no UI imports ──
│   ├── quantum/   gates.py states.py measurement.py channels.py
│   ├── protocol/  config.py e91.py chsh.py eve.py postprocessing.py theory.py results.py
│   ├── analysis/  experiments.py   (batch trials, convergence, Eve sweeps)
│   └── reporting/ csv_export.py pdf_report.py
├── ui/                            ── presentation layer ──
│   ├── theme.py  components.py  charts.py  state.py  animations.py
│   └── views/ overview.py laboratory.py protocol.py bell.py eavesdropping.py reports.py
├── tests/                         pytest suite
└── docs/  THEORY.md  ARCHITECTURE.md
```

Data flow: `ExperimentConfig` (validated, frozen, JSON-serialisable) → `run_experiment()` → `ExperimentResult` (raw round table + Bell analysis + key pipeline + metrics) → UI pages / reports. The UI never computes physics; it only renders `ExperimentResult`.

Key data structures
* `ExperimentConfig`, `EveConfig` — frozen dataclasses with `validate()`, `to_dict()`, `from_dict()`.
* `RoundData` — NumPy column arrays (settings, outcomes, role, Eve flags) + `to_frame()`.
* `BellAnalysis` — per-correlator counts/E/σ, labelling (a,a′,b,b′), S, σ_S, significance, 3×3 correlation matrix.
* `KeyPipeline` — sifted keys, estimation sample, Cascade report, final keys, rates.
* `ExperimentResult` — all of the above + `metrics()` summary dict.

---

## 6. Application pages

1. **Overview** — hero, live status, KPI tiles (pairs, S, agreement, QBER, security), animated Alice–source–Bob channel driven by the current run, recent activity.
2. **Quantum Laboratory** — controls (pairs, six angles, presets, noise, seed, estimation fraction, Bell confidence), run/reset, measurement-direction diagram, live round tape, outcome histograms, observed vs theoretical correlation heatmaps, single-pair state trace.
3. **E91 Protocol** — eight-step animated walkthrough (generation → distribution → Alice → Bob → public discussion → Bell test → key extraction → verdict) fed by the current run's actual rounds.
4. **Bell Analyzer** — S vs classical/Tsirelson bounds, correlators with error bars on the −cos curve, substituted CHSH formula, significance, Monte-Carlo S distribution, convergence vs N.
5. **Eavesdropping Detection** — Eve ON/OFF, attack parameters, paired comparison (same seed), correlators, S, QBER, agreement, Eve's knowledge, sweep over interception fraction with theory overlay.
6. **Results & Reports** — summary, key funnel, tables, CSV (rounds, metrics), PDF report, JSON config download/upload for exact reproduction, session history.

UI direction: near-black navy surfaces, electric cyan (quantum/Alice), violet (Bob/entanglement), amber/red reserved for Eve and alerts; IBM Plex Sans + Plex Mono; custom CSS replacing Streamlit chrome; custom HTML/SVG components for animations; a shared Plotly template.

---

## 7. Testing strategy

| Area | Tests |
|------|-------|
| Quantum core | singlet amplitudes; ρ Hermitian, trace 1, PSD, pure; concurrence = 1; R_y measurement == projectors; P(x,y) = (1 − xy·cos(a−b))/4; marginals = ½ |
| Channels | depolarising Kraus completeness; visibility (1 − p)² |
| Correlations | sampled E within 5σ of −cos(a−b); 3×3 matrix |
| CHSH | default labelling; S → 2√2 for 2·10⁵ pairs; ideal formula; local-hidden-variable model never exceeds 2; separable states ≤ 2 |
| Key | role classification counts ≈ 2/9, 4/9, 3/9; zero QBER and identical keys ideal; Bob flip logic |
| Eve | QBER ≈ analytic prediction (≈ 20.8 %); S ≤ 2 under full attack; partial attack interpolates; Eve knowledge > 50 % |
| Post-processing | Cascade corrects all errors at 2–10 % QBER; leak accounted; Toeplitz hash linear & identical on equal inputs; abort when S_low ≤ 2 |
| Reproducibility | same seed ⇒ identical rounds/keys; Eve toggle keeps settings |
| Validation | invalid configs raise `ConfigError` with clear messages |
| Reports | CSV columns/rows; PDF bytes start with `%PDF`; JSON round-trip |
| Optional | Qiskit cross-validation (skipped if Qiskit absent) |

---

## 8. Performance

* Branch tables make sampling O(N) vectorised; 10⁶ pairs < 1 s.
* Cascade is the heaviest step: O(n log n) parity work per pass with NumPy prefix sums.
* Toeplitz hashing via FFT convolution: O(n log n).
* Streamlit `st.cache_data` keyed on config dict; heavy sweeps behind explicit buttons.
* UI limits: N ∈ [100, 1 000 000].

---

## 9. Deployment

```bash
cd EntangleSecure
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py          # http://localhost:8501
pytest -q                     # test suite
```

---

## 10. Implementation checklist

- [x] Inspect workspace, environment
- [x] Plan (this document)
- [x] Quantum core (gates, states, measurement, channels)
- [x] Protocol engine (config, E91 sampling, Eve, CHSH, theory)
- [x] Post-processing (estimation, Cascade, Toeplitz PA, key rate)
- [x] Analysis helpers (batches, convergence, sweeps)
- [x] Reporting (CSV, PDF, JSON)
- [x] Test suite green
- [x] UI theme, components, charts
- [x] Six pages
- [x] Run app and verify every page/interaction
- [x] README, THEORY, ARCHITECTURE

### Delivery notes

* All checklist items are complete. 107 automated tests pass, including Qiskit cross-validation and Streamlit AppTest smoke tests of every page.
* Added during implementation:
  * a detection-efficiency (fair-sampling) parameter, so that "successful measurement rounds" is a real quantity;
  * a single-pair collapse trace;
  * a noise-robustness sweep;
  * on-page Monte-Carlo and convergence studies.
* The layout was checked visually with headless Chromium at 1440 px and 390 px widths.
