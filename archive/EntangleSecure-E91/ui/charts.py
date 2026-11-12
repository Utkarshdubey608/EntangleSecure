"""Plotly figure builders. Every figure is drawn from simulation output; theory is overlay only."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from entanglesecure.protocol import ExperimentConfig, ExperimentResult
from entanglesecure.protocol.roles import ROLE_CHSH, ROLE_KEY, ROLE_MATRIX
from entanglesecure.protocol.theory import CLASSICAL_BOUND, TSIRELSON_BOUND, visibility

from .theme import CRITICAL, INK, INK_2, LINE_STRONG, MUTED, S_ALICE, S_BOB, S_EVE, THEORY, VIOLET

PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"], "toImageButtonOptions": {"scale": 2}}
ROLE_LABEL = {ROLE_KEY: "key", ROLE_CHSH: "CHSH"}


def _bounds(fig: go.Figure, axis: str = "x", show_labels: bool = True) -> None:
    """Reference lines for the classical (2) and Tsirelson (2√2) bounds."""
    for val, color, text in ((CLASSICAL_BOUND, CRITICAL, "classical bound 2"), (TSIRELSON_BOUND, VIOLET, "Tsirelson bound 2√2")):
        kw = dict(line=dict(color=color, width=1.5, dash="dot"))
        if show_labels:
            kw.update(annotation_text=text, annotation_font=dict(color=color, size=11))
        if axis == "x":
            fig.add_vline(x=val, annotation_position="top", **kw)
        else:
            fig.add_hline(y=val, annotation_position="top left", **kw)


# ---------------------------------------------------------------------------
# Measurement geometry
# ---------------------------------------------------------------------------


def measurement_directions(cfg: ExperimentConfig, height: int = 330) -> go.Figure:
    """Directions in the x–z plane of the Bloch sphere (θ measured from +z towards +x)."""
    fig = go.Figure()
    sets = [("Alice", cfg.alice_angles_deg, S_ALICE, "A", "solid"), ("Bob", cfg.bob_angles_deg, S_BOB, "B", "solid")]
    if cfg.eve.enabled:
        sets.append(("Eve", cfg.eve.basis_angles_deg, S_EVE, "E", "dot"))
    for name, angles, color, prefix, dash in sets:
        for k, a in enumerate(angles):
            r_tip = 1.0 if name != "Bob" else 0.86
            fig.add_trace(
                go.Scatterpolar(
                    r=[0, r_tip], theta=[a, a], mode="lines+markers+text",
                    line=dict(color=color, width=2.5, dash=dash), marker=dict(size=[0, 9], color=color),
                    text=["", f"{prefix}{k}"], textposition="top center", textfont=dict(color=INK, size=11),
                    name=name, legendgroup=name, showlegend=k == 0,
                    hovertemplate=f"{name} {prefix}{k}: {a:g}°<extra></extra>",
                )
            )
    fig.update_layout(
        height=height,
        margin=dict(l=30, r=30, t=40, b=20),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            angularaxis=dict(rotation=90, direction="clockwise", gridcolor="rgba(163,176,199,0.10)", linecolor=LINE_STRONG,
                             tickfont=dict(color=MUTED, size=10), dtick=45),
            radialaxis=dict(visible=False, range=[0, 1.1]),
        ),
        legend=dict(y=-0.02, yanchor="top", x=0.5, xanchor="center"),
    )
    return fig


# ---------------------------------------------------------------------------
# Correlations
# ---------------------------------------------------------------------------


def correlation_curve(res: ExperimentResult, height: int = 380) -> go.Figure:
    """Measured E for all nine setting pairs against Δ = a − b, over the singlet law −V·cos Δ."""
    cfg = res.config
    v = visibility(cfg.depolarizing_noise)
    d = np.linspace(-180, 180, 361)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d, y=-v * np.cos(np.radians(d)), mode="lines", name=f"singlet law −V·cos Δ (V = {v:.3f})",
                             line=dict(color=THEORY, width=2, dash="dash"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d, y=-1 + 2 * np.abs(d) / 180, mode="lines", name="Bell's local hidden-variable model −1 + 2|Δ|/180°",
                             line=dict(color=MUTED, width=1.5, dash="dot"), hoverinfo="skip", visible="legendonly"))
    rows = []
    for (i, j), c in res.bell.correlators.items():
        delta = ((cfg.alice_angles_deg[i] - cfg.bob_angles_deg[j] + 180) % 360) - 180
        rows.append((delta, c.expectation, c.stderr, c.theory, f"A{i}B{j}", int(ROLE_MATRIX[i, j]), c.n))
    df = pd.DataFrame(rows, columns=["delta", "E", "err", "th", "lab", "role", "n"])
    for role, name, color, symbol in ((ROLE_CHSH, "CHSH settings", S_ALICE, "circle"), (ROLE_KEY, "key settings", S_BOB, "diamond"), (2, "discarded settings", MUTED, "circle-open")):
        sub = df[df.role == role]
        fig.add_trace(
            go.Scatter(
                x=sub.delta, y=sub.E, mode="markers", name=name,
                error_y=dict(type="data", array=sub.err, color=color, thickness=1.5, width=4),
                marker=dict(size=11, color=color, symbol=symbol, line=dict(color="#0B1220", width=2)),
                text=sub.lab,
                customdata=np.stack([sub.th, sub.n, sub.err], axis=-1) if len(sub) else None,
                hovertemplate="%{text}  Δ = %{x:.0f}°<br>E measured %{y:.4f} ± %{customdata[2]:.4f}<br>E theory %{customdata[0]:.4f}<br>%{customdata[1]:,} rounds<extra></extra>",
            )
        )
    fig.update_layout(height=height, xaxis=dict(title="Δ = a − b (degrees)", dtick=45, range=[-185, 185]),
                      yaxis=dict(title="correlation E(a, b)", range=[-1.12, 1.12]))
    return fig


def correlation_heatmap(matrix: np.ndarray, cfg: ExperimentConfig, title: str, height: int = 300) -> go.Figure:
    """3×3 correlation matrix on a diverging scale (cyan −1, neutral 0, violet +1)."""
    x = [f"B{j} · {b:g}°" for j, b in enumerate(cfg.bob_angles_deg)]
    y = [f"A{i} · {a:g}°" for i, a in enumerate(cfg.alice_angles_deg)]
    text = [[("—" if not math.isfinite(v) else f"{(round(v, 3) or 0.0):+.3f}") for v in row] for row in matrix]
    role = [[{0: "key", 1: "CHSH", 2: "discard"}[int(ROLE_MATRIX[i, j])] for j in range(3)] for i in range(3)]
    fig = go.Figure(
        go.Heatmap(
            z=matrix, x=x, y=y, zmin=-1, zmax=1, text=text, texttemplate="%{text}",
            textfont=dict(color=INK, size=13), customdata=role, xgap=3, ygap=3,
            colorscale=[[0, "#0E7490"], [0.5, "#1E2638"], [1, "#6D4FD8"]],
            colorbar=dict(thickness=8, outlinewidth=0, tickfont=dict(color=INK_2, size=10), len=0.9),
            hovertemplate="%{y} × %{x}<br>E = %{z:.4f}<br>role: %{customdata}<extra></extra>",
        )
    )
    fig.update_layout(title=title, height=height, yaxis=dict(autorange="reversed"), margin=dict(l=80, r=10, t=40, b=40))
    return fig


def agreement_bars(res: ExperimentResult, height: int = 320) -> go.Figure:
    """Share of rounds with equal vs opposite outcomes for each setting pair, with the theory value."""
    labels, same, opp, th = [], [], [], []
    for (i, j), c in sorted(res.bell.correlators.items()):
        n = max(c.n, 1)
        labels.append(f"A{i}B{j}")
        same.append((c.counts[0, 0] + c.counts[1, 1]) / n)
        opp.append((c.counts[0, 1] + c.counts[1, 0]) / n)
        th.append((1 + c.theory) / 2)
    fig = go.Figure()
    fig.add_bar(x=labels, y=same, name="equal outcomes", marker=dict(color=S_ALICE, line=dict(color="#0B1220", width=2)),
                hovertemplate="%{x}: equal %{y:.3f}<extra></extra>")
    fig.add_bar(x=labels, y=opp, name="opposite outcomes", marker=dict(color=S_BOB, line=dict(color="#0B1220", width=2)),
                hovertemplate="%{x}: opposite %{y:.3f}<extra></extra>")
    fig.add_scatter(x=labels, y=th, mode="markers", name="theory: equal", marker=dict(symbol="line-ew", size=26, color=INK, line=dict(width=2, color=INK)),
                    hovertemplate="%{x}: theory equal %{y:.3f}<extra></extra>")
    fig.update_layout(barmode="stack", height=height, yaxis=dict(title="fraction of rounds", range=[0, 1.02], tickformat=".0%"))
    return fig


# ---------------------------------------------------------------------------
# CHSH
# ---------------------------------------------------------------------------


def chsh_scale(entries: Sequence[tuple[str, float, float, str]], height: int = 220) -> go.Figure:
    """S with ±1σ and ±2σ intervals on a 0–3 scale. entries: (label, S, stderr, colour)."""
    fig = go.Figure()
    fig.add_vrect(x0=0, x1=CLASSICAL_BOUND, fillcolor="rgba(248,113,113,0.06)", line_width=0)
    fig.add_vrect(x0=CLASSICAL_BOUND, x1=TSIRELSON_BOUND, fillcolor="rgba(167,139,250,0.08)", line_width=0)
    fig.add_annotation(x=1.0, y=1.0, yref="paper", text="local realism allows", showarrow=False, font=dict(color=MUTED, size=11), yanchor="bottom")
    fig.add_annotation(x=(CLASSICAL_BOUND + TSIRELSON_BOUND) / 2, y=1.0, yref="paper", text="only quantum", showarrow=False, font=dict(color=MUTED, size=11), yanchor="bottom")
    for label, s, err, color in entries:
        if not math.isfinite(s):
            continue
        fig.add_trace(go.Scatter(
            x=[s], y=[label], mode="markers+text", text=[f"{s:.3f} ± {err:.3f}"], textposition="top left" if s > 2.3 else "top right",
            textfont=dict(color=INK, size=12),
            marker=dict(size=15, color=color, line=dict(color="#0B1220", width=2)),
            error_x=dict(type="data", array=[2 * err], color=color, thickness=2, width=6),
            name=label, showlegend=False, hovertemplate=f"{label}<br>S = {s:.4f}<br>σ = {err:.4f}<br>bars: ±2σ<extra></extra>",
        ))
    for val, color, text in ((CLASSICAL_BOUND, CRITICAL, "2"), (TSIRELSON_BOUND, VIOLET, "2√2")):
        fig.add_vline(x=val, line=dict(color=color, width=1.5, dash="dot"), annotation_text=text,
                      annotation_position="bottom", annotation_font=dict(color=color, size=11))
    n = len(entries)
    fig.update_layout(height=height, xaxis=dict(range=[0, 3.05], title="CHSH parameter S", dtick=0.5),
                      yaxis=dict(showgrid=False, range=[-0.6, n - 0.25]), margin=dict(l=110, r=20, t=40, b=48))
    return fig


def chsh_terms(results: Sequence[tuple[str, ExperimentResult, str]], height: int = 320) -> go.Figure:
    """The four CHSH correlators (measured ± σ) for one or more runs, with theory ticks."""
    fig = go.Figure()
    first = results[0][1]
    symbols = [f"{sym}<br>A{c.alice_idx}B{c.bob_idx}" for sym, c, _ in first.bell.chsh_terms()]
    for label, res, color in results:
        terms = res.bell.chsh_terms()
        fig.add_bar(
            x=symbols, y=[c.expectation for _, c, _ in terms], name=label,
            marker=dict(color=color, line=dict(color="#0B1220", width=2)),
            error_y=dict(type="data", array=[c.stderr for _, c, _ in terms], color=INK_2, thickness=1.2, width=4),
            hovertemplate="%{x}<br>E = %{y:.4f}<extra>" + label + "</extra>",
        )
        fig.add_scatter(
            x=symbols, y=[c.theory for _, c, _ in terms], mode="markers", name="theory" if len(results) == 1 else f"{label}: theory",
            marker=dict(symbol="line-ew", size=30, line=dict(width=2.5, color=INK)), showlegend=len(results) == 1,
            hovertemplate="%{x}<br>theory %{y:.4f}<extra></extra>",
        )
    fig.add_hline(y=0, line=dict(color=LINE_STRONG, width=1))
    fig.update_layout(barmode="group", height=height, yaxis=dict(title="E", range=[-1.08, 1.08]))
    return fig


def chsh_histogram(df: pd.DataFrame, s_theory: float, height: int = 330) -> go.Figure:
    fig = go.Figure()
    fig.add_histogram(x=df.S, nbinsx=min(40, max(10, len(df) // 4)), name="simulated trials",
                      marker=dict(color=S_ALICE, line=dict(color="#0B1220", width=1.5)),
                      hovertemplate="S ∈ %{x}<br>%{y} trials<extra></extra>")
    if len(df) > 1 and df.S_stderr.notna().all():
        sigma = float(df.S_stderr.mean())
        xs = np.linspace(df.S.min() - 3 * sigma, df.S.max() + 3 * sigma, 200)
        binw = (df.S.max() - df.S.min()) / min(40, max(10, len(df) // 4)) or sigma
        ys = len(df) * binw * np.exp(-0.5 * ((xs - s_theory) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))
        fig.add_scatter(x=xs, y=ys, mode="lines", name="normal(S_theory, σ̄)", line=dict(color=THEORY, dash="dash", width=2), hoverinfo="skip")
    _bounds(fig, "x")
    fig.update_layout(height=height, xaxis=dict(title="CHSH parameter S"), yaxis=dict(title="trials"), bargap=0.04,
                      legend=dict(orientation="h", y=-0.28, yanchor="top", x=0), margin=dict(t=40, b=80))
    return fig


def convergence_plot(df: pd.DataFrame, height: int = 330) -> go.Figure:
    fig = go.Figure()
    upper, lower = df.S + 2 * df.S_stderr, df.S - 2 * df.S_stderr
    fig.add_scatter(x=np.r_[df.pairs, df.pairs[::-1]], y=np.r_[upper, lower[::-1]], fill="toself", fillcolor="rgba(14,165,198,0.14)",
                    line=dict(width=0), name="±2σ", hoverinfo="skip")
    fig.add_scatter(x=df.pairs, y=df.S, mode="lines+markers", name="measured S", line=dict(color=S_ALICE, width=2), marker=dict(size=6),
                    hovertemplate="%{x:,} pairs<br>S = %{y:.4f}<extra></extra>")
    fig.add_scatter(x=df.pairs, y=df.S_theory, mode="lines", name="theory", line=dict(color=THEORY, dash="dash", width=1.5), hoverinfo="skip")
    _bounds(fig, "y", show_labels=True)
    fig.update_layout(height=height, xaxis=dict(title="entangled pairs used", type="log"), yaxis=dict(title="S", range=[0.8, 3.6]))
    return fig


# ---------------------------------------------------------------------------
# Sweeps (one measure per chart — never a dual axis)
# ---------------------------------------------------------------------------


def sweep_plot(df: pd.DataFrame, x: str, y: str, y_err: str | None, y_theory: str, x_title: str, y_title: str,
               color: str, ref: Sequence[tuple[float, str, str]] = (), height: int = 320, pct: bool = False) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=df[x], y=df[y_theory], mode="lines", name="theory", line=dict(color=THEORY, dash="dash", width=2), hoverinfo="skip")
    fig.add_scatter(
        x=df[x], y=df[y], mode="markers", name="simulated",
        marker=dict(size=9, color=color, line=dict(color="#0B1220", width=2)),
        error_y=dict(type="data", array=df[y_err], color=color, thickness=1.4, width=3) if y_err else None,
        hovertemplate=f"{x_title}: %{{x:.2f}}<br>{y_title}: %{{y:{'.2%' if pct else '.4f'}}}<extra></extra>",
    )
    for val, col, text in ref:
        fig.add_hline(y=val, line=dict(color=col, width=1.5, dash="dot"), annotation_text=text,
                      annotation_position="top left", annotation_font=dict(color=col, size=11))
    fig.update_layout(height=height, xaxis=dict(title=x_title), yaxis=dict(title=y_title, tickformat=".0%" if pct else None))
    return fig


def compare_bars(labels: Sequence[str], values: Sequence[float], colors: Sequence[str], title: str, pct: bool = False,
                 errors: Sequence[float] | None = None, height: int = 260) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=list(labels), y=list(values), marker=dict(color=list(colors), line=dict(color="#0B1220", width=2)),
            text=[f"{v:.1%}" if pct else f"{v:.3f}" for v in values], textposition="outside", textfont=dict(color=INK),
            error_y=dict(type="data", array=list(errors), color=INK_2, thickness=1.2, width=4) if errors else None,
            hovertemplate="%{x}: %{y:" + (".2%" if pct else ".4f") + "}<extra></extra>",
        )
    )
    top = max([v for v in values if math.isfinite(v)] + [0.01])
    fig.update_layout(title=title, height=height, showlegend=False,
                      yaxis=dict(tickformat=".0%" if pct else None, range=[0, top * 1.3]), margin=dict(l=48, r=12, t=40, b=36))
    return fig
