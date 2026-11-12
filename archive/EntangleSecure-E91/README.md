# EntangleSecure

**Design and Simulation of Entanglement-Based Quantum Key Distribution Using the E91 Protocol with Bell Inequality Analysis**

EntangleSecure simulates the Ekert-1991 (E91) protocol end to end. It covers singlet-pair generation, distribution through a noisy channel, an optional intercept-resend eavesdropper, randomly chosen measurements, a CHSH Bell test with error bars, and classical key distillation (sifting, QBER estimation, Cascade, Toeplitz privacy amplification). An interactive six-page dashboard presents the results.

Every number in the interface comes from simulated measurement data. No Bell violation, QBER or key length is hard-coded.

---

## Quick start

Requires Python 3.11 or newer.

```bash
cd EntangleSecure
source .venv/bin/activate            # if .venv already exists
streamlit run app.py                 # opens http://localhost:8501
pytest                               # 107 tests
```

To create the environment from scratch, [uv](https://docs.astral.sh/uv/) is the most reliable route:

```bash
uv venv --python 3.12 --python-preference only-managed --seed .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt   # or requirements.txt without tests/Qiskit
```

Plain `venv` works too, if `python3` is a healthy 3.11+ interpreter:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Troubleshooting

* **`ensurepip ... died with SIGSEGV`.** The interpreter crashes whenever it starts a subprocess. This was observed with a locally compiled pyenv CPython 3.12.14 on macOS 26. Use the uv command above: `only-managed` makes uv use its prebuilt CPython, which is not affected. To check an interpreter, run `python -c "import subprocess; subprocess.run(['true']); print('ok')"`.
* **`pip: command not found` / `streamlit: command not found`.** The venv was not activated, usually because an earlier step in an `&&` chain failed. Run `source .venv/bin/activate`, or call the tools directly as `.venv/bin/streamlit run app.py`.
* **`python3 --version` prints 3.9.** That is the macOS/Xcode system Python, which is too old for NumPy 2 and Streamlit. Use the uv command above, or point `python3` at a 3.11+ install.

Use the engine without the UI:

```python
from entanglesecure.protocol import ExperimentConfig, run_experiment

res = run_experiment(ExperimentConfig(n_pairs=100_000, seed=7))
print(res.bell.s_value, res.bell.s_stderr)        # ≈ 2.83 ± 0.013
print(res.keys.sifted_qber, res.keys.final_length)

attacked = run_experiment(ExperimentConfig(n_pairs=100_000, seed=7).with_eve(True))
print(attacked.bell.s_value, attacked.security_status)   # ≈ 1.41, COMPROMISED
```

---

## The application

| Page | What it shows |
|------|---------------|
| **Overview** | A live Alice ← source → Bob channel replaying the current run's pairs (settings, outcomes, roles, Eve's interceptions). Also headline metrics, the S value against the classical and quantum bounds, the security verdict, and recent activity. |
| **Quantum laboratory** | Controls for pair count, six measurement directions (with presets), depolarizing noise, detection efficiency, seed, Eve, and post-processing. Results include measurement-direction geometry, E versus Δ, measured and theoretical correlation matrices, outcome statistics, the raw measurement record, and a single-pair trace with Born probabilities and collapse. |
| **E91 protocol** | An eight-step animated walkthrough: generation (real state-vector amplitudes after each gate), distribution, Alice's measurement, Bob's measurement, public discussion, Bell test, key extraction, and verdict. All of it is driven by the current run. |
| **Bell inequality analyzer** | S with σ, significance and S − zσ. Also the term-by-term CHSH sum with the measured numbers substituted, correlators against theory, E(Δ) against Bell's local model, a Monte-Carlo distribution of S, convergence with N, and a noise-robustness sweep. |
| **Eavesdropping detection** | An Eve on/off control and attack strategy, with a paired comparison under the same seed (identical setting choices). Shows verdicts, S, all four correlators, QBER, Eve's knowledge, the attacked sifted keys with errors highlighted, and a sweep over the interception fraction with theory overlays. |
| **Results and reports** | The key-distillation funnel and Cascade report, sifted and final keys, and the Bell table. Downloads include a PDF report, summary CSV, the full measurement-record CSV, and the configuration JSON. Upload a JSON file, or pick from session history, to reproduce a run exactly. |

---

## Physics in one page

Full derivations are in [docs/THEORY.md](docs/THEORY.md).

