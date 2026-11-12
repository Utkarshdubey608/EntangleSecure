const BASE = "/api";
const TOKEN_KEYS = { voter: "qv_voter_token", admin: "qv_admin_token" };

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function storageSet(key, value) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* storage unavailable: token lives only for this page */ }
}

export const tokens = {
  get: (role) => storageGet(TOKEN_KEYS[role]),
  set: (role, value) => storageSet(TOKEN_KEYS[role], value),
  clear: (role) => storageSet(TOKEN_KEYS[role], null),
};

export async function api(path, { method = "GET", body, auth } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = tokens.get(auth);
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach the QuantumVote server. Check that the backend is running, then try again.", 0);
  }
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = null; }
  }
  if (!res.ok) {
    let detail = data && data.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg || String(d)).join("; ");
    if (typeof detail !== "string" || !detail) detail = `The server returned an error (${res.status}).`;
    if (res.status === 401 && auth) tokens.clear(auth);
    throw new ApiError(detail, res.status);
  }
  return data;
}

export const get = (path, opts) => api(path, { ...opts, method: "GET" });
export const post = (path, body = {}, opts) => api(path, { ...opts, method: "POST", body });
