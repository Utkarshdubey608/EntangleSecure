"""PDF experiment report (fpdf2, core fonts, charts drawn with vector primitives)."""

from __future__ import annotations

import datetime as dt
import json
import math

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from ..protocol.experiment import INSECURE, SECURE, ExperimentResult
from ..protocol.theory import CLASSICAL_BOUND, TSIRELSON_BOUND

# Core PDF fonts are Latin-1 only: transliterate the physics notation.
_ASCII = {
    "ψ": "psi", "⁻": "-", "√": "sqrt", "σ": "sigma", "′": "'", "≤": "<=", "≥": ">=", "−": "-",
    "→": "->", "⊗": "x", "χ": "chi", "θ": "theta", "…": "...", "—": "-", "–": "-", "⟩": ">", "⟨": "<",
    "·": "*", "°": " deg", "≈": "~", "×": "x", "±": "+/-",
}

INK = (20, 27, 45)
MUTED = (100, 110, 130)
CYAN = (8, 145, 178)
VIOLET = (124, 58, 237)
GREEN = (5, 150, 105)
RED = (220, 38, 38)
AMBER = (217, 119, 6)
RULE = (220, 225, 235)


def _t(text: str) -> str:
    for k, v in _ASCII.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def _fmt(v, digits: int = 4) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return "-" if math.isnan(v) else f"{v:.{digits}f}"
    return str(v)


