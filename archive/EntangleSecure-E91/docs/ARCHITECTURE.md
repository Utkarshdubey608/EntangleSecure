# Architecture

## Layers

```
┌────────────────────────────── presentation (ui/, screens/, app.py) ──────────────────────────────┐
│ app.py: page config, CSS, st.navigation, sidebar summary                                         │
│ ui/views/*: one module per page, renders ExperimentResult and calls ui.state                     │
│ ui/charts.py (Plotly)   ui/animations.py (canvas iframes)   ui/components.py (HTML blocks)       │
│ ui/state.py: session state, cached runs, history, user-facing error handling                     │
└───────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                │ ExperimentConfig → ExperimentResult
┌───────────────────────────────────── entanglesecure/ (no Streamlit) ─────────────────────────────┐
│ protocol/experiment.py  run_experiment(): validate → model → sample → Bell → keys → metrics      │
│ protocol/config.py      ExperimentConfig, EveConfig (frozen, validated, JSON)                    │
│ protocol/e91.py         QuantumModel (exact states, Born tables), RoundData, sample_rounds()     │
│ protocol/eve.py         intercept-resend branches (Lüders), Eve's guesses                        │
│ protocol/chsh.py        labelling, correlators, S, σ, significance                               │
│ protocol/postprocessing.py  sifting, estimation, Cascade, verification, Toeplitz, key length     │
│ protocol/theory.py      closed-form predictions (independent oracle), key-rate bounds            │
│ protocol/trace.py       per-pair sequential collapse for visualisation                           │
│ protocol/roles.py       key / CHSH / discard / lost role table                                   │
│ quantum/*               gates, states (singlet circuit, concurrence…), measurement, channels     │
│ analysis/experiments.py repeated trials, convergence, Eve and noise sweeps                       │
│ reporting/*             CSV (rounds, summary), PDF (fpdf2, vector charts)                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

The UI never computes physics. Everything it shows is an attribute of `ExperimentResult`, or comes from the `analysis` and `theory` modules.

## Data flow of one run

1. `ExperimentConfig.validate()` normalises the inputs or raises `ConfigError` with a readable message.
2. `build_quantum_model()` computes:
   * the statevector from the circuit, then ρ_source;
   * the depolarizing Kraus channel, giving ρ_channel;
   * the Eve branches from Lüders projections on Bob's qubit;
   * the Born table `joint[branch, i, j, 4]`.
3. `sample_rounds()` uses separate RNG streams for settings, Eve, outcomes and loss, plus vectorised inverse-CDF sampling. It returns `RoundData` (column arrays).
4. `analyze_bell()` counts outcomes, then computes the correlators and S ± σ using the a-priori labelling.
5. `run_key_pipeline()` runs sifting, then estimation, then the Bell gate. If the gate passes, it continues with Cascade, the hash check, the χ(S_low) key length, and Toeplitz hashing. The result is `KeyPipeline`.
6. `ExperimentResult.metrics()` produces a flat dictionary, which feeds the UI, the CSV and the PDF.

## Performance

| Step | Complexity | Measured, 10⁶ pairs (Apple silicon) |
|------|-----------|-----------|
| Model (≤ 17 branches × 9 settings, 4×4 algebra) | O(1) | ≈ 1 ms |
| Sampling | O(N) vectorised | ≈ 0.06 s |
| Full run, ideal channel (Bell + Cascade + Toeplitz on 2·10⁵ bits) | O(N + n log n) | ≈ 0.13 s |
| Full run, p = 0.02 noise (≈ 2 300 corrections in Cascade) | O(N + n log n) | ≈ 0.42 s |

Streamlit caches runs by configuration JSON (`st.cache_data`), so identical configurations, such as re-runs from history or report generation, are free.

## UI design system

* **Surfaces.** Background `#070B16`, surface `#0B1220`, raised `#101A2D`, hairlines `#1C2740`.
* **Accents.** Cyan `#22D3EE` stands for Alice and quantum, violet `#A78BFA` for Bob and entanglement, blue `#4C8DFF` for the channel, and amber for Eve.
* **Chart marks.** The colours `#0EA5C6`, `#8B6CF0` and `#C98410` pass a dark-mode categorical palette validator (lightness band, chroma, CVD separation, contrast).
* **Status colours.** Green, amber and red are reserved for security states and always appear with a text label.
* **Typography.** IBM Plex Sans is used for the interface. IBM Plex Mono is used only for formulas, bit strings and keys.
* **Animations.** These are `<canvas>` scenes in sandboxed iframes (`st.iframe`), with data injected as JSON from the current result. They respect `prefers-reduced-motion`.

## Testing layers

1. **Exact physics** (`test_quantum.py`): algebraic identities, checked to 1e-12.
2. **Statistical physics** (`test_chsh.py`, `test_eve.py`, `test_protocol.py`): sampled estimates checked to within 5σ of the closed-form theory.
3. **Algorithms** (`test_postprocessing.py`): Cascade correctness and leakage, Toeplitz against the explicit matrix.
4. **Interfaces** (`test_config_reporting.py`, `test_app_pages.py`): validation, serialisation, reports, and every page and main action.
5. **External oracle** (`test_qiskit_crossval.py`): Qiskit `Statevector` and `DensityMatrix`.
