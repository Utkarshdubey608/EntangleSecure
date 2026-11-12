import { get, post, tokens } from "../api.js";
import {
  esc, icons, callout, statusPill, statusLabel, toast, confirmDialog, busy, groupHex,
  fmtBytes, skeletonLines, candColor,
} from "../util.js";
import { renderAudit } from "./verify.js";

const ATTACKS = [
  { kind: "modify_ballot", title: "Edit a stored ballot", body: "Flips bytes inside one encrypted ballot in the database." },
  { kind: "delete_ballot", title: "Delete a ballot", body: "Removes one ballot from the bulletin board." },
  { kind: "inject_ballot", title: "Stuff the ballot box", body: "Adds a ballot that no voter credential paid for." },
  { kind: "forge_result", title: "Forge the result", body: "Changes the published vote counts after the tally." },
];
const PHASES = ["setup", "open", "closed", "tallied"];

export async function render(root) {
  let alive = true;
  const cleanup = () => { alive = false; };

  if (!tokens.get("admin")) {
    drawLogin();
    return cleanup;
  }
  await drawConsole();
  return cleanup;

  // ---------------------------------------------------------------- login
  function drawLogin(message) {
    root.innerHTML = `
    <div class="page">
      <header class="page-head">
        <h1>Election authority</h1>
        <p>Create elections, open and close the polls, run the tally, and try to tamper with the record to see the audit catch it.</p>
      </header>
      <section class="panel admin-login">
        <h3>Sign in as administrator</h3>
        <p class="muted">The authority holds the ML-KEM decryption key and the ML-DSA signing key.</p>
        <form class="form-grid" novalidate>
          <div class="field">
            <label for="admin-pw">Administrator password</label>
            <input class="input" id="admin-pw" name="password" type="password" autocomplete="current-password">
            <span class="hint">Demo password: quantum-admin</span>
          </div>
          <div data-err>${message ? callout("warn", esc(message)) : ""}</div>
          <div><button class="btn btn-primary" type="submit">Sign in</button></div>
        </form>
      </section>
    </div>`;
    const form = root.querySelector("form");
    form.password.focus();
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const errBox = form.querySelector("[data-err]");
      if (!form.password.value) { errBox.innerHTML = callout("error", "Enter the administrator password."); return; }
      try {
        const r = await busy(form.querySelector("button"), "Signing in…", () => post("/admin/login", { password: form.password.value }));
        tokens.set("admin", r.token);
        await drawConsole();
      } catch (err) {
        errBox.innerHTML = callout("error", esc(err.status === 401 ? "That password isn't correct." : err.message));
      }
    });
  }

  function handleAuth(err) {
    if (err && err.status === 401) {
      tokens.clear("admin");
      drawLogin("Your administrator session ended. Sign in again.");
      return true;
    }
    return false;
  }

  // ---------------------------------------------------------------- console
  async function drawConsole() {
    root.innerHTML = `
    <div class="page">
      <div class="admin-bar">
        <div>
          <h1 style="font-size:var(--fs-2xl)">Election authority console</h1>
          <p class="muted" style="margin-top:6px">Every action here goes through the same API and cryptography as a real voter.</p>
        </div>
        <button class="btn btn-ghost" type="button" data-logout>Sign out</button>
      </div>
      <div class="admin-grid">
        <section class="panel" data-lifecycle>${skeletonLines(5)}</section>
        <section class="panel" data-demo>
          <h3>Demo tools</h3>
          <p class="muted">Get a full election ready to present in seconds.</p>
          <div class="stack">
            <div class="attack">
              <div><b>Reset the demo election</b><span>New authority keys, 4 candidates, voters V001–V030. Erases the current election.</span></div>
              <button class="btn btn-danger btn-sm" type="button" data-reset>Reset</button>
            </div>
            <form class="inline-form" data-sim>
              <div class="field"><label for="sim-n">Simulate voters casting ballots</label><input class="input" id="sim-n" type="number" min="1" max="200" value="10"></div>
              <button class="btn btn-ghost" type="submit">Cast ballots</button>
            </form>
            <p class="faint" style="font-size:var(--fs-xs)">Simulated voters sign in, get a credential and cast through the full encrypted flow.</p>
          </div>
        </section>
        <section class="panel attack-panel span-2" data-attacks>
          <div class="section-head" style="margin-bottom:14px">
            <div><h3>Attack simulator</h3><p>Act as a corrupt insider with direct database access. After each attack the public audit re-runs to show whether it's caught.</p></div>
            <button class="btn btn-ghost btn-sm" type="button" data-restore>Undo all attacks</button>
          </div>
          <div class="grid-2">
            <div class="attack-list">
              ${ATTACKS.map((a) => `<div class="attack"><div><b>${esc(a.title)}</b><span>${esc(a.body)}</span></div>
                <button class="btn btn-danger btn-sm" type="button" data-attack="${esc(a.kind)}">Attack</button></div>`).join("")}
            </div>
            <div>
              <div class="btn-row"><button class="btn btn-quantum btn-sm" type="button" data-run-audit>Run the public audit</button></div>
              <div class="audit-mini" data-audit><p class="faint" style="font-size:var(--fs-sm)">Run an attack or the audit to see the checklist.</p></div>
            </div>
          </div>
        </section>
        <section class="panel span-2" data-voters>${skeletonLines(4)}</section>
        <section class="panel" data-keys>${skeletonLines(5)}</section>
        <section class="panel" data-create></section>
      </div>
    </div>`;

    root.querySelector("[data-logout]").addEventListener("click", () => {
      tokens.clear("admin");
      toast("Signed out");
      drawLogin();
    });
    wireDemo();
    wireAttacks();
    drawCreate();
    await Promise.all([refreshLifecycle(), refreshVoters(), refreshKeys()]);
  }

  // ---------------------------------------------------------------- lifecycle
  async function refreshLifecycle() {
    const box = root.querySelector("[data-lifecycle]");
    if (!box) return;
    let el;
    try {
      el = await get("/election");
    } catch (err) {
      if (!alive) return;
      box.innerHTML = err.status === 404
        ? `<h3>No election yet</h3><p class="muted" style="margin-top:6px">Create one below, or reset the demo election to start with sample candidates and voters.</p>`
        : callout("error", esc(err.message));
      return;
    }
    if (!alive || !box.isConnected) return;
    const idx = PHASES.indexOf(el.status);
    const s = el.stats || {};
    box.innerHTML = `
      <div class="status-card-top">
        <div><div class="status-card-label">Election</div><h3 style="margin-top:4px">${esc(el.title)}</h3></div>
        ${statusPill(el.status)}
      </div>
      <ol class="lifecycle" aria-label="Election phase">
        ${PHASES.map((p, i) => `<li class="${i < idx ? "done" : i === idx ? "current" : ""}">${esc(statusLabel(p))}</li>`).join("")}
      </ol>
      <dl class="status-stats" style="margin-top:0">
        <div><dt>Registered</dt><dd>${esc(s.registered ?? 0)}</dd></div>
        <div><dt>Credentials</dt><dd>${esc(s.credentials_issued ?? 0)}</dd></div>
        <div><dt>Ballots</dt><dd>${esc(s.ballots_cast ?? 0)}</dd></div>
      </dl>
      <div class="btn-row" style="margin-top:20px">
        <button class="btn btn-primary" type="button" data-phase="open" ${el.status === "setup" ? "" : "disabled"}>Open the polls</button>
        <button class="btn btn-ghost" type="button" data-phase="close" ${el.status === "open" ? "" : "disabled"}>Close the polls</button>
        <button class="btn btn-quantum" type="button" data-phase="tally" ${el.status === "closed" ? "" : "disabled"}>Decrypt and tally</button>
      </div>`;
    const PHASE_COPY = {
      open: { title: "Open the polls?", body: "Voters can request credentials and cast ballots until you close the polls.", confirm: "Open the polls", done: "Polls opened" },
      close: { title: "Close the polls?", body: "No more ballots will be accepted. The authority signs the final bulletin-board head with ML-DSA-65. This can't be undone.", confirm: "Close the polls", done: "Polls closed and final head signed" },
      tally: { title: "Decrypt and tally?", body: "Every ballot is decapsulated with the ML-KEM private key, decrypted and counted. The result is signed and published. This can't be undone.", confirm: "Decrypt and tally", done: "Results published" },
    };
    box.querySelectorAll("[data-phase]").forEach((b) => b.addEventListener("click", async () => {
      const copy = PHASE_COPY[b.dataset.phase];
      if (!(await confirmDialog(copy))) return;
      try {
        await busy(b, "Working…", () => post(`/admin/election/${b.dataset.phase}`, {}, { auth: "admin" }));
        toast(copy.done, "ok");
        await Promise.all([refreshLifecycle(), refreshVoters()]);
      } catch (err) {
        if (!handleAuth(err)) toast(err.message, "error");
      }
    }));
  }

  // ---------------------------------------------------------------- demo tools
  function wireDemo() {
    const reset = root.querySelector("[data-reset]");
    reset.addEventListener("click", async () => {
      const ok = await confirmDialog({
        title: "Reset the demo election?",
        body: "This deletes the current election, its ballots and its keys, then creates a fresh demo election with new post-quantum keys and 30 voters.",
        confirm: "Reset the election",
        danger: true,
      });
      if (!ok) return;
      try {
        await busy(reset, "Generating keys…", () => post("/admin/reset-demo", {}, { auth: "admin" }));
        toast("Demo election created with fresh ML-KEM and ML-DSA keys", "ok");
        root.querySelector("[data-audit]").innerHTML = `<p class="faint" style="font-size:var(--fs-sm)">Run an attack or the audit to see the checklist.</p>`;
        await Promise.all([refreshLifecycle(), refreshVoters(), refreshKeys()]);
      } catch (err) {
        if (!handleAuth(err)) toast(err.message, "error");
      }
    });
    const sim = root.querySelector("[data-sim]");
    sim.addEventListener("submit", async (e) => {
      e.preventDefault();
      const n = Math.round(Number(sim.querySelector("input").value));
      if (!Number.isFinite(n) || n < 1 || n > 200) { toast("Choose between 1 and 200 ballots.", "error"); return; }
      try {
        const r = await busy(sim.querySelector("button"), "Encrypting ballots…", () => post("/admin/simulate", { count: n }, { auth: "admin" }));
        toast(`${r.cast} encrypted ${r.cast === 1 ? "ballot" : "ballots"} cast`, "ok");
        await Promise.all([refreshLifecycle(), refreshVoters()]);
      } catch (err) {
        if (!handleAuth(err)) toast(err.message, "error");
      }
    });
  }

  // ---------------------------------------------------------------- attacks
  async function runAudit(flash) {
    const box = root.querySelector("[data-audit]");
    try {
      const a = await get("/audit");
      if (alive && box.isConnected) renderAudit(box, a, { flashFailures: flash });
    } catch (err) {
      if (alive && box.isConnected) box.innerHTML = callout("error", esc(err.message));
    }
  }

  function wireAttacks() {
    root.querySelectorAll("[data-attack]").forEach((b) => b.addEventListener("click", async () => {
      try {
        const r = await busy(b, "Attacking…", () => post("/admin/attack", { kind: b.dataset.attack }, { auth: "admin" }));
        toast(r.description || "Attack applied", "error");
        await runAudit(true);
        await refreshLifecycle();
      } catch (err) {
        if (!handleAuth(err)) toast(err.message, "error");
      }
    }));
    const restore = root.querySelector("[data-restore]");
    restore.addEventListener("click", async () => {
      try {
        await busy(restore, "Restoring…", () => post("/admin/attack/restore", {}, { auth: "admin" }));
        toast("All attacks undone. The original record is back.", "ok");
        await runAudit(false);
        await refreshLifecycle();
      } catch (err) {
        if (!handleAuth(err)) toast(err.message, "error");
      }
    });
    const auditBtn = root.querySelector("[data-run-audit]");
    auditBtn.addEventListener("click", () => busy(auditBtn, "Auditing…", () => runAudit(true)));
  }

  // ---------------------------------------------------------------- voters
  async function refreshVoters() {
    const box = root.querySelector("[data-voters]");
    if (!box) return;
    let data;
    try {
      data = await get("/admin/voters", { auth: "admin" });
    } catch (err) {
      if (!alive) return;
      if (handleAuth(err)) return;
      box.innerHTML = `<h3>Electoral roll</h3>${callout(err.status === 404 ? "info" : "error", esc(err.status === 404 ? "Create an election to start the electoral roll." : err.message))}`;
      return;
    }
    if (!alive || !box.isConnected) return;
    const voters = data.voters || [];
    const issued = voters.filter((v) => v.credential_issued).length;
    box.innerHTML = `
      <div class="section-head" style="margin-bottom:14px">
        <div><h3>Electoral roll</h3><p>${voters.length} registered, ${issued} credentials issued. The roll records who received a credential, never how they voted.</p></div>
      </div>
      <div class="table-wrap voters-table">
        <table>
          <thead><tr><th>Voter ID</th><th>Name</th><th>Demo password</th><th>Credential</th></tr></thead>
          <tbody>
            ${voters.length ? voters.map((v) => `<tr>
              <td class="mono">${esc(v.voter_id)}</td>
              <td>${esc(v.name)}</td>
              <td class="mono">${esc(v.demo_password)}</td>
              <td>${v.credential_issued ? '<span class="pill pill-good">Issued</span>' : '<span class="pill">Not yet</span>'}</td>
            </tr>`).join("") : `<tr><td colspan="4" class="muted">No voters registered yet.</td></tr>`}
          </tbody>
        </table>
      </div>
      <form class="inline-form" data-add style="margin-top:16px">
        <div class="field" style="flex:1 1 320px"><label for="new-voters">Register voters</label>
          <input class="input" id="new-voters" placeholder="Full names, separated by commas"></div>
        <button class="btn btn-ghost" type="submit">Register</button>
      </form>`;
    const form = box.querySelector("[data-add]");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const names = form.querySelector("input").value.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
      if (!names.length) { toast("Enter at least one name.", "error"); return; }
      try {
        const r = await busy(form.querySelector("button"), "Registering…", () => post("/admin/voters", { names }, { auth: "admin" }));
        const created = Array.isArray(r) ? r : r.voters || [];
        toast(`Registered ${created.length || names.length} ${names.length === 1 ? "voter" : "voters"}`, "ok");
        await Promise.all([refreshVoters(), refreshLifecycle()]);
      } catch (err) {
        if (!handleAuth(err)) toast(err.message, "error");
      }
    });
  }

  // ---------------------------------------------------------------- keys
  async function refreshKeys() {
    const box = root.querySelector("[data-keys]");
    if (!box) return;
    let k;
    try {
      k = await get("/admin/keys", { auth: "admin" });
    } catch (err) {
      if (!alive) return;
      if (handleAuth(err)) return;
      box.innerHTML = `<h3>Authority keys</h3>${callout(err.status === 404 ? "info" : "error", esc(err.status === 404 ? "Keys are generated when an election is created." : err.message))}`;
      return;
    }
    if (!alive || !box.isConnected) return;
    box.innerHTML = `<h3>Authority keys</h3>
      <p class="muted">Public material only. Secret keys never leave the server.</p>
      <dl class="keys-list">${renderKeyEntries(k)}</dl>`;
  }

  function renderKeyEntries(obj) {
    const scalarRow = (key, value) => {
      const str = Array.isArray(value) ? value.join(", ") : String(value ?? "—");
      const isHex = /^[0-9a-f]{24,}$/i.test(str);
      const isBytes = /bytes$/i.test(key) && Number.isFinite(Number(value));
      if (isHex) {
        return `<div class="kv kv-hex"><span>${esc(humanize(key))}</span><span class="hash">${esc(groupHex(str.slice(0, 64)) + (str.length > 64 ? " …" : ""))}</span></div>`;
      }
      return `<div class="kv"><span>${esc(humanize(key))}</span><span>${esc(isBytes ? fmtBytes(value) : str)}</span></div>`;
    };
    const flat = [];
    const groups = [];
    for (const [key, value] of Object.entries(obj || {})) {
      if (value && typeof value === "object" && !Array.isArray(value)) groups.push([key, value]);
      else flat.push(scalarRow(key, value));
    }
    const groupTitle = (key, value) => value.algorithm ? `${value.algorithm}${value.standard ? ` (${value.standard})` : ""}` : humanize(key);
    return [
      flat.length ? `<div class="key-item">${flat.join("")}</div>` : "",
      ...groups.map(([key, value]) => `<div class="key-item"><dt>${esc(groupTitle(key, value))}</dt><dd>${
        Object.entries(value).filter(([k]) => k !== "algorithm" && k !== "standard").map(([k, v]) =>
          v && typeof v === "object" && !Array.isArray(v) ? scalarRow(k, JSON.stringify(v)) : scalarRow(k, v)).join("")
      }</dd></div>`),
    ].join("");
  }

  function humanize(key) {
    const s = String(key).replace(/_/g, " ").replace(/\balg\b/i, "algorithm").replace(/\bkem\b/i, "KEM").replace(/\bsig\b/i, "signature");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  // ---------------------------------------------------------------- create
  function drawCreate() {
    const box = root.querySelector("[data-create]");
    const rows = [
      { name: "", party: "" },
      { name: "", party: "" },
    ];
    box.innerHTML = `
      <h3>Create a new election</h3>
      <p class="muted">Generates a fresh ML-KEM-768 key pair and ML-DSA-65 key pair, and signs the election manifest. Replaces the current election.</p>
      <form class="form-grid" novalidate>
        <div class="field"><label for="el-title">Title</label><input class="input" id="el-title" name="title" placeholder="Student Council Election 2026" maxlength="120"></div>
        <div class="field"><label for="el-desc">Description</label><textarea class="textarea" id="el-desc" name="description" rows="2" maxlength="400" placeholder="Who is voting, and for what"></textarea></div>
        <div class="field"><label>Candidates</label><div class="cand-rows" data-rows></div>
          <div><button class="btn btn-ghost btn-sm" type="button" data-add-row style="margin-top:4px">Add a candidate</button></div></div>
        <div data-err></div>
        <div><button class="btn btn-primary" type="submit">Create election</button></div>
      </form>`;
    const rowsBox = box.querySelector("[data-rows]");
    const drawRows = () => {
      rowsBox.innerHTML = rows.map((r, i) => `<div class="cand-row" style="--cand:${esc(candColor(null, i))}">
        <input class="input" aria-label="Candidate ${i + 1} name" placeholder="Candidate ${i + 1} name" data-i="${i}" data-f="name" value="${esc(r.name)}" maxlength="80">
        <input class="input" aria-label="Candidate ${i + 1} party" placeholder="Party or slate (optional)" data-i="${i}" data-f="party" value="${esc(r.party)}" maxlength="80">
        <button class="icon-btn" type="button" data-del="${i}" aria-label="Remove candidate ${i + 1}" ${rows.length <= 2 ? "disabled" : ""}>${icons.trash}</button>
      </div>`).join("");
    };
    drawRows();
    rowsBox.addEventListener("input", (e) => {
      const t = e.target;
      if (t.dataset.i != null) rows[Number(t.dataset.i)][t.dataset.f] = t.value;
    });
    rowsBox.addEventListener("click", (e) => {
      const del = e.target.closest("[data-del]");
      if (del && rows.length > 2) { rows.splice(Number(del.dataset.del), 1); drawRows(); }
    });
    box.querySelector("[data-add-row]").addEventListener("click", () => {
      if (rows.length >= 8) { toast("An election can have up to 8 candidates here.", "error"); return; }
      rows.push({ name: "", party: "" });
      drawRows();
      rowsBox.querySelector(`[data-i="${rows.length - 1}"][data-f="name"]`)?.focus();
    });
    const form = box.querySelector("form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const errBox = box.querySelector("[data-err]");
      const title = form.elements.title.value.trim();
      const description = form.elements.description.value.trim();
      const candidates = rows.map((r) => ({ name: r.name.trim(), party: r.party.trim() })).filter((r) => r.name);
      if (!title) { errBox.innerHTML = callout("error", "Give the election a title."); return; }
      if (candidates.length < 2) { errBox.innerHTML = callout("error", "Add at least two candidates with names."); return; }
      const ok = await confirmDialog({
        title: "Create this election?",
        body: "The current election, its ballots and its keys will be replaced. New post-quantum keys are generated for this one.",
        confirm: "Create election",
        danger: true,
      });
      if (!ok) return;
      errBox.innerHTML = "";
      try {
        await busy(form.querySelector("button[type=submit]"), "Generating keys…", () => post("/admin/election", { title, description, candidates }, { auth: "admin" }));
        toast("Election created. Register voters, then open the polls.", "ok");
        form.reset();
        rows.splice(0, rows.length, { name: "", party: "" }, { name: "", party: "" });
        drawRows();
        await Promise.all([refreshLifecycle(), refreshVoters(), refreshKeys()]);
      } catch (err) {
        if (!handleAuth(err)) errBox.innerHTML = callout("error", esc(err.message));
      }
    });
  }
}
