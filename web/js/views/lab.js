import { get, post } from "../api.js";
import { esc, icons, callout, fmtMs, sleep, busy, skeletonLines, errorState } from "../util.js";
import { mountLattice } from "../lattice.js";

const PQ_COLOR = "#A586FF";
const CL_COLOR = "#93A3C2";

export async function render(root) {
  let alive = true;
  root.innerHTML = `
  <div class="page">
    <header class="page-head">
      <h1>Quantum Lab</h1>
      <p>Two experiments that show why QuantumVote uses post-quantum cryptography: a live speed and size comparison against today's classical algorithms, and a quantum attack on a ballot protected by RSA.</p>
    </header>

    <section aria-labelledby="attack-title">
      <div class="section-head">
        <div>
          <h2 id="attack-title">Shor's attack on a legacy RSA ballot</h2>
          <p>A ballot from an older system was encrypted with RSA. Shor's algorithm factors the RSA modulus, which gives away the private key. The toy key here is small so every step fits on screen; a real quantum computer would do the same to RSA-2048.</p>
        </div>
      </div>
      <div class="attack-grid">
        <article class="panel legacy" data-legacy>
          <h3>Legacy ballot, RSA</h3>
          <p class="muted">Encrypted as c = m<sup>e</sup> mod n. Its security rests only on n being hard to factor.</p>
          <div data-rsa>${skeletonLines(2, ["70%", "50%"])}</div>
          <div class="btn-row" style="margin-top:6px"><button class="btn btn-danger" type="button" data-attack>Run Shor's attack</button></div>
          <ol class="shor-steps" data-steps></ol>
          <div data-broken></div>
        </article>
        <article class="panel safe-card">
          <h3>QuantumVote ballot, ML-KEM-768</h3>
          <span class="safe-badge">${icons.shield} No known quantum attack</span>
          <canvas class="lattice-mini" aria-hidden="true"></canvas>
          <p class="muted" data-pqc>Security comes from finding short vectors in a high-dimensional lattice like the one above. Shor's algorithm finds periods, and a lattice problem has no period to find.</p>
        </article>
      </div>
    </section>

    <section class="section" aria-labelledby="bench-title">
      <div class="section-head">
        <div>
          <h2 id="bench-title">Live benchmark</h2>
          <p>Each operation is timed on this server right now. Post-quantum keys and signatures are larger, and that's the price of surviving a quantum computer.</p>
        </div>
        <button class="btn btn-ghost" type="button" data-rerun>Run the benchmark again</button>
      </div>
      <div data-bench><div class="panel">${skeletonLines(6)}</div></div>
    </section>
  </div>`;

  const stopLattice = mountLattice(root.querySelector(".lattice-mini"), { density: 1.6, highlight: true });

  // ------------------------------------------------------------ Shor demo
  const rsaBox = root.querySelector("[data-rsa]");
  const stepsBox = root.querySelector("[data-steps]");
  const brokenBox = root.querySelector("[data-broken]");
  const attackBtn = root.querySelector("[data-attack]");
  rsaBox.innerHTML = `<p class="faint" style="font-size:var(--fs-sm);margin:14px 0">Run the attack to generate a legacy key and an encrypted vote.</p>`;

  attackBtn.addEventListener("click", async () => {
    stepsBox.innerHTML = "";
    brokenBox.innerHTML = "";
    let d;
    try {
      d = await busy(attackBtn, "Running…", () => post("/lab/shor", {}));
    } catch (err) {
      if (alive) brokenBox.innerHTML = "<br>" + callout("error", esc(err.message));
      return;
    }
    if (!alive) return;
    attackBtn.disabled = true;
    const rsa = d.rsa || {};
    const vote = d.vote || {};
    rsaBox.innerHTML = `
      <dl class="rsa-params">
        <div><dt>Modulus n</dt><dd>${esc(rsa.n)}</dd></div>
        <div><dt>Public exponent e</dt><dd>${esc(rsa.e)}</dd></div>
        <div><dt>Ciphertext c</dt><dd>${esc(vote.ciphertext_int)}</dd></div>
        <div><dt>Plaintext</dt><dd>hidden</dd></div>
      </dl>`;
    for (const s of d.steps || []) {
      if (!alive) return;
      stepsBox.insertAdjacentHTML("beforeend", `<li><div><b>${esc(s.title)}</b><span>${esc(s.detail)}</span></div></li>`);
      await sleep(520);
    }
    if (!alive) return;
    const rec = d.recovered || {};
    const dec = d.decrypted || {};
    brokenBox.innerHTML = d.success
      ? `<div class="broken" role="alert">
          <span class="broken-stamp">BROKEN</span>
          <h4>The vote was recovered: ${esc(dec.name || dec.candidate_id)}</h4>
          <p class="muted" style="font-size:var(--fs-sm)">With p and q known, the private key d follows immediately, and anyone can decrypt every ballot ever encrypted to this key.</p>
          <dl class="rsa-params">
            <div><dt>p</dt><dd>${esc(rec.p)}</dd></div>
            <div><dt>q</dt><dd>${esc(rec.q)}</dd></div>
            <div><dt>φ(n)</dt><dd>${esc(rec.phi)}</dd></div>
            <div><dt>Private key d</dt><dd>${esc(rec.d)}</dd></div>
          </dl>
        </div>`
      : callout("warn", "This run didn't recover the key. Shor's algorithm is probabilistic; run it again to pick a different base.");
    rsaBox.querySelector("dl div:last-child dd").textContent = d.success ? `m = ${dec.plaintext_int}` : "hidden";
    if (d.pqc_comparison) root.querySelector("[data-pqc]").textContent = d.pqc_comparison;
    attackBtn.disabled = false;
    attackBtn.textContent = "Run the attack again";
  });

  // ------------------------------------------------------------ benchmark
  const benchBox = root.querySelector("[data-bench]");
  const rerun = root.querySelector("[data-rerun]");

  function drawBench(b) {
    const rows = b.rows || [];
    const sizes = b.sizes || [];
    const order = [];
    const byScheme = new Map();
    rows.forEach((r) => {
      if (!byScheme.has(r.scheme)) { byScheme.set(r.scheme, []); order.push(r.scheme); }
      byScheme.get(r.scheme).push(r);
    });
    const maxMs = Math.max(...rows.map((r) => Number(r.ms) || 0), 0.001);
    const minMs = Math.max(Math.min(...rows.map((r) => Number(r.ms) || maxMs)), 0.001);
    // Log scale: operations span several orders of magnitude.
    const lo = Math.log10(minMs) - 0.3;
    const hi = Math.log10(maxMs);
    const width = (ms) => Math.max(2, ((Math.log10(Math.max(ms, 0.0001)) - lo) / Math.max(hi - lo, 0.001)) * 100);
    const maxSize = Math.max(...sizes.map((s) => Math.max(Number(s.public_key) || 0, Number(s.ciphertext_or_signature) || 0)), 1);

    benchBox.innerHTML = `
      <div class="bench-layout">
        <section class="panel">
          <h3>Time per operation</h3>
          <div class="legend" style="margin:6px 0 18px">
            <span><i style="background:${PQ_COLOR}"></i>Post-quantum</span>
            <span><i style="background:${CL_COLOR}"></i>Classical</span>
            <span>Bar length on a log scale</span>
          </div>
          <div class="bench-chart">
            ${order.map((scheme) => {
              const list = byScheme.get(scheme);
              const pq = list[0].family === "post-quantum";
              const color = pq ? PQ_COLOR : CL_COLOR;
              return `<div class="bench-group">
                <h4><i style="background:${color}"></i>${esc(scheme)}</h4>
                ${list.map((r) => `<div class="bench-line">
                  <span class="op">${esc(r.operation)}</span>
                  <span class="track"><i style="background:${color}" data-w="${width(Number(r.ms)).toFixed(2)}"></i></span>
                  <span class="ms">${esc(fmtMs(r.ms))}</span>
                </div>`).join("")}
              </div>`;
            }).join("")}
          </div>
        </section>
        <section class="panel">
          <h3>Key and output sizes</h3>
          <p class="muted">Bytes that travel with every key exchange or signature.</p>
          <div class="table-wrap" style="margin-top:6px">
            <table class="size-table">
              <thead><tr><th>Scheme</th><th class="num">Public key</th><th class="num">Ciphertext or signature</th><th>Quantum-safe</th></tr></thead>
              <tbody>
                ${sizes.map((s) => {
                  const pq = s.family === "post-quantum";
                  return `<tr>
                    <td><b>${esc(s.scheme)}</b><div class="faint" style="font-size:var(--fs-xs)">${esc(s.purpose || "")}</div></td>
                    <td class="num">${esc(Number(s.public_key).toLocaleString())}<span class="size-bar ${pq ? "" : "classical"}" style="width:${Math.max(3, (Number(s.public_key) / maxSize) * 120).toFixed(1)}px"></span></td>
                    <td class="num">${esc(Number(s.ciphertext_or_signature).toLocaleString())}<span class="size-bar ${pq ? "" : "classical"}" style="width:${Math.max(3, (Number(s.ciphertext_or_signature) / maxSize) * 120).toFixed(1)}px"></span></td>
                    <td>${s.quantum_safe ? '<span class="pill pill-good">Yes</span>' : '<span class="pill pill-bad">No</span>'}</td>
                  </tr>`;
                }).join("")}
              </tbody>
            </table>
          </div>
          ${b.note ? `<div style="margin-top:16px">${callout("info", esc(b.note))}</div>` : ""}
        </section>
      </div>`;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      benchBox.querySelectorAll(".bench-line .track i").forEach((i) => { i.style.width = `${i.dataset.w}%`; });
    }));
  }

  async function loadBench() {
    try {
      const b = await get("/lab/benchmark");
      if (alive) drawBench(b);
    } catch (err) {
      if (!alive) return;
      benchBox.innerHTML = errorState(err);
      benchBox.querySelector("[data-retry]")?.addEventListener("click", () => {
        benchBox.innerHTML = `<div class="panel">${skeletonLines(6)}</div>`;
        loadBench();
      });
    }
  }
  rerun.addEventListener("click", () => busy(rerun, "Measuring…", loadBench));
  loadBench();

  return () => { alive = false; stopLattice(); };
}
