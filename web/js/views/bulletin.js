import { get } from "../api.js";
import { esc, groupHex, shortHex, fmtTime, fmtBytes, boolPill, skeletonLines, errorState, busy } from "../util.js";

const PAGE = 20;

export async function render(root) {
  let alive = true;
  let offset = 0;
  let total = 0;
  let loaded = [];
  let genesis = null;

  root.innerHTML = `
  <div class="page">
    <header class="page-head">
      <h1>Public bulletin board</h1>
      <p>Every encrypted ballot, in the order it was cast. Each block stores the hash of the block before it, so editing, removing or slipping in a ballot breaks the chain for everyone to see.</p>
    </header>
    <dl class="board-summary" data-summary>
      ${Array.from({ length: 4 }, () => `<div class="metric">${skeletonLines(2, ["50%", "80%"])}</div>`).join("")}
    </dl>
    <form class="board-tools" data-search role="search">
      <label class="sr-only" for="board-search">Receipt code</label>
      <input class="input mono" id="board-search" placeholder="Paste a receipt code to verify it" autocomplete="off" spellcheck="false">
      <button class="btn btn-ghost" type="submit">Verify receipt</button>
    </form>
    <ol class="chain" data-chain aria-label="Ballot chain, newest first"></ol>
    <div class="board-more" data-more></div>
  </div>`;

  const summary = root.querySelector("[data-summary]");
  const chain = root.querySelector("[data-chain]");
  const more = root.querySelector("[data-more]");

  root.querySelector("[data-search]").addEventListener("submit", (e) => {
    e.preventDefault();
    const code = root.querySelector("#board-search").value.replace(/[\s-]/g, "");
    if (code) location.hash = `#/verify?code=${encodeURIComponent(code)}`;
  });

  function drawSummary(d) {
    summary.innerHTML = `
      <div class="metric"><dt>Ballots on the chain</dt><dd>${esc(d.total)}</dd></div>
      <div class="metric"><dt>Chain integrity</dt><dd>${boolPill(d.chain_valid, { yes: "Every link verified", no: "Chain broken", pending: "Not checked" })}</dd></div>
      <div class="metric"><dt>Signed final head</dt><dd>${boolPill(d.head_signature_valid, { yes: "Signature valid", no: "Signature invalid", pending: "Signed at close" })}</dd></div>
      <div class="metric"><dt>Current head</dt><dd><span class="hash" title="${esc(d.head_hash)}">${esc(shortHex(d.head_hash, 12, 8))}</span></dd></div>`;
  }

  function blockHTML(e) {
    return `<li class="block">
      <div class="block-seq"><b>#${esc(e.seq)}</b><span>${esc(fmtTime(e.cast_at))}</span></div>
      <div class="block-body">
        <div class="block-row"><span>Block hash</span><span class="hash">${esc(groupHex(e.entry_hash))}</span></div>
        <div class="block-row"><span>Previous hash</span><span class="hash hash-muted">${esc(shortHex(e.prev_hash, 16, 8))}</span></div>
        <div class="block-row"><span>Sealed ballot</span>
          <span class="block-cipher">
            <span><b>KEM</b> ${esc(e.kem_ciphertext_preview)}… ${esc(fmtBytes(e.kem_ciphertext_bytes))}</span>
            <span><b>AES-GCM</b> ${esc(e.ciphertext_preview)}… ${esc(fmtBytes(e.ciphertext_bytes))}</span>
          </span>
        </div>
      </div>
    </li>`;
  }

  function linkHTML(newer, older) {
    if (!older) return "";
    const ok = newer.prev_hash === older.entry_hash;
    return `<li class="link ${ok ? "" : "broken"}" aria-label="${ok ? "Link verified" : "Link broken"}">
      <span>${ok ? `#${esc(newer.seq)} points to #${esc(older.seq)}` : `#${esc(newer.seq)} doesn't point to #${esc(older.seq)}`}</span>
    </li>`;
  }

  function drawChain() {
    if (!loaded.length) {
      chain.innerHTML = `<li class="state"><h3>No ballots yet</h3><p>Encrypted ballots appear here the moment they're cast. Nothing on this board reveals who voted or how.</p><a class="btn btn-primary" href="#/vote">Cast the first ballot</a></li>`;
      more.innerHTML = "";
      return;
    }
    let html = "";
    loaded.forEach((e, i) => {
      html += blockHTML(e);
      if (i < loaded.length - 1) html += linkHTML(e, loaded[i + 1]);
    });
    const allLoaded = loaded.length >= total;
    if (allLoaded && genesis) {
      const last = loaded[loaded.length - 1];
      const ok = last.prev_hash === genesis;
      html += `<li class="link ${ok ? "" : "broken"}"><span>${ok ? `#${esc(last.seq)} points to the genesis block` : `#${esc(last.seq)} doesn't point to the genesis block`}</span></li>
        <li class="block genesis">
          <div class="block-seq"><b>#0</b><span>Genesis</span></div>
          <div class="block-body"><div class="block-row"><span>Genesis hash</span><span class="hash">${esc(groupHex(genesis))}</span></div>
          <p class="faint" style="font-size:var(--fs-xs)">Derived from the election manifest. The chain starts here.</p></div>
        </li>`;
    }
    chain.innerHTML = html;
    more.innerHTML = allLoaded ? "" : `<button class="btn btn-ghost" type="button">Load ${Math.min(PAGE, total - loaded.length)} older ballots</button>`;
    more.querySelector("button")?.addEventListener("click", (e) => busy(e.currentTarget, "Loading…", loadPage));
  }

  async function loadPage() {
    const d = await get(`/bulletin?limit=${PAGE}&offset=${offset}`);
    if (!alive) return;
    total = d.total;
    genesis = d.genesis_hash || null;
    loaded = loaded.concat(d.entries || []);
    offset += (d.entries || []).length;
    drawSummary(d);
    drawChain();
  }

  async function first() {
    try {
      await loadPage();
    } catch (err) {
      if (!alive) return;
      summary.innerHTML = "";
      chain.innerHTML = err.status === 404
        ? `<li class="state"><h3>No election yet</h3><p>The bulletin board opens when an administrator creates an election.</p><a class="btn btn-ghost" href="#/admin">Open the Admin console</a></li>`
        : `<li>${errorState(err)}</li>`;
      chain.querySelector("[data-retry]")?.addEventListener("click", () => { chain.innerHTML = ""; first(); });
    }
  }
  await first();
  return () => { alive = false; };
}
