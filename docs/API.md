# QuantumVote API

The backend is FastAPI and serves the web app at `/` and the JSON API under `/api`. Locally it runs at `http://localhost:8000`.

## Conventions

- Errors return HTTP 4xx with `{"detail": "readable message"}`.
- Authenticated routes need the header `Authorization: Bearer <token>`.
- Hex strings are lowercase.
- Times are ISO-8601 UTC strings.

## Election lifecycle

`setup` → `open` → `closed` → `tallied`

There is one active election at a time.

## Public

### `GET /api/election`

```json
{
  "id": "el_3f2a…",
  "title": "Student Council Election 2026",
  "description": "…",
  "status": "open",
  "candidates": [{"id": "c1", "name": "Aarav Mehta", "party": "Innovation Front", "color": "#22d3ee"}],
  "created_at": "…", "opened_at": "…|null", "closed_at": "…|null", "tallied_at": "…|null",
  "stats": {"registered": 30, "credentials_issued": 12, "ballots_cast": 12, "turnout": 0.4},
  "authority": {
    "kem_alg": "ML-KEM-768", "sig_alg": "ML-DSA-65",
    "kem_public_key_fingerprint": "ab12…(64 hex)", "sig_public_key_fingerprint": "…",
    "kem_public_key_bytes": 1184, "sig_public_key_bytes": 1952,
    "manifest_signature_valid": true
  }
}
```

Returns 404 if no election exists.

### `GET /api/bulletin?limit=50&offset=0`

Returns entries newest first.

```json
{
  "entries": [{
    "seq": 1, "entry_hash": "…64 hex", "prev_hash": "…64 hex",
    "kem_ciphertext_preview": "first 32 hex chars", "ciphertext_preview": "first 32 hex chars",
    "kem_ciphertext_bytes": 1088, "ciphertext_bytes": 110, "cast_at": "…"
  }],
  "total": 12, "head_hash": "…", "genesis_hash": "…",
  "chain_valid": true,
  "head_signature_valid": true
}
```

`head_signature_valid` is null while the election is open. Once it is closed, the authority signs the final head.

### `GET /api/results`

Before tallying:

```json
{"status": "open", "sealed": true}
```

After tallying:

```json
{
  "status": "tallied", "sealed": false,
  "counts": [{"candidate_id": "c1", "name": "…", "party": "…", "color": "#…", "votes": 5, "percent": 41.7}],
  "total_valid": 12, "invalid": 0, "winners": ["c1"],
  "tallied_at": "…", "bulletin_head": "…",
  "signature_valid": true, "signature_preview": "first 48 hex", "signature_bytes": 3309
}
```

### `POST /api/verify/receipt`

Request: `{"receipt_code": "<entry_hash hex, spaces/dashes allowed>"}`

```json
{
  "found": true, "seq": 4, "entry_hash": "…", "cast_at": "…",
  "receipt_signature_valid": true, "chain_valid": true,
  "included_in_final_head": true
}
```

`included_in_final_head` is null while the election is open. If the receipt isn't found, the response is `{"found": false}`.

### `GET /api/audit`

```json
{
  "all_passed": true,
  "checks": [{"id": "manifest", "label": "Election manifest signed by authority (ML-DSA-65)", "passed": true, "detail": "…"}]
}
```

The check ids are:
- `manifest`
- `chain`
- `ballot_integrity`
- `receipts`
- `head_signature`
- `count_consistency`
- `results_signature`

A check that can't be evaluated yet has `passed: null`.

### `GET /api/lab/benchmark`

These are real timings, measured live on the server.

```json
{
  "rows": [{"scheme": "ML-KEM-768", "family": "post-quantum", "operation": "Key generation", "ms": 7.9}],
  "sizes": [{"scheme": "ML-KEM-768", "family": "post-quantum", "purpose": "Key exchange", "public_key": 1184, "ciphertext_or_signature": 1088, "quantum_safe": true}],
  "note": "…"
}
```

The schemes are:
- ML-KEM-768
- ML-DSA-65
- RSA-2048 (OAEP and PSS)
- ECDSA P-256 / ECDH X25519

