import { get } from "../api.js";
import { esc, statusLabel, fmtTime, fmtPct, fmtBytes, groupHex, boolPill, candColor, skeletonLines, errorState } from "../util.js";

const LOCK_SVG = `<svg viewBox="0 0 200 200" aria-hidden="true">
  <defs><pattern id="lat" width="20" height="20" patternUnits="userSpaceOnUse" patternTransform="skewX(-16)">
    <circle cx="10" cy="10" r="1.6" fill="#A586FF" opacity=".5"/></pattern></defs>
  <rect x="8" y="8" width="184" height="184" rx="28" fill="url(#lat)" opacity=".7"/>
  <path d="M68 92V70a32 32 0 0 1 64 0v22" fill="none" stroke="#93A3C2" stroke-width="12" stroke-linecap="round"/>
  <rect x="50" y="90" width="100" height="78" rx="16" fill="#16264A" stroke="#A586FF" stroke-width="3"/>
  <circle cx="100" cy="122" r="10" fill="#A586FF"/><rect x="96" y="126" width="8" height="22" rx="4" fill="#A586FF"/>
</svg>`;

export async function render(root) {
  let alive = true;
  root.innerHTML = `
  <div class="page">
    <header class="page-head">
      <h1>Results</h1>
      <p>Ballots stay encrypted until the polls close and the authority runs the tally. The published result is signed, so anyone can check it wasn't changed afterwards.</p>
    </header>
    <div data-body><div class="panel">${skeletonLines(6)}</div></div>
  </div>`;
  const body = root.querySelector("[data-body]");

  async function load() {
    let res;
    let election = null;
    try {
      [res, election] = await Promise.all([get("/results"), get("/election").catch(() => null)]);
    } catch (err) {
      if (!alive) return;
      body.innerHTML = err.status === 404
        ? `<div class="state"><h3>No election yet</h3><p>Results appear here after an election is created, run and tallied.</p><a class="btn btn-ghost" href="#/admin">Open the Admin console</a></div>`
        : errorState(err);
      body.querySelector("[data-retry]")?.addEventListener("click", load);
      return;
    }
    if (!alive) return;

    if (res.sealed || res.status !== "tallied") {
      const s = (election && election.stats) || {};
      body.innerHTML = `
        <section class="panel sealed">
          ${LOCK_SVG}
          <div>
            <h2>Results are sealed</h2>
            <p>The election is <strong>${esc(statusLabel(res.status).toLowerCase())}</strong>. Every ballot is encrypted to the authority's ML-KEM-768 key, and nobody, including the administrator, can see partial results. The tally runs once, after the polls close.</p>
            <dl class="result-meta" style="grid-template-columns:repeat(3,minmax(0,1fr))">
              <div class="metric"><dt>Ballots sealed</dt><dd>${esc(s.ballots_cast ?? "—")}</dd></div>
              <div class="metric"><dt>Registered</dt><dd>${esc(s.registered ?? "—")}</dd></div>
              <div class="metric"><dt>Turnout so far</dt><dd>${esc(fmtPct(s.turnout))}</dd></div>
            </dl>
            <div class="btn-row" style="margin-top:22px">
              ${res.status === "open" ? '<a class="btn btn-primary" href="#/vote">Cast your vote</a>' : ""}
              <a class="btn btn-ghost" href="#/bulletin">See the sealed ballots</a>
            </div>
          </div>
        </section>`;
      return;
    }

    const counts = [...(res.counts || [])];
    if (!counts.length) {
      body.innerHTML = `<div class="state"><h3>No candidates in the result</h3><p>The tally finished but returned no candidate counts.</p></div>`;
      return;
    }
    const candIndex = new Map(((election && election.candidates) || []).map((c, i) => [c.id, i]));
    const colorOf = (c) => candColor(c, candIndex.get(c.candidate_id) ?? counts.indexOf(c));
    const sorted = [...counts].sort((a, b) => b.votes - a.votes);
    const max = Math.max(1, ...counts.map((c) => c.votes));
    const winners = sorted.filter((c) => (res.winners || []).includes(c.candidate_id));
    const lead = winners[0] || sorted[0];
    const tie = winners.length > 1;
    const s = (election && election.stats) || {};

    body.innerHTML = `
      <div class="results-top">
        <section class="winner" style="--cand:${esc(colorOf(lead))}" aria-label="Winner">
          <small>${tie ? "Tie between" : "Winner"}</small>
          <h2>${esc(tie ? winners.map((w) => w.name).join(" and ") : lead.name)}</h2>
          <div class="party">${esc(tie ? "Equal number of votes" : lead.party || "Independent")}</div>
          <div class="winner-votes">
            <div><b>${esc(lead.votes)}</b><span>votes</span></div>
            <div><b>${esc(Number(lead.percent).toFixed(1))}%</b><span>of valid ballots</span></div>
          </div>
        </section>
        <section class="panel" aria-labelledby="dist-title">
          <h3 id="dist-title">Vote distribution</h3>
          <p class="muted">${esc(res.total_valid)} valid ballots decrypted and counted.</p>
          <div class="bars">
            ${sorted.map((c) => `
              <div class="bar-row" style="--cand:${esc(colorOf(c))}">
                <div class="bar-label"><b>${esc(c.name)}</b><span>${esc(c.votes)} ${c.votes === 1 ? "vote" : "votes"}, ${esc(Number(c.percent).toFixed(1))}%</span></div>
                <div class="bar-track" role="img" aria-label="${esc(c.name)}: ${esc(c.votes)} votes"><i data-w="${(c.votes / max) * 100}"></i></div>
              </div>`).join("")}
          </div>
        </section>
      </div>
      <dl class="result-meta">
        <div class="metric"><dt>Valid ballots</dt><dd>${esc(res.total_valid)}</dd></div>
        <div class="metric"><dt>Rejected ballots</dt><dd>${esc(res.invalid)}</dd></div>
        <div class="metric"><dt>Turnout</dt><dd>${esc(fmtPct(s.turnout))}</dd></div>
        <div class="metric"><dt>Tallied</dt><dd style="font-size:var(--fs-sm)">${esc(fmtTime(res.tallied_at))}</dd></div>
      </dl>
      <section class="panel" style="margin-top:20px" aria-labelledby="sig-title">
        <div class="section-head" style="margin-bottom:12px">
          <div><h3 id="sig-title">Signed result</h3><p>The authority signed these counts together with the final bulletin-board head using ML-DSA-65.</p></div>
          ${boolPill(res.signature_valid, { yes: "Signature valid", no: "Signature invalid", pending: "Unsigned" })}
        </div>
        ${res.signature_valid === false ? `<div class="callout callout-error" style="margin-bottom:14px"><div>The published result doesn't match its signature. Someone changed the numbers after the tally.</div></div>` : ""}
        <dl class="keys-list">
          <div class="key-item"><dt>Bulletin-board head committed to</dt><dd class="hash">${esc(groupHex(res.bulletin_head))}</dd></div>
          <div class="key-item"><dt>Signature (${esc(fmtBytes(res.signature_bytes))})</dt><dd class="hash hash-muted">${esc(res.signature_preview || "")}…</dd></div>
        </dl>
        <div class="btn-row" style="margin-top:18px"><a class="btn btn-ghost" href="#/verify">Audit the whole election</a></div>
      </section>`;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      body.querySelectorAll(".bar-track i").forEach((i) => { i.style.width = `${Number(i.dataset.w).toFixed(2)}%`; });
    }));
  }
  await load();
  return () => { alive = false; };
}