* **State.** The source produces |ψ⁻⟩ = (|01⟩ − |10⟩)/√2, using the circuit X⊗X → H⊗I → CNOT on |00⟩.
* **Measurements.** A direction θ is a spin axis in the x–z plane of the Bloch sphere, with observable σ(θ) = cos θ Z + sin θ X and outcomes ±1. The measurement is implemented as R_y(−θ) followed by a Z measurement. For photons, the polariser angle is θ/2.
* **Correlation.** E(a,b) = ⟨σ(a)⊗σ(b)⟩ = −cos(a − b), and P(x,y|a,b) = (1 − xy cos(a − b))/4.
* **Settings (Ekert 1991).** Alice uses A = (0°, 45°, 90°) and Bob uses B = (45°, 90°, 135°), each chosen uniformly.
  * Key rounds: (A1,B0) and (A2,B1), with identical directions, are perfectly anti-correlated. Bob flips his bit. These are 2/9 of pairs.
  * CHSH rounds: {A0,A2} × {B0,B2}, 4/9 of pairs.
  * Discarded: the remaining 3/9.
* **CHSH.** S = |E(a,b) + E(a,b′) + E(a′,b) − E(a′,b′)|, with a = A2, a′ = A0, b = B0, b′ = B2. The ideal value is |−4/√2| = 2√2.
  * The term that carries the minus sign is chosen from the configured angles, never from the data.
  * Error bars: σ_E = √((1 − E²)/N) and σ_S = √Σσ_E².
