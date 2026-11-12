import { get, post, tokens } from "../api.js";
import {
  esc, icons, callout, statusLabel, groupHex, fmtTime, fmtBytes, fmtMs, toast, sleep,
  copyText, downloadJSON, busy, initials, candColor, skeletonLines, reducedMotion,
} from "../util.js";

const STEPS = [
  { title: "Sign in", sub: "Prove you're on the roll" },
  { title: "Credential", sub: "Become anonymous" },
  { title: "Choose", sub: "Pick a candidate" },
  { title: "Encrypt and cast", sub: "Seal with ML-KEM" },
  { title: "Receipt", sub: "Signed with ML-DSA" },
];
const CRED_KEY = "qv_pending_credential";

function sessionGet(key) {
  try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch { return null; }
}
function sessionSet(key, value) {
  try {
    if (value == null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, JSON.stringify(value));
  } catch { /* not persisted */ }
}

export async function render(root) {
  const state = {
    step: 0,
    election: null,
    voter: null,
    credential: null,
    fingerprint: null,
    candidateId: null,
    receipt: null,
    trace: null,
  };

  const pending = sessionGet(CRED_KEY);
  if (pending && pending.credential) {
    state.credential = pending.credential;
    state.fingerprint = pending.fingerprint;
    state.voter = pending.voter || null;
    state.step = 2;
  } else if (tokens.get("voter")) {
    tokens.clear("voter");
  }

  root.innerHTML = `
  <div class="page">
    <header class="page-head">
      <h1>Cast your ballot</h1>
      <p>Your vote is encrypted before it reaches the ballot box, and the ballot box never learns your name. It takes about a minute.</p>
    </header>
    <div class="vote-layout">
      <ol class="stepper" aria-label="Voting progress"></ol>
      <section class="wizard-panel" aria-live="polite"><div>${skeletonLines(4)}</div></section>
    </div>
  </div>`;

  const stepper = root.querySelector(".stepper");
  const panel = root.querySelector(".wizard-panel");
  let alive = true;

  function drawStepper() {
    stepper.innerHTML = STEPS.map((s, i) => {
      const cls = i < state.step ? "done" : i === state.step ? "current" : "";
      const dot = i < state.step ? icons.check : String(i + 1);
      return `<li class="${cls}" ${i === state.step ? 'aria-current="step"' : ""}>
        <span class="dot">${dot}</span>
        <span><span class="stepper-title">${esc(s.title)}</span><br><span class="stepper-sub">${esc(s.sub)}</span></span>
      </li>`;
    }).join("");
  }

  function go(step) {
    state.step = step;
    drawStepper();
    [viewLogin, viewCredential, viewChoose, viewCast, viewReceipt][step]();
    panel.querySelector("h2")?.setAttribute("tabindex", "-1");
    panel.querySelector("h2")?.focus({ preventScroll: true });
  }

  // ---------------------------------------------------------------- step 1
  function viewLogin() {
    const el = state.election;
    const notOpen = el && el.status !== "open";
    panel.innerHTML = `
      <h2>Sign in to vote</h2>
      <p class="muted">Use the voter ID and password from your registration letter.</p>
      ${notOpen ? callout("warn", `<strong>${esc(el.title)}</strong> isn't accepting ballots right now. Its status is <strong>${esc(statusLabel(el.status))}</strong>. You can still sign in, but casting will be refused until the polls open.`) + "<br>" : ""}
      <form class="form-grid login-form" novalidate>
        <div class="field">
          <label for="voter-id">Voter ID</label>
          <input class="input mono" id="voter-id" name="voter_id" autocomplete="username" placeholder="V001" required>
        </div>
        <div class="field">
          <label for="voter-pw">Password</label>
          <input class="input" id="voter-pw" name="password" type="password" autocomplete="current-password" required>
          <span class="hint">Demo voters are V001 to V030. The password is qv- plus the number, for example qv-001.</span>
        </div>
        <div class="form-error"></div>
        <div><button class="btn btn-primary" type="submit">Sign in</button></div>
      </form>`;
    const form = panel.querySelector("form");
    const errBox = form.querySelector(".form-error");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const voter_id = form.voter_id.value.trim().toUpperCase();
      const password = form.password.value;
      if (!voter_id || !password) {
        errBox.innerHTML = callout("error", "Enter both your voter ID and your password.");
        return;
      }
      errBox.innerHTML = "";
      const btn = form.querySelector("button[type=submit]");
      try {
        const res = await busy(btn, "Checking the roll…", () => post("/voter/login", { voter_id, password }));
        tokens.set("voter", res.token);
        state.voter = res.voter;
        go(1);
      } catch (err) {
        errBox.innerHTML = callout("error", esc(err.status === 401 ? "That voter ID and password don't match the electoral roll. Check both and try again." : err.message));
      }
    });
    form.voter_id.focus();
  }

  // ---------------------------------------------------------------- step 2
  function viewCredential() {
    const v = state.voter || {};
    const already = v.credential_issued;
    panel.innerHTML = `
      <h2>Get your anonymous credential</h2>
      <p class="muted">The authority gives you one random credential that can be used once. From here on, your ballot carries only this credential, never your name.</p>
      <div class="unlink" aria-hidden="true">
        <div class="unlink-box"><small>Known to the authority</small><strong>${esc(v.name || "Voter")} (${esc(v.voter_id || "")})</strong></div>
        <div class="unlink-cut"></div>
        <div class="unlink-box"><small>Seen by the ballot box</small><strong>Random 256-bit credential</strong></div>
      </div>
      <div data-cred>
        ${already ? callout("warn", "This voter has already received a ballot credential. Each voter gets exactly one, so a second ballot isn't possible. If you were interrupted, return to this page in the same browser tab to finish.") : ""}
      </div>
      <div class="wizard-actions">
        <button class="btn btn-ghost" type="button" data-signout>Sign out</button>
        <button class="btn btn-quantum" type="button" data-issue ${already ? "disabled" : ""}>Issue my credential</button>
      </div>`;
    panel.querySelector("[data-signout]").addEventListener("click", () => {
      tokens.clear("voter");
      state.voter = null;
      go(0);
    });
    const issue = panel.querySelector("[data-issue]");
    issue.addEventListener("click", async () => {
      const box = panel.querySelector("[data-cred]");
      try {
        const res = await busy(issue, "Issuing…", () => post("/voter/credential", {}, { auth: "voter" }));
        state.credential = res.credential;
        state.fingerprint = res.credential_fingerprint;
        sessionSet(CRED_KEY, { credential: res.credential, fingerprint: res.credential_fingerprint, voter: state.voter });
        // The voter session is no longer needed: the rest of the flow is anonymous.
        tokens.clear("voter");
        box.innerHTML = `<div class="credential-box">
            <small>Credential fingerprint (SHA3-256)</small>
            <span class="hash">${esc(groupHex(res.credential_fingerprint))}</span>
            <small>The full credential stays in this browser tab and is spent when you cast.</small>
          </div>`;
        issue.outerHTML = `<button class="btn btn-primary" type="button" data-next>Choose a candidate</button>`;
        panel.querySelector("[data-next]").addEventListener("click", () => go(2));
        panel.querySelector("[data-signout]").remove();
        toast("Anonymous credential issued", "ok");
      } catch (err) {
        if (err.status === 409) {
          box.innerHTML = callout("warn", "This voter has already received a ballot credential. Each voter gets exactly one, so a second ballot isn't possible.");
          issue.disabled = true;
        } else if (err.status === 400) {
          box.innerHTML = callout("warn", `${esc(err.message)} Credentials are issued only while the polls are open.`);
        } else if (err.status === 401) {
          box.innerHTML = callout("error", "Your sign-in has expired. Sign in again to continue.");
          state.voter = null;
          setTimeout(() => alive && go(0), 1600);
        } else {
          box.innerHTML = callout("error", esc(err.message));
        }
      }
    });
  }

  // ---------------------------------------------------------------- step 3
  function viewChoose() {
    const cands = (state.election && state.election.candidates) || [];
    panel.innerHTML = `
      <h2>Choose one candidate</h2>
      <p class="muted">${esc(state.election ? state.election.title : "")}. Your choice stays on this screen until you confirm it on the next step.</p>
      ${cands.length ? `<div class="candidates" role="radiogroup" aria-label="Candidates">
        ${cands.map((c, i) => `
          <button type="button" class="candidate" role="radio" aria-checked="${state.candidateId === c.id}" data-id="${esc(c.id)}" style="--cand:${esc(candColor(c, i))}" tabindex="${state.candidateId === c.id || (!state.candidateId && i === 0) ? 0 : -1}">
            <span class="candidate-avatar">${esc(initials(c.name))}</span>
            <span><span class="candidate-name">${esc(c.name)}</span><br><span class="candidate-party">${esc(c.party || "Independent")}</span></span>
            <span class="candidate-radio" aria-hidden="true"></span>
          </button>`).join("")}
      </div>` : callout("warn", "This election has no candidates yet.")}
      <div class="wizard-actions">
        <span class="faint" style="font-size:var(--fs-xs)">Credential ${esc(String(state.fingerprint || "").slice(0, 8))}… ready</span>
        <button class="btn btn-primary" type="button" data-next ${state.candidateId ? "" : "disabled"}>Review my ballot</button>
      </div>`;
    const group = panel.querySelector("[role=radiogroup]");
    const next = panel.querySelector("[data-next]");
    if (group) {
      const radios = [...group.querySelectorAll("[role=radio]")];
      const select = (btn) => {
        radios.forEach((r) => { r.setAttribute("aria-checked", String(r === btn)); r.tabIndex = r === btn ? 0 : -1; });
        state.candidateId = btn.dataset.id;
        next.disabled = false;
      };
      radios.forEach((r, i) => {
        r.addEventListener("click", () => select(r));
        r.addEventListener("keydown", (e) => {
          const k = e.key;
          if (["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(k)) {
            e.preventDefault();
            const dir = k === "ArrowDown" || k === "ArrowRight" ? 1 : -1;
            const n = radios[(i + dir + radios.length) % radios.length];
            n.focus();
            select(n);
          }
        });
      });
    }
    next.addEventListener("click", () => go(3));
  }

  // ---------------------------------------------------------------- step 4
  function viewCast() {
    const cands = state.election.candidates || [];
    const idx = cands.findIndex((c) => c.id === state.candidateId);
    const c = cands[idx];
    panel.innerHTML = `
      <h2>Review and cast</h2>
      <p class="muted">Once cast, a ballot can't be changed. Your credential is spent and the encrypted ballot joins the public chain.</p>
      <div class="review-card" style="--cand:${esc(candColor(c, idx))}">
        <span class="candidate-avatar">${esc(initials(c && c.name))}</span>
        <div><div class="candidate-name">${esc(c ? c.name : "")}</div><div class="candidate-party">${esc(c ? c.party || "Independent" : "")}</div></div>
      </div>
      <ol class="trace" aria-label="Encryption steps">
        ${["ML-KEM-768 encapsulation", "HKDF-SHA3-256 key derivation", "AES-256-GCM encryption", "Hash-chain append (SHA3-256)", "Receipt signed (ML-DSA-65)"].map((s) => `
          <li class="trace-step"><span class="check-icon">${icons.clock}</span><div><div class="trace-name">${esc(s)}</div><div class="trace-detail">Waiting</div></div><div class="trace-meta"></div></li>`).join("")}
      </ol>
      <div data-err></div>
      <div class="wizard-actions">
        <button class="btn btn-ghost" type="button" data-back>Change my choice</button>
        <button class="btn btn-quantum" type="button" data-cast>Encrypt and cast ballot</button>
      </div>`;
    panel.querySelector("[data-back]").addEventListener("click", () => go(2));
    const castBtn = panel.querySelector("[data-cast]");
    castBtn.addEventListener("click", async () => {
      const errBox = panel.querySelector("[data-err]");
      errBox.innerHTML = "";
      panel.querySelector("[data-back]").disabled = true;
      let res;
      try {
        res = await busy(castBtn, "Encrypting…", () => post("/voter/cast", { credential: state.credential, candidate_id: state.candidateId }));
      } catch (err) {
        panel.querySelector("[data-back]").disabled = false;
        let msg = err.message;
        if (err.status === 403) {
          msg = "This credential was already used or isn't valid, so the ballot box refused it. Each credential can cast exactly one ballot.";
          sessionSet(CRED_KEY, null);
        } else if (err.status === 400) {
          msg = `${err.message} Ballots are accepted only while the polls are open.`;
        }
        errBox.innerHTML = "<br>" + callout("error", esc(msg));
        return;
      }
      castBtn.remove();
      panel.querySelector("[data-back]").remove();
      sessionSet(CRED_KEY, null);
      tokens.clear("voter");
      state.credential = null;
      state.receipt = res.receipt;
      state.trace = res.crypto_trace || [];
      await animateTrace(state.trace);
      if (!alive) return;
      const actions = panel.querySelector(".wizard-actions");
      actions.innerHTML = `<span class="muted" style="font-size:var(--fs-sm)">Ballot sealed and on the chain.</span>
        <button class="btn btn-primary" type="button" data-receipt>Show my receipt</button>`;
      actions.querySelector("[data-receipt]").addEventListener("click", () => go(4));
      actions.querySelector("[data-receipt]").focus();
    });
  }

  async function animateTrace(trace) {
    const list = panel.querySelector(".trace");
    // Rebuild from what the server actually did, in its order.
    list.innerHTML = trace.map((t) => `
      <li class="trace-step"><span class="check-icon">${icons.clock}</span>
        <div><div class="trace-name">${esc(t.step)}</div><div class="trace-detail">${esc(t.detail || "")}</div></div>
        <div class="trace-meta">${t.ms != null ? `<b>${esc(fmtMs(t.ms))}</b>` : ""}${t.bytes != null ? esc(fmtBytes(t.bytes)) : ""}</div>
      </li>`).join("");
    const items = [...list.children];
    for (const li of items) {
      if (!alive) return;
      li.classList.add("active");
      await sleep(reducedMotion() ? 0 : 420);
      li.classList.remove("active");
      li.classList.add("done");
      li.querySelector(".check-icon").innerHTML = icons.check;
    }
  }

  // ---------------------------------------------------------------- step 5
  function viewReceipt() {
    const r = state.receipt;
    const code = r.receipt_code;
    panel.innerHTML = `
      <h2>Your ballot is counted</h2>
      <p class="muted">Keep this receipt. It proves your encrypted ballot is on the public chain without revealing who you voted for.</p>
      <article class="ticket" aria-label="Ballot receipt">
        <div class="ticket-top">
          <div class="ticket-head">
            <span class="ticket-brand">${icons.logo} QuantumVote receipt</span>
            <span class="ticket-seal">Signed with ${esc(r.sig_alg || "ML-DSA-65")}</span>
          </div>
          <div class="ticket-label">Receipt code</div>
          <div class="ticket-code">${esc(groupHex(code))}</div>
        </div>
        <div class="ticket-perf" aria-hidden="true"></div>
        <dl class="ticket-bottom">
          <div><dt>Ballot number</dt><dd>#${esc(r.seq)}</dd></div>
          <div><dt>Cast at</dt><dd>${esc(fmtTime(r.cast_at))}</dd></div>
          <div><dt>Signature</dt><dd>${esc(fmtBytes(r.signature_bytes))}</dd></div>
        </dl>
      </article>
      <div class="btn-row" style="margin-top:26px">
        <a class="btn btn-primary" href="#/verify?code=${encodeURIComponent(code)}">Verify on the bulletin board</a>
        <button class="btn btn-ghost" type="button" data-copy>Copy receipt code</button>
        <button class="btn btn-ghost" type="button" data-dl>Download receipt</button>
      </div>`;
    panel.querySelector("[data-copy]").addEventListener("click", async () => {
      const ok = await copyText(code);
      toast(ok ? "Receipt code copied" : "Couldn't copy. Select the code and copy it manually.", ok ? "ok" : "error");
    });
    panel.querySelector("[data-dl]").addEventListener("click", () => {
      downloadJSON(`quantumvote-receipt-${r.seq}.json`, r);
      toast("Receipt downloaded", "ok");
    });
  }

  drawStepper();
  try {
    state.election = await get("/election");
  } catch (err) {
    if (!alive) return () => {};
    panel.innerHTML = err.status === 404
      ? `<h2>No election is running</h2><p class="muted" style="margin-top:8px">An administrator needs to create and open an election before anyone can vote.</p><div class="btn-row" style="margin-top:22px"><a class="btn btn-ghost" href="#/admin">Open the Admin console</a></div>`
      : `<h2>The ballot couldn't load</h2><p class="muted" style="margin-top:8px">${esc(err.message)}</p><div class="btn-row" style="margin-top:22px"><button class="btn btn-ghost" type="button" data-retry>Try again</button></div>`;
    panel.querySelector("[data-retry]")?.addEventListener("click", () => location.reload());
    return () => { alive = false; };
  }
  if (!alive) return () => {};
  go(state.step);
  return () => { alive = false; };
}