### `POST /api/lab/shor`

Request: `{}` or `{"vote": "c2"}`

This is a toy RSA-encrypted ballot from a legacy system. The response shows it being broken by the steps of Shor's algorithm. The quantum period-finding step is simulated classically.

```json
{
  "rsa": {"p": 61, "q": 53, "n": 3233, "e": 17},
  "vote": {"candidate_id": "c2", "name": "…", "plaintext_int": 2, "ciphertext_int": 2100},
  "steps": [{"title": "Pick a random base", "detail": "a = 7, gcd(7, 3233) = 1"}],
  "recovered": {"p": 61, "q": 53, "phi": 3120, "d": 2753},
  "decrypted": {"plaintext_int": 2, "candidate_id": "c2", "name": "…"},
  "success": true,
  "pqc_comparison": "…plain-language note on why ML-KEM is not broken by Shor…"
}
```

## Voter

### `POST /api/voter/login`

Request: `{"voter_id": "V001", "password": "…"}`

Response:

```json
{"token": "…", "voter": {"voter_id": "V001", "name": "…", "credential_issued": false}}
```

### `POST /api/voter/credential` (needs the voter token)

This returns a one-time anonymous ballot credential, issued once per voter. After this point the server cannot link the credential to the voter.

```json
{"credential": "64 hex", "credential_fingerprint": "first 16 hex of SHA3-256(credential)"}
```

The request fails with 409 if a credential was already issued, and 400 if the election is not open.

### `POST /api/voter/cast` (no voter token; only the anonymous credential)

Request: `{"credential": "64 hex", "candidate_id": "c2"}`

```json
{
  "receipt": {
    "election_id": "…", "seq": 13, "receipt_code": "64 hex (= entry_hash)", "cast_at": "…",
    "sig_alg": "ML-DSA-65", "authority_signature": "hex", "signature_bytes": 3309
  },
  "crypto_trace": [
    {"step": "ML-KEM-768 encapsulation", "detail": "…", "ms": 3.1, "bytes": 1088},
    {"step": "HKDF-SHA3-256 key derivation", "detail": "…", "ms": 0.1},
    {"step": "AES-256-GCM encryption", "detail": "…", "ms": 0.1, "bytes": 110},
    {"step": "Hash-chain append (SHA3-256)", "detail": "…", "ms": 0.1},
    {"step": "Receipt signed (ML-DSA-65)", "detail": "…", "ms": 40.2, "bytes": 3309}
  ]
}
```

The request fails with 403 for an invalid or used credential, 400 for an unknown candidate or an election that is not open.

## Admin

The demo admin password is `quantum-admin`, or whatever the `QVOTE_ADMIN_PASSWORD` environment variable is set to.

- `POST /api/admin/login` takes `{"password"}` and returns `{"token"}`.
- `POST /api/admin/election` takes `{"title", "description", "candidates": [{"name", "party"}]}`. It creates a new election with fresh authority keys, replacing the current one, and returns the election object.
- `POST /api/admin/election/open`, `/close` and `/tally` each return the election object, or results for `/tally`.
- `GET /api/admin/voters` returns `{"voters": [{"voter_id", "name", "credential_issued", "demo_password"}]}`.
- `POST /api/admin/voters` takes `{"names": ["…"]}` and returns the created voters with their demo passwords.
- `GET /api/admin/keys` returns the algorithms, fingerprints, sizes and public-key hex previews. Secret keys are never returned.
- `POST /api/admin/simulate` takes `{"count": 10}`. It casts that many random ballots through the full voter flow (login, credential, cast) using voters who haven't voted. It returns `{"cast": n}`.
- `POST /api/admin/attack` takes `{"kind": "modify_ballot" | "delete_ballot" | "inject_ballot" | "forge_result"}` and returns `{"applied": true, "description": "…"}`.
- `POST /api/admin/attack/restore` undoes all attacks and returns `{"restored": true}`.
- `POST /api/admin/reset-demo` recreates the demo election with 4 candidates and 30 voters, and returns the election object.

Demo voters are `V001`–`V030`, and each password is `qv-` followed by the voter number (for example, `qv-001`).
