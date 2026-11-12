import { get } from "../api.js";
import { esc, statusPill, fmtPct, shortHex, skeletonLines } from "../util.js";
import { mountLattice } from "../lattice.js";

export async function render(root) {
  root.innerHTML = `
  <section class="hero">
    <canvas class="hero-canvas" aria-hidden="true"></canvas>
    <div class="hero-inner">
      <div>
        <h1>Elections that stay secret after quantum computers arrive.</h1>
        <p class="hero-lede">QuantumVote seals every ballot with ML-KEM-768 and signs every receipt with ML-DSA-65, the post-quantum standards NIST published in 2024. Voters stay anonymous, and anyone can check the count.</p>
        <div class="btn-row">
          <a class="btn btn-primary" href="#/vote">Cast your vote</a>
          <a class="btn btn-ghost" href="#/bulletin">See the public ballot board</a>
        </div>
        <div class="hero-standards">
          <span><i></i><b>FIPS 203</b> ML-KEM key encapsulation</span>
          <span><i></i><b>FIPS 204</b> ML-DSA digital signatures</span>
        </div>
      </div>
      <aside class="status-card" aria-live="polite" data-status>
        ${skeletonLines(5)}
      </aside>
    </div>
  </section>

  <div class="page" style="padding-top:64px">
    <section aria-labelledby="how-title">
      <div class="section-head">
        <div>
          <h2 id="how-title">How a ballot travels</h2>
          <p>Four steps from login to proof. Your identity is checked at the start and then cut away from the ballot.</p>
        </div>
      </div>
      <ol class="flow">
        <li>
          <span class="flow-num">1</span>
          <h3>Prove you can vote</h3>
          <p>Sign in with your voter ID. The authority checks you against the electoral roll.</p>
          <span class="algo-tag">scrypt password check</span>
        </li>
        <li>
          <span class="flow-num">2</span>
          <h3>Get an anonymous credential</h3>
          <p>You receive one random, single-use credential. It isn't tied to your name, so the ballot box never learns who you are.</p>
          <span class="algo-tag">SHA3-256 fingerprint</span>
        </li>
        <li>
          <span class="flow-num">3</span>
          <h3>Encrypt and cast</h3>
          <p>Your choice is sealed with a fresh key from ML-KEM-768 and encrypted with AES-256-GCM, then appended to the public chain.</p>
          <span class="algo-tag">ML-KEM-768 + AES-256-GCM</span>
        </li>
        <li>
          <span class="flow-num">4</span>
          <h3>Verify your receipt</h3>
          <p>You get a receipt signed with ML-DSA-65. Look it up on the bulletin board any time to confirm your ballot was counted.</p>
          <span class="algo-tag">ML-DSA-65 signature</span>
        </li>
      </ol>
    </section>

    <section class="section" aria-labelledby="prims-title">
      <div class="section-head">
        <div>
          <h2 id="prims-title">The cryptography inside</h2>
          <p>Two post-quantum standards protect secrecy and authenticity. Two classical primitives that quantum computers only weaken, not break, do the rest.</p>
        </div>
      </div>
      <div class="spec">
        <div class="spec-item pq">
          <div class="spec-name"><h3>ML-KEM-768</h3><span class="spec-std">NIST FIPS 203, lattice based</span></div>
          <p>Key encapsulation built on the Module Learning With Errors problem. Each ballot gets its own shared secret that only the election authority can recover.</p>
          <div class="spec-facts"><span>Public key <b>1,184 B</b></span><span>Ciphertext <b>1,088 B</b></span><span>Security <b>category 3</b></span></div>
        </div>
        <div class="spec-item pq">
          <div class="spec-name"><h3>ML-DSA-65</h3><span class="spec-std">NIST FIPS 204, lattice based</span></div>
          <p>Digital signatures on the election manifest, every voter receipt, the final bulletin-board head and the published result. Forged results fail verification.</p>
          <div class="spec-facts"><span>Public key <b>1,952 B</b></span><span>Signature <b>3,309 B</b></span><span>Security <b>category 3</b></span></div>
        </div>
        <div class="spec-item sym">
          <div class="spec-name"><h3>AES-256-GCM</h3><span class="spec-std">Authenticated encryption</span></div>
          <p>Encrypts the ballot itself with the key derived from ML-KEM. Changing a single bit of a stored ballot makes decryption fail at tally time.</p>
          <div class="spec-facts"><span>Key <b>256 bit</b></span><span>Grover leaves <b>128-bit</b> strength</span></div>
        </div>
        <div class="spec-item sym">
          <div class="spec-name"><h3>SHA3-256 chain</h3><span class="spec-std">NIST FIPS 202</span></div>
          <p>Each bulletin-board entry includes the hash of the one before it. Deleting, inserting or editing any ballot breaks every link after it.</p>
          <div class="spec-facts"><span>Digest <b>32 B</b></span><span>Collision <b>128-bit</b> post-quantum</span></div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="lab-teaser">
        <div>
          <h2>Watch a legacy RSA ballot get broken</h2>
          <p>The Quantum Lab runs the steps of Shor's algorithm against a ballot from an RSA-based system and recovers the vote, then shows why the ML-KEM ballot holds. It also benchmarks both families live on this server.</p>
        </div>
        <a class="btn btn-quantum" href="#/lab">Open the Quantum Lab</a>
      </div>
    </section>
  </div>`;

  const stop = mountLattice(root.querySelector(".hero-canvas"));
  const card = root.querySelector("[data-status]");

  try {
    const el = await get("/election");
    if (!card.isConnected) return stop;
    const s = el.stats || {};
    const a = el.authority || {};
    const turnout = Number(s.turnout) || 0;
    const cta = el.status === "open"
      ? `<a class="btn btn-primary" href="#/vote" style="width:100%;margin-top:20px">Vote in this election</a>`
      : el.status === "tallied"
        ? `<a class="btn btn-primary" href="#/results" style="width:100%;margin-top:20px">See the signed results</a>`
        : `<a class="btn btn-ghost" href="#/bulletin" style="width:100%;margin-top:20px">Open the bulletin board</a>`;
    card.innerHTML = `
      <div class="status-card-top">
        <div>
          <div class="status-card-label">Current election</div>
          <h2>${esc(el.title)}</h2>
        </div>
        ${statusPill(el.status)}
      </div>
      <div class="turnout">
        <div class="turnout-top">
          <span class="turnout-value">${esc(fmtPct(turnout))}</span>
          <span class="muted" style="font-size:var(--fs-sm)">turnout</span>
        </div>
        <div class="turnout-bar" role="img" aria-label="Turnout ${esc(fmtPct(turnout))}"><span style="width:0%"></span></div>
      </div>
      <dl class="status-stats">
        <div><dt>Registered</dt><dd>${esc(s.registered ?? 0)}</dd></div>
        <div><dt>Credentials</dt><dd>${esc(s.credentials_issued ?? 0)}</dd></div>
        <div><dt>Ballots</dt><dd>${esc(s.ballots_cast ?? 0)}</dd></div>
      </dl>
      <div class="status-keys">
        <div><span>${esc(a.kem_alg || "ML-KEM-768")} key</span><span class="mono">${esc(shortHex(a.kem_public_key_fingerprint, 8, 6))}</span></div>
        <div><span>${esc(a.sig_alg || "ML-DSA-65")} key</span><span class="mono">${esc(shortHex(a.sig_public_key_fingerprint, 8, 6))}</span></div>
        <div><span>Signed manifest</span><span>${a.manifest_signature_valid === true ? '<span class="pill pill-good">Verified</span>' : a.manifest_signature_valid === false ? '<span class="pill pill-bad">Invalid</span>' : "—"}</span></div>
      </div>
      ${cta}`;
    requestAnimationFrame(() => {
      const bar = card.querySelector(".turnout-bar span");
      if (bar) bar.style.width = `${Math.min(100, Math.max(0, turnout * 100)).toFixed(1)}%`;
    });
  } catch (err) {
    if (!card.isConnected) return stop;
    card.innerHTML = err.status === 404
      ? `<div class="status-card-label">Current election</div>
         <h2 style="margin-top:4px">No election yet</h2>
         <p class="muted" style="margin-top:10px">An administrator creates the election and its post-quantum keys in the Admin console.</p>
         <a class="btn btn-ghost" href="#/admin" style="width:100%;margin-top:20px">Open the Admin console</a>`
      : `<div class="status-card-label">Current election</div>
         <h2 style="margin-top:4px">Status unavailable</h2>
         <p class="muted" style="margin-top:10px">${esc(err.message)}</p>`;
  }
  return stop;
}
