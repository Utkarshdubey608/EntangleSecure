const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/[&<>"']/g, (c) => ESC[c]);
}

export const icons = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" aria-hidden="true"><path d="M7 7l10 10M17 7L7 17"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v6M12 7.5v.01"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5l9.5 16.5h-19z"/><path d="M12 10v4.5M12 17.5v.01"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2.8l7.5 3v6c0 4.6-3.2 8-7.5 9.4-4.3-1.4-7.5-4.8-7.5-9.4v-6z"/><path d="M8.5 12.2l2.4 2.4 4.6-4.8"/></svg>',
  shieldBad: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2.8l7.5 3v6c0 4.6-3.2 8-7.5 9.4-4.3-1.4-7.5-4.8-7.5-9.4v-6z"/><path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13"/></svg>',
  logo: '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="8" fill="#0A1428"/><path d="M9.5 16.5l4.5 4.5L23 11" fill="none" stroke="#2DD4E8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

export const reducedMotion = () =>
  typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export const sleep = (ms) => new Promise((r) => setTimeout(r, reducedMotion() ? 0 : ms));

export function groupHex(hex, size = 4) {
  const clean = String(hex || "").replace(/[^0-9a-f]/gi, "").toLowerCase();
  return clean.match(new RegExp(`.{1,${size}}`, "g"))?.join(" ") ?? "";
}

export function shortHex(hex, head = 10, tail = 6) {
  const s = String(hex || "");
  if (s.length <= head + tail + 1) return s;
  return `${s.slice(0, head)}…${s.slice(-tail)}`;
}

export function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

export function fmtBytes(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return `${Number(n).toLocaleString()} B`;
}

export function fmtMs(ms) {
  const v = Number(ms);
  if (!Number.isFinite(v)) return "—";
  if (v < 0.1) return `${v.toFixed(3)} ms`;
  if (v < 10) return `${v.toFixed(2)} ms`;
  return `${v.toFixed(1)} ms`;
}

export function fmtPct(fraction) {
  const v = Number(fraction);
  if (!Number.isFinite(v)) return "—";
  return `${(v * 100).toFixed(v * 100 >= 10 || v === 0 ? 0 : 1)}%`;
}

const STATUS_LABEL = { setup: "Setting up", open: "Polls open", closed: "Polls closed", tallied: "Results published" };
export function statusPill(status) {
  const s = String(status || "");
  const cls = { setup: "pill-setup", open: "pill-open", closed: "pill-closed", tallied: "pill-tallied" }[s] || "";
  return `<span class="pill ${cls}">${esc(STATUS_LABEL[s] || s || "Unknown")}</span>`;
}
export const statusLabel = (s) => STATUS_LABEL[s] || s;

export function boolPill(value, { yes = "Valid", no = "Invalid", pending = "Pending" } = {}) {
  if (value === true) return `<span class="pill pill-good">${esc(yes)}</span>`;
  if (value === false) return `<span class="pill pill-bad">${esc(no)}</span>`;
  return `<span class="pill pill-wait">${esc(pending)}</span>`;
}

export function checkItem({ label, passed, detail, id }) {
  const state = passed === true ? "pass" : passed === false ? "fail" : "pending";
  const icon = passed === true ? icons.check : passed === false ? icons.cross : icons.clock;
  const srState = passed === true ? "Passed" : passed === false ? "Failed" : "Pending";
  return `<li class="check ${state}" ${id ? `data-check="${esc(id)}"` : ""}>
    <span class="check-icon">${icon}<span class="sr-only">${srState}</span></span>
    <div><div class="check-label">${esc(label)}</div>${detail ? `<div class="check-detail">${esc(detail)}</div>` : ""}</div>
  </li>`;
}

export function callout(kind, html) {
  const icon = { info: icons.info, warn: icons.warn, error: icons.warn, ok: icons.check }[kind] || icons.info;
  return `<div class="callout callout-${kind}">${icon}<div>${html}</div></div>`;
}

export function skeletonLines(n = 3, widths = ["90%", "70%", "80%", "60%"]) {
  return Array.from({ length: n }, (_, i) => `<span class="skeleton" style="width:${widths[i % widths.length]};margin-top:${i ? 10 : 0}px"></span>`).join("");
}

export function toast(message, kind = "info") {
  const host = document.querySelector(".toasts");
  if (!host) return;
  const el = document.createElement("div");
  el.className = `toast ${kind === "error" ? "toast-error" : kind === "ok" ? "toast-ok" : ""}`;
  el.textContent = message;
  host.appendChild(el);
  const ttl = kind === "error" ? 6500 : 3800;
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 250);
  }, ttl);
}

export function confirmDialog({ title, body, confirm = "Confirm", danger = false }) {
  const dlg = document.querySelector("dialog.confirm");
  if (!dlg || typeof dlg.showModal !== "function") return Promise.resolve(window.confirm(`${title}\n\n${body}`));
  dlg.querySelector(".confirm-title").textContent = title;
  dlg.querySelector(".confirm-body").textContent = body;
  const ok = dlg.querySelector(".confirm-ok");
  ok.textContent = confirm;
  ok.className = `btn ${danger ? "btn-danger" : "btn-primary"} confirm-ok`;
  dlg.returnValue = "cancel";
  return new Promise((resolve) => {
    dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
    dlg.showModal();
  });
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

export function downloadJSON(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Put a button into a busy state while an async task runs. */
export async function busy(button, label, task) {
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="spinner" aria-hidden="true"></span>${esc(label)}`;
  try {
    return await task();
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.innerHTML = original;
    }
  }
}

export function initials(name) {
  return String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

const FALLBACK_COLORS = ["#2DD4E8", "#A586FF", "#34D39A", "#F5B84B", "#FF8FA3", "#6FB4F3"];
export function candColor(c, i = 0) {
  const color = c && typeof c.color === "string" && /^#[0-9a-f]{3,8}$/i.test(c.color) ? c.color : null;
  return color || FALLBACK_COLORS[i % FALLBACK_COLORS.length];
}

export function errorState(err, retryLabel = "Try again") {
  return `<div class="state">
    <h3>This page couldn't load</h3>
    <p>${esc(err && err.message ? err.message : "Something went wrong.")}</p>
    <button class="btn btn-ghost" data-retry type="button">${esc(retryLabel)}</button>
  </div>`;
}