class _Report(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*CYAN)
        self.cell(0, 6, "ENTANGLESECURE", new_x=XPos.RIGHT)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, "E91 Quantum Key Distribution - Experiment Report", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*RULE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"Page {self.page_no()}", align="C")

    # ---- helpers ------------------------------------------------------
    def h1(self, text: str) -> None:
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*INK)
        self.multi_cell(0, 9, _t(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def h2(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*INK)
        self.cell(0, 8, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*CYAN)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.l_margin + 18, self.get_y())
        self.set_line_width(0.2)
        self.ln(2)

    def para(self, text: str, size: float = 9.5) -> None:
        self.set_font("Helvetica", "", size)
        self.set_text_color(*INK)
        self.multi_cell(0, 5, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def table(self, header: list[str], rows: list[list[str]], widths: list[float]) -> None:
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(238, 242, 248)
        self.set_text_color(*INK)
        for h, w in zip(header, widths):
            self.cell(w, 6.5, _t(h), border=0, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8.5)
        for r_i, row in enumerate(rows):
            if self.get_y() > self.h - 22:
                self.add_page()
            fill = r_i % 2 == 1
            self.set_fill_color(248, 250, 252)
            for v, w in zip(row, widths):
                self.cell(w, 6, _t(str(v)), border=0, fill=fill)
            self.ln()

    def kv(self, pairs: list[tuple[str, str]], col_w: float = 60) -> None:
        for k, v in pairs:
            self.set_font("Helvetica", "", 9)
            self.set_text_color(*MUTED)
            self.cell(col_w, 5.6, _t(k))
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*INK)
            self.cell(0, 5.6, _t(v), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _chsh_chart(pdf: _Report, s: float, s_err: float, s_theory: float) -> None:
    """Horizontal scale 0 … 3 with classical and Tsirelson markers and the measured S ± σ."""
    x0, y0 = pdf.l_margin, pdf.get_y() + 4
    w, h = pdf.w - pdf.l_margin - pdf.r_margin, 12
    scale = w / 3.0
    pdf.set_fill_color(240, 244, 250)
    pdf.rect(x0, y0, w, h, style="F")
    pdf.set_fill_color(254, 226, 226)
    pdf.rect(x0, y0, CLASSICAL_BOUND * scale, h, style="F")
    pdf.set_fill_color(224, 242, 254)
    pdf.rect(x0 + CLASSICAL_BOUND * scale, y0, (TSIRELSON_BOUND - CLASSICAL_BOUND) * scale, h, style="F")
    for val, col, label in ((CLASSICAL_BOUND, RED, "classical 2"), (TSIRELSON_BOUND, VIOLET, "Tsirelson 2sqrt2")):
        pdf.set_draw_color(*col)
        pdf.set_line_width(0.5)
        pdf.line(x0 + val * scale, y0 - 1, x0 + val * scale, y0 + h + 1)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*col)
        pdf.text(x0 + val * scale - 8, y0 + h + 5, label)
    if math.isfinite(s):
        xs = x0 + min(s, 3.0) * scale
        pdf.set_draw_color(*INK)
        pdf.set_line_width(0.4)
        pdf.line(x0 + max(s - s_err, 0) * scale, y0 + h / 2, x0 + min(s + s_err, 3) * scale, y0 + h / 2)
        pdf.set_fill_color(*CYAN)
        pdf.ellipse(xs - 1.8, y0 + h / 2 - 1.8, 3.6, 3.6, style="F")
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*INK)
        pdf.text(xs - 10, y0 - 2, f"S = {s:.3f} +/- {s_err:.3f}")
    pdf.set_line_width(0.2)
    for tick in range(4):
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*MUTED)
        pdf.text(x0 + tick * scale - 1, y0 + h + 9, str(tick))
    pdf.set_y(y0 + h + 12)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, _t(f"Theoretical prediction for this configuration: S = {s_theory:.4f}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _correlation_bars(pdf: _Report, result: ExperimentResult) -> None:
    """Measured vs theoretical E for all nine setting pairs (bars from a zero line)."""
    x0, y0 = pdf.l_margin + 8, pdf.get_y() + 4
    w, h = pdf.w - pdf.l_margin - pdf.r_margin - 8, 46
    mid = y0 + h / 2
    pdf.set_draw_color(*RULE)
    pdf.line(x0, mid, x0 + w, mid)
    for v in (-1, 1):
        y = mid - v * h / 2
        pdf.line(x0, y, x0 + w, y)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*MUTED)
        pdf.text(x0 - 7, y + 1, f"{v:+d}")
    slot = w / 9
    for k, ((i, j), c) in enumerate(sorted(result.bell.correlators.items())):
        cx = x0 + k * slot + slot * 0.2
        bw = slot * 0.28
        for off, val, col in ((0, c.expectation, CYAN), (bw + 1, c.theory, VIOLET)):
            if not math.isfinite(val):
                continue
            top = mid - max(val, 0) * h / 2
            pdf.set_fill_color(*col)
            pdf.rect(cx + off, top, bw, abs(val) * h / 2, style="F")
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*INK)
        pdf.text(cx, y0 + h + 5, f"A{i}B{j}")
    pdf.set_y(y0 + h + 8)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*CYAN)
    pdf.cell(28, 5, "measured E", new_x=XPos.RIGHT)
    pdf.set_text_color(*VIOLET)
    pdf.cell(0, 5, "theory E", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_pdf_report(result: ExperimentResult, comparison: ExperimentResult | None = None) -> bytes:
    cfg = result.config
    m = result.metrics()
    pdf = _Report(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 14, 16)
    pdf.add_page()

    pdf.h1("EntangleSecure: E91 Entanglement-Based QKD Experiment")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    stamp = dt.datetime.fromtimestamp(result.timestamp).strftime("%Y-%m-%d %H:%M:%S")
    pdf.cell(0, 6, f"Generated {stamp}  |  seed {cfg.seed}  |  runtime {result.runtime_s:.3f} s", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    status = result.security_status
    color = {SECURE: GREEN, INSECURE: RED}.get(status, AMBER)
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 10, _t(f"  Security status: {status}"), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if result.keys.abort_reason:
        pdf.ln(1)
        pdf.para(result.keys.abort_reason, 8.5)

    pdf.h2("1. Configuration")
    pdf.kv(
        [
            ("Entangled pairs (singlet |psi->)", f"{cfg.n_pairs:,}"),
            ("Alice directions A0, A1, A2", ", ".join(f"{a:g}°" for a in cfg.alice_angles_deg)),
            ("Bob directions B0, B1, B2", ", ".join(f"{b:g}°" for b in cfg.bob_angles_deg)),
            ("Depolarizing noise p (per particle)", f"{cfg.depolarizing_noise:.3f}"),
            ("Detection efficiency", f"{cfg.detection_efficiency:.3f}"),
            ("QBER estimation fraction", f"{cfg.estimation_fraction:.2f}"),
            ("Bell confidence margin", f"{cfg.bell_confidence_sigma:g} sigma"),
            ("Cascade passes", str(cfg.cascade_passes)),
            (
                "Eavesdropper",
                f"intercept-resend, q = {cfg.eve.intercept_fraction:.2f}, directions {', '.join(f'{a:g}°' for a in cfg.eve.basis_angles_deg)}"
                if cfg.eve.enabled
                else "disabled",
            ),
        ]
    )

    pdf.h2("2. Measurement statistics")
    pdf.kv(
        [
            ("Total entangled pairs", f"{m['total_pairs']:,}"),
            ("Detected (successful) rounds", f"{m['detected_rounds']:,}"),
            ("Lost rounds (no detection)", f"{m['lost_rounds']:,}"),
            ("Key-generation rounds", f"{m['key_rounds']:,}"),
            ("CHSH test rounds", f"{m['chsh_rounds']:,}"),
            ("Discarded rounds", f"{m['discarded_rounds']:,}"),
            ("Entanglement (concurrence) after channel", f"{m['entanglement_concurrence']:.4f}"),
        ]
    )

    pdf.h2("3. CHSH Bell inequality analysis")
    lab = result.bell.labelling
    pdf.para(
        f"S = |E(a,b) + E(a,b') + E(a',b) - E(a',b')| with a = A{lab.a}, a' = A{lab.a_prime}, "
        f"b = B{lab.b}, b' = B{lab.b_prime}. Local realism requires S <= 2; quantum mechanics allows S <= 2sqrt2 = 2.8284."
    )
    _chsh_chart(pdf, result.bell.s_value, result.bell.s_stderr, result.bell.s_theory)
    rows = []
    for sym, c, sign in result.bell.chsh_terms():
        rows.append(
            [sym, f"A{c.alice_idx}B{c.bob_idx}", f"{cfg.alice_angles_deg[c.alice_idx]:g}°, {cfg.bob_angles_deg[c.bob_idx]:g}°", f"{c.n:,}",
             _fmt(c.expectation), _fmt(c.stderr), _fmt(c.theory), "+" if sign > 0 else "-"]
        )
    pdf.table(["Term", "Settings", "Angles", "N", "E measured", "std. err.", "E theory", "sign"], rows, [22, 20, 30, 18, 24, 22, 22, 12])
    pdf.ln(2)
    sig = result.bell.significance
    pdf.kv(
        [
            ("CHSH value S", f"{_fmt(result.bell.s_value)} +/- {_fmt(result.bell.s_stderr)}"),
            ("Conservative S - z*sigma", _fmt(result.bell.s_lower)),
            ("Distance from classical bound", f"{_fmt(sig, 1)} sigma"),
            ("Classical inequality violated", _fmt(result.bell.violates_classical)),
            ("Violation statistically confirmed", _fmt(result.bell.violation_confirmed)),
        ]
    )
    for note in result.bell.notes:
        pdf.para("Note: " + note, 8.5)

    pdf.h2("4. Correlations for all setting pairs")
    _correlation_bars(pdf, result)

    pdf.h2("5. Key generation")
    k = result.keys
    pdf.table(["Stage", "Bits / pairs"], [[s, f"{v:,}"] for s, v in k.stages], [90, 40])
    pdf.ln(2)
    pdf.kv(
        [
            ("Sifted key length (Alice = Bob)", f"{len(k.sifted):,}"),
            ("Sifted key agreement", f"{_fmt(k.agreement * 100 if math.isfinite(k.agreement) else float('nan'), 2)} %"),
            ("QBER (whole sifted key, simulation)", f"{_fmt(k.sifted_qber * 100, 2)} %"),
            ("QBER estimate (revealed sample)", f"{_fmt(k.qber_estimate * 100, 2)} % on {k.estimation_size:,} bits"),
            ("QBER theory", f"{_fmt(result.theory_qber * 100, 2)} %"),
            ("Eve information bound chi(S)", _fmt(k.eve_info_bound)),
            ("Cascade leaked bits", _fmt(k.cascade.leaked_bits if k.cascade else None)),
            ("Residual errors after Cascade", _fmt(k.cascade.residual_errors if k.cascade else None)),
            ("Final secret key length", f"{k.final_length:,} bits"),
            ("Final keys identical", _fmt(k.keys_match)),
            ("Secure yield", f"{m['secure_yield_per_pair']:.4f} bits / pair"),
        ]
    )
    if k.final_length:
        pdf.ln(1)
        pdf.set_font("Courier", "", 7.5)
        pdf.set_text_color(*INK)
        hexkey = m["final_key_hex"]
        shown = hexkey if len(hexkey) <= 512 else hexkey[:512] + "..."
        pdf.multi_cell(0, 4, "Final key (hex):\n" + shown, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.h2("6. Eavesdropping assessment")
    if cfg.eve.enabled:
        pdf.para(
            f"Eve intercepted {m['eve_intercepted_pairs']:,} of {m['total_pairs']:,} pairs on Bob's channel "
            f"(intercept-resend). Her guesses agree with Bob's sifted key on {_fmt(k.eve_agreement * 100, 1)} % of bits."
        )
    else:
        pdf.para("Eve disabled for this run.")
    if comparison is not None:
        c = comparison.metrics()
        pdf.ln(1)
        pdf.table(
            ["Metric", "This run", "Comparison run"],
            [
                ["Eve enabled", _fmt(m["eve_enabled"]), _fmt(c["eve_enabled"])],
                ["CHSH S", _fmt(m["chsh_s"]), _fmt(c["chsh_s"])],
                ["QBER", _fmt(m["qber"]), _fmt(c["qber"])],
                ["Key agreement", _fmt(m["key_agreement"]), _fmt(c["key_agreement"])],
                ["Final key bits", str(m["final_key_length"]), str(c["final_key_length"])],
                ["Status", m["security_status"], c["security_status"]],
            ],
            [60, 50, 50],
        )

    pdf.h2("7. Method and limitations")
    pdf.para(
        "States are simulated exactly as 4x4 density matrices: |psi-> = (|01> - |10>)/sqrt2 prepared by the circuit "
        "X(x)X -> H(x)I -> CNOT, local depolarizing channels in Kraus form, and Eve's intercept-resend as a projective "
        "(Luders) measurement on Bob's particle. Outcomes are sampled shot-by-shot from Born-rule probabilities. "
        "Measurement directions are Bloch-sphere angles in the x-z plane; E(a,b) = -cos(a-b) for the ideal singlet. "
        "Error correction uses Cascade; privacy amplification uses Toeplitz hashing. The secret-key length uses the "
        "asymptotic device-independent bound chi(S) = h((1 + sqrt((S/2)^2 - 1))/2) (Acin et al. 2007) with S - z*sigma; "
        "finite-key effects, photon loss beyond a fair-sampling detection efficiency, and classical-channel "
        "authentication are not modelled. The eavesdropper uses one individual attack strategy only."
    )
    pdf.h2("8. Reproducibility")
    pdf.set_font("Courier", "", 7.5)
    pdf.set_text_color(*INK)
    pdf.para("Re-running with this configuration (e.g. by uploading the JSON on the Results page) reproduces every number in this report.", 8.5)
    pdf.set_font("Courier", "", 7.5)
    pdf.multi_cell(0, 3.8, _t(json.dumps(cfg.to_dict())), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())
