import { esc } from "./util.js";

const routes = {
  "": () => import("./views/home.js"),
  vote: () => import("./views/vote.js"),
  bulletin: () => import("./views/bulletin.js"),
  verify: () => import("./views/verify.js"),
  results: () => import("./views/results.js"),
  lab: () => import("./views/lab.js"),
  admin: () => import("./views/admin.js"),
};

const TITLES = {
  "": "QuantumVote",
  vote: "Vote · QuantumVote",
  bulletin: "Bulletin board · QuantumVote",
  verify: "Verify · QuantumVote",
  results: "Results · QuantumVote",
  lab: "Quantum Lab · QuantumVote",
  admin: "Admin · QuantumVote",
};

const main = document.getElementById("main");
const nav = document.getElementById("primary-nav");
const toggle = document.querySelector(".menu-toggle");
let cleanup = null;
let renderId = 0;

export function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const name = path.split("/")[0] || "";
  return { name, params: new URLSearchParams(query) };
}

export function navigate(hash) {
  if (location.hash === hash) render();
  else location.hash = hash;
}

function setActive(name) {
  nav.querySelectorAll("a[data-route]").forEach((a) => {
    if (a.dataset.route === name) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

function closeMenu() {
  nav.classList.remove("open");
  toggle.setAttribute("aria-expanded", "false");
}

async function render() {
  const id = ++renderId;
  const { name, params } = parseHash();
  const loader = routes[name];
  if (typeof cleanup === "function") {
    try { cleanup(); } catch { /* ignore */ }
  }
  cleanup = null;
  closeMenu();
  setActive(loader ? name : null);
  document.title = TITLES[name] || "QuantumVote";

  if (!loader) {
    main.innerHTML = `<div class="page"><div class="state">
      <h3>There's no page at this address</h3>
      <p>The link may be mistyped. Use the menu above, or go back to the start.</p>
      <a class="btn btn-primary" href="#/">Go to the home page</a>
    </div></div>`;
    return;
  }

  try {
    const mod = await loader();
    if (id !== renderId) return;
    main.innerHTML = "";
    const result = await mod.render(main, params);
    if (id !== renderId) {
      if (typeof result === "function") result();
      return;
    }
    cleanup = typeof result === "function" ? result : null;
  } catch (err) {
    if (id !== renderId) return;
    main.innerHTML = `<div class="page"><div class="state">
      <h3>This page couldn't load</h3>
      <p>${esc(err && err.message ? err.message : String(err))}</p>
      <button class="btn btn-ghost" type="button" data-reload>Try again</button>
    </div></div>`;
    main.querySelector("[data-reload]")?.addEventListener("click", render);
  }
  if (id === renderId) {
    window.scrollTo({ top: 0 });
    main.focus({ preventScroll: true });
  }
}

toggle.addEventListener("click", () => {
  const open = !nav.classList.contains("open");
  nav.classList.toggle("open", open);
  toggle.setAttribute("aria-expanded", String(open));
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && nav.classList.contains("open")) {
    closeMenu();
    toggle.focus();
  }
});

window.addEventListener("hashchange", render);
render();
