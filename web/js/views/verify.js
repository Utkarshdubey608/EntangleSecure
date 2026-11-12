import { get, post } from "../api.js";
import { esc, icons, checkItem, callout, groupHex, fmtTime, busy } from "../util.js";

export function renderAudit(container, audit, { flashFailures = false } = {}) {
  const checks = audit.checks || [];
  const failed = checks.filter((c) => c.passed === false).length;
  const pending = checks.filter((c) => c.passed == null).length;
  const verdict = audit.all_passed
    ? `<div class="verdict ok">${icons.shield}<div><strong>Every check passed</strong><span>The election record is intact and every signature verifies.</span></div></div>`
    : failed
      ? `<div class="verdict bad">${icons.shieldBad}<div><strong>${failed} ${failed === 1 ? "check failed" : "checks failed"}</strong><span>The record has been altered. The failing checks show what was tampered with.</span></div></div>`
      : `<div class="verdict wait">${icons.clock}<div><strong>No problems found so far</strong><span>${pending} ${pending === 1 ? "check runs" : "checks run"} after the polls close or the tally is published.</span></div></div>`;
  container.innerHTML = `${verdict}<ul class="checklist">${checks.map((c) => checkItem(c)).join("")}</ul>`;
  if (flashFailures) container.querySelectorAll(".check.fail").forEach((el) => el.classList.add("flash"));
}

export async function render(root, params) {
  let alive = true;
  const prefill = (params.get("code") || "").replace(/[^0-9a-f]/gi, "");

  root.innerHTML = `
  <div class="page">
    <header class="page-head">
      <h1>Verify the election</h1>
      <p>Check that your own ballot is on the chain, or audit the whole election. Both checks are public: no login, no trust in the administrator required.</p>
    </header>
    <div class="verify-layout">
      <section class="panel" aria-labelledby="receipt-title">
        <h3 id="receipt-title">Check my receipt</h3>
        <p class="muted">Paste the code from your receipt. Spaces and dashes are fine.</p>
        <form class="form-grid" data-form>
          <div class="field">
            <label for="receipt-code">Receipt code</label>
            <textarea class="textarea input mono" id="receipt-code" rows="3" spellcheck="false" placeholder="a3f1 09bc …">${esc(groupHex(prefill))}</textarea>
          </div>
          <div><button class="btn btn-primary" type="submit">Check receipt</button></div>
        </form>
        <div data-receipt-result></div>
      </section>
      <section class="panel" aria-labelledby="audit-title">
        <h3 id="audit-title">Public audit</h3>
        <p class="muted">Re-verifies the signed manifest, the entire hash chain, every ballot's integrity, every receipt signature and the published result.</p>
        <button class="btn btn-quantum" type="button" data-audit>Run the full audit</button>
        <div data-audit-result></div>
      </section>
    </div>
  </div>`;

  const form = root.querySelector("[data-form]");
  const out = root.querySelector("[data-receipt-result]");

  async function check() {
    const code = form.querySelector("textarea").value.replace(/[\s-]/g, "").toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(code)) {
      out.innerHTML = "<br>" + callout("error", "A receipt code is 64 hexadecimal characters (0–9 and a–f). Check that you copied all of it.");
      return;
    }
    const btn = form.querySelector("button[type=submit]");
    try {
      const r = await busy(btn, "Checking…", () => post("/verify/receipt", { receipt_code: code }));
      if (!alive) return;
      if (!r.found) {
        out.innerHTML = `<div class="verdict bad">${icons.shieldBad}<div><strong>Receipt not on the board</strong><span>No ballot with this code exists in the current election. If you just voted, check the code; if it's correct, your ballot may have been removed, so report it.</span></div></div>`;
        return;
      }
      const good = r.receipt_signature_valid && r.chain_valid && r.included_in_final_head !== false;
      out.innerHTML = `
        <div class="verdict ${good ? "ok" : "bad"}">${good ? icons.shield : icons.shieldBad}
          <div><strong>${good ? `Ballot #${esc(r.seq)} is on the chain` : `Ballot #${esc(r.seq)} failed a check`}</strong>
          <span>Cast ${esc(fmtTime(r.cast_at))}</span></div>
        </div>
        <ul class="checklist">
          ${checkItem({ label: "Found on the public bulletin board", passed: true, detail: `Block #${r.seq}` })}
          ${checkItem({ label: "Receipt signature verifies (ML-DSA-65)", passed: r.receipt_signature_valid, detail: r.receipt_signature_valid ? "The authority really issued this receipt." : "The signature doesn't match. This receipt wasn't issued by the authority, or the block was altered." })}
          ${checkItem({ label: "Hash chain intact", passed: r.chain_valid, detail: r.chain_valid ? "Every block links to the one before it." : "At least one block has been edited, removed or inserted." })}
          ${checkItem({ label: "Included in the signed final head", passed: r.included_in_final_head, detail: r.included_in_final_head == null ? "Checked once the polls close and the authority signs the final chain head." : r.included_in_final_head ? "Your ballot is part of the chain the authority committed to." : "Your ballot isn't covered by the signed final head." })}
        </ul>`;
    } catch (err) {
      if (!alive) return;
      out.innerHTML = "<br>" + callout("error", esc(err.status === 404 ? "There's no election to check against yet." : err.message));
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); check(); });
  form.querySelector("textarea").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); check(); }
  });

  const auditBtn = root.querySelector("[data-audit]");
  const auditOut = root.querySelector("[data-audit-result]");
  auditBtn.addEventListener("click", async () => {
    try {
      const a = await busy(auditBtn, "Auditing…", () => get("/audit"));
      if (alive) renderAudit(auditOut, a, { flashFailures: true });
    } catch (err) {
      if (alive) auditOut.innerHTML = "<br>" + callout("error", esc(err.status === 404 ? "There's no election to audit yet." : err.message));
    }
  });

  if (prefill.length === 64) check();
  return () => { alive = false; };
}