* **Noise.** A local depolarizing channel p on each particle gives a Werner state with visibility V = (1 − p)². Then S = 2√2·V and QBER = (1 − V)/2.
* **Eve (intercept-resend on Bob's arm).** She measures along θ_E and resends |e, θ_E⟩, which leaves a product state with E = −cos(a − θ_E)cos(b − θ_E).
  * Product states can never violate CHSH.
  * Guessing among Bob's directions with q = 1 gives S = √2 and QBER = 20.8 %.
* **Key length.** ℓ = ⌊n·(1 − χ(S − zσ)) − leak_EC⌋, using the device-independent bound χ(S) = h((1 + √((S/2)² − 1))/2) (Acín et al., PRL 98, 230501, 2007). If S − zσ ≤ 2, the protocol aborts.

### What is exact, what is a model

| Exact / genuine | Simplified / idealised |
|-----------------|------------------------|
| 4×4 density-matrix simulation, Kraus channels, Lüders measurement | Source emits exactly one pair per round (no multi-pair emission) |
| Born-rule shot sampling from the computed state | Detector loss is fair sampling (detection loophole not modelled) |
| CHSH estimation with propagated standard errors | One individual attack strategy (intercept-resend) |
| Real Cascade (parity exchange, BINARY, back-tracking) with leakage counted | Authenticated classical channel assumed, not implemented |
| Real Toeplitz universal hashing | Asymptotic key rate, no finite-key corrections |

---

## Architecture

```
EntangleSecure/
├── app.py                    Streamlit entry point (navigation, theme, sidebar)
├── screens/                  thin page scripts → ui.views.*
├── ui/                       presentation only: theme, components, charts, animations, state
│   └── views/                overview, laboratory, protocol, bell, eavesdropping, reports
├── entanglesecure/           simulation library (no UI imports)
│   ├── quantum/              gates, states, measurement, channels: exact 2-qubit simulator
│   ├── protocol/             config, roles, e91 (sampling), eve, chsh, postprocessing, theory, experiment, trace
│   ├── analysis/             Monte-Carlo, convergence, Eve and noise sweeps
│   └── reporting/            CSV and PDF reports
├── tests/                    107 tests (physics, protocol, post-processing, reports, UI smoke tests, Qiskit)
└── docs/                     THEORY.md, ARCHITECTURE.md
```

Details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The plan and design decisions are in [PROJECT_PLAN.md](PROJECT_PLAN.md).

**Why a NumPy simulator rather than Qiskit at runtime?** The system has two qubits. An exact 4×4 density-matrix engine is mathematically identical, adds no ~100 MB dependency, and lets 10⁶ shots be sampled in well under a second. Qiskit is kept as an independent oracle: `tests/test_qiskit_crossval.py` checks the singlet state and every measurement distribution against `qiskit.quantum_info`.

**Why Streamlit?** It suits a Python-native scientific engine. Its default look is replaced by a custom theme, custom HTML components, and canvas animations in sandboxed iframes, each fed with the current run's data.

---

## Testing

```
107 passed in ~3 s
```

| File | Tests | Covers |
|------|------:|--------|
| `test_quantum.py` | 20 | singlet amplitudes and density matrix, purity, concurrence, rotational invariance, eigenstates, circuit-style measurement against projectors, Born probabilities (1 − xy cos Δ)/4, E = −cos Δ, collapse, Kraus completeness, Werner visibility and concurrence |
| `test_chsh.py` | 12 | Ekert labelling; ideal S = 2√2; estimator and σ; S → 2√2 at 4·10⁵ pairs within 5σ; all nine correlators within 5σ; exhaustive local-deterministic bound \|S\| ≤ 2; 200 random product states ≤ 2; labelling independent of data; σ ∝ 1/√N; S under noise |
| `test_protocol.py` | 11 | role table and 2/9, 4/9, 3/9 frequencies; key rounds have equal directions; raw anti-correlation; identical ideal keys; not every round contributes; unbiased marginals (no-signalling); seed reproducibility; Eve toggle keeps settings; misaligned-key QBER = ½·sin²(7.5°); detection loss |
| `test_eve.py` | 7 | Eve branches are physical and disentangled; QBER ≈ 20.83 % analytic; full attack gives S < 2 and abort; separable bound for many Eve strategies; linear interpolation in q; Eve's information gain |
| `test_postprocessing.py` | 13 | Cascade corrects 1–10 % QBER with leakage above the Shannon limit; Toeplitz against the explicit matrix, FFT path, linearity; key-rate bounds; hex encoding; noisy-channel final-key formula; abort paths |
| `test_config_reporting.py` | 31 | 21 invalid configurations rejected with readable messages; JSON round trip; malformed JSON; rounds CSV; summary CSV sections; PDF generation |
| `test_app_pages.py` | 11 | every page renders; overview, laboratory, eavesdropping, Bell and reports actions run without exceptions |
| `test_qiskit_crossval.py` | 2 | singlet state and 25 measurement distributions match Qiskit (skipped if Qiskit is absent) |

Typical numbers (seeded, reproducible):

| Scenario | Pairs | S (theory) | QBER (theory) | Final key |
|----------|------:|-----------|---------------|-----------|
| Ideal channel | 200 000 | 2.826 ± 0.010 (2.828) | 0 % (0 %) | 32 614 bits, identical |
| Eve, q = 1 | 200 000 | 1.421 ± 0.012 (1.414) | 20.85 % (20.83 %) | 0, aborted |
| Noise p = 0.10 | 20 000 | 2.255 ± 0.035 (2.291) | 9.1 % (9.5 %) | 0, DI bound exhausted |

---

## Key formulas

| Quantity | Formula |
|----------|---------|
| Singlet correlation | E(a,b) = −V·cos(a − b), V = (1 − p)² |
| Joint probability | P(x,y\|a,b) = (1 − xy·V·cos(a − b))/4 |
| Correlator estimate | E = (N₊₊ + N₋₋ − N₊₋ − N₋₊)/N, σ_E = √((1 − E²)/N) |
| CHSH | S = \|E(a,b) + E(a,b′) + E(a′,b) − E(a′,b′)\| ≤ 2 (local), ≤ 2√2 (quantum) |
| Intercept-resend correlation | E = −V·[(1 − q)cos(a − b) + q·⟨cos(a − θ)cos(b − θ)⟩_θ] |
| QBER (aligned key setting) | Q = (1 + E)/2 |
| Eve's information bound (DI, collective) | χ(S) = h((1 + √((S/2)² − 1))/2) |
| Final key length | ℓ = ⌊n_EC·(1 − χ(S − zσ)) − leak_EC⌋ |
| BBM92 rate (for comparison) | r = 1 − 2h(Q) |

---

## Known limitations and assumptions

1. **Asymptotic security.** χ(S) is the collective-attack, asymptotic bound. Finite-key terms (smoothing, sampling deviations) are approximated only by the S − zσ margin, which defaults to z = 2.
2. **Attack model.** Only intercept-resend is simulated. Entangling-probe, collective and coherent attacks are covered analytically by χ(S), not simulated.
3. **Fair sampling.** Lost rounds are discarded, which assumes fair sampling. A real device-independent test would need to close the detection loophole.
4. **Ideal source and detectors.** The model has no multi-pair emission, dark counts or detector-efficiency mismatch.
5. **Classical channel.** It is assumed authenticated. Authentication itself is not implemented.
6. **Cascade parameters** follow the textbook schedule (k₁ ≈ 0.73/Q, doubling, 4 passes). Real implementations tune them further.
7. **Absolute value in S.** |S| is used, as in the CHSH definition. A finite-sample estimate can exceed 2√2, and the UI flags this as a fluctuation.

---

## Possible extensions

* Finite-key composable security analysis (e.g. entropy accumulation for DI-QKD).
* Entangling-probe (Fuchs–Peres–Brandt style) and collective attacks, simulated with an ancilla qubit.
* Photon-pair source models: SPDC statistics, multi-pair noise, distance-dependent loss, and key rate against fibre length.
* Closing the detection loophole: no-click outcomes assigned as ±1, and the efficiency threshold.
* Hardware runs: executing the CHSH circuits on IBM Quantum backends through Qiskit Runtime and comparing with simulation.
* LDPC or polar-code error correction, and comparison of their leakage with Cascade.
* BBM92 and BB84 side-by-side mode.
