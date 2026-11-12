// A drifting 2-D lattice: the mathematical structure behind ML-KEM and ML-DSA.
// Points are integer combinations of two skewed basis vectors; the highlighted
// path traces a short lattice vector, the object that is hard to find.
import { reducedMotion } from "./util.js";

export function mountLattice(canvas, { density = 1, highlight = true } = {}) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};
  let raf = 0;
  let running = true;
  let w = 0;
  let h = 0;
  let dpr = 1;
  const t0 = performance.now();

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = canvas.getBoundingClientRect();
    w = Math.max(1, rect.width);
    h = Math.max(1, rect.height);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw(now) {
    const t = (now - t0) / 1000;
    ctx.clearRect(0, 0, w, h);
    const unit = Math.max(34, Math.min(62, w / 22)) / density;
    const angle = 0.18 + Math.sin(t * 0.05) * 0.04;
    const b1 = { x: unit * Math.cos(angle), y: unit * Math.sin(angle) };
    const b2 = { x: unit * 0.42 + Math.sin(t * 0.07) * 4, y: unit * 0.93 };
    const ox = w * 0.62 + Math.sin(t * 0.04) * 18;
    const oy = h * 0.5 + Math.cos(t * 0.05) * 12;

    const span = Math.ceil(Math.max(w, h) / unit) + 4;
    // faint basis grid
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(147,163,194,0.07)";
    for (let i = -span; i <= span; i++) {
      ctx.beginPath();
      ctx.moveTo(ox + i * b1.x - span * b2.x, oy + i * b1.y - span * b2.y);
      ctx.lineTo(ox + i * b1.x + span * b2.x, oy + i * b1.y + span * b2.y);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(ox + i * b2.x - span * b1.x, oy + i * b2.y - span * b1.y);
      ctx.lineTo(ox + i * b2.x + span * b1.x, oy + i * b2.y + span * b1.y);
      ctx.stroke();
    }
    // lattice points
    for (let i = -span; i <= span; i++) {
      for (let j = -span; j <= span; j++) {
        const x = ox + i * b1.x + j * b2.x;
        const y = oy + i * b1.y + j * b2.y;
        if (x < -10 || y < -10 || x > w + 10 || y > h + 10) continue;
        const d = Math.hypot(x - ox, y - oy) / Math.max(w, h);
        const tw = 0.5 + 0.5 * Math.sin(t * 0.9 + i * 1.7 + j * 2.3);
        const a = Math.max(0.08, 0.55 - d * 0.9) * (0.65 + 0.35 * tw);
        ctx.fillStyle = `rgba(165,134,255,${a.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(x, y, 1.6 + tw * 0.6, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (highlight) {
      // basis vectors from the origin, and a short vector b1 - b2 pulsing
      const pulse = 0.55 + 0.45 * Math.sin(t * 1.4);
      const arrow = (v, color, width) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(ox, oy);
        ctx.lineTo(ox + v.x, oy + v.y);
        ctx.stroke();
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(ox + v.x, oy + v.y, 3.2, 0, Math.PI * 2);
        ctx.fill();
      };
      arrow({ x: 3 * b1.x + 2 * b2.x, y: 3 * b1.y + 2 * b2.y }, "rgba(147,163,194,0.35)", 1.4);
      arrow({ x: -2 * b1.x + 3 * b2.x, y: -2 * b1.y + 3 * b2.y }, "rgba(147,163,194,0.35)", 1.4);
      arrow({ x: b1.x - b2.x, y: b1.y - b2.y }, `rgba(45,212,232,${(0.5 + pulse * 0.5).toFixed(3)})`, 2.4);
      ctx.fillStyle = "#E6ECF7";
      ctx.beginPath();
      ctx.arc(ox, oy, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = `rgba(45,212,232,${(0.25 * pulse).toFixed(3)})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(ox, oy, 10 + pulse * 10, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  function loop(now) {
    if (!running) return;
    draw(now);
    raf = requestAnimationFrame(loop);
  }

  resize();
  const ro = typeof ResizeObserver === "function" ? new ResizeObserver(() => { resize(); if (reducedMotion()) draw(performance.now()); }) : null;
  ro?.observe(canvas);

  let visible = true;
  const io = typeof IntersectionObserver === "function"
    ? new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        if (visible && !reducedMotion() && running) { cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); }
        else cancelAnimationFrame(raf);
      })
    : null;
  io?.observe(canvas);

  if (reducedMotion()) draw(t0 + 4000);
  else raf = requestAnimationFrame(loop);

  return () => {
    running = false;
    cancelAnimationFrame(raf);
    ro?.disconnect();
    io?.disconnect();
  };
}
