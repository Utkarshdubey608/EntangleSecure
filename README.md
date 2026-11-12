# QuantumVote: Safe E-Voting Using Post-Quantum Cryptography

QuantumVote is a complete e-voting system protected with the NIST post-quantum standards:

- **ML-KEM-768** (FIPS 203) for ballot encryption.
- **ML-DSA-65** (FIPS 204) for signatures.

A voter signs in and receives an anonymous one-time credential. They cast a ballot encrypted to the election authority and get a signed receipt. Anyone can check that receipt on a public, hash-chained bulletin board. The authority publishes a signed tally, and a public audit catches any tampering.

## Why post-quantum?

Today's e-voting and web security rely on RSA and elliptic curves. Shor's algorithm breaks both on a large quantum computer. Encrypted ballots recorded today could be decrypted years later ("harvest now, decrypt later"), which would expose how people voted. QuantumVote uses lattice-based schemes that have no known efficient quantum attack. The Quantum Lab page demonstrates the difference live.

## Features

| Page | What it shows |
|---|---|
| **Home** | Live election status, how the protocol works, the algorithms used |
| **Vote** | Five-step flow: sign in → anonymous credential → choose candidate → encrypt and cast (live crypto trace with timings) → signed receipt |
| **Bulletin board** | Every encrypted ballot as a SHA3-256 hash chain, with chain-integrity status |
| **Verify** | Check your receipt, or run the full public audit (7 checks) |
| **Results** | Sealed until the tally, then a chart of the signed result |
| **Quantum Lab** | Live benchmark of PQC vs RSA/ECC, plus Shor's algorithm breaking a legacy RSA ballot step by step |
| **Admin** | Election lifecycle (open → close → tally), create elections, voter roll, authority keys, vote simulator, **attack simulator** |

## Cryptographic design

| Purpose | Mechanism |
|---|---|
| Ballot encryption | ML-KEM-768 encapsulation → HKDF-SHA3-256 → AES-256-GCM (KEM-DEM hybrid). The election ID is bound as associated data. |
| Authority signatures | ML-DSA-65 signs the election manifest, every receipt, the final bulletin head at closing, and the result. |
| Bulletin board | Append-only SHA3-256 hash chain from a genesis hash derived from the signed manifest. |
| One person, one vote | One credential per voter, single use, enforced in a database transaction. |
| Anonymity | Credentials are stored only as SHA3-256 hashes, with no voter ID. Ballots carry no voter ID. |
| Passwords | scrypt (N=2¹⁴, r=8, p=1) with per-voter salt. |

### What the public audit detects

| Attack (in the Admin attack simulator) | Checks that fail |
|---|---|
| Flip one bit of an encrypted ballot | Ballot integrity (and the tally rejects it via the AES-GCM tag) |
| Delete a ballot | Hash chain, sealed head, count consistency, result signature |
| Stuff a forged ballot | Receipt signature, sealed head, count consistency, result signature |
| Rewrite the published result | Result signature |

## Run it locally

You need Python 3.11 or newer.

```bash
python3.12 -m venv .venv            # or: uv venv --python 3.12 .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn qvote.api:app --port 8000
```

Then open http://localhost:8000. The interactive API docs are at http://localhost:8000/api/docs.

Demo logins:
- **Admin:** password `quantum-admin` (override it with `QVOTE_ADMIN_PASSWORD`).
- **Voters:** `V001`–`V030`, each with password `qv-` followed by the number (`V001` → `qv-001`).

Run the tests with `.venv/bin/python -m pytest`.

## Presentation script (about 8 minutes)

1. **Home:** explain the problem (Shor breaks RSA) and the four-step flow.
2. **Quantum Lab:** run Shor's attack on a legacy RSA ballot, then show the PQC benchmark and key sizes.
3. **Vote** as `V001`: show the anonymous credential, then the live encryption trace (ML-KEM → HKDF → AES-GCM → hash chain → ML-DSA receipt). Download the receipt.
4. **Vote again** as `V001`: it is refused, showing one person, one vote.
5. **Admin → Simulate 15 votes.** Then **Bulletin board** shows the chain growing.
6. **Verify:** paste the receipt; it is found and signed.
7. **Admin → Close → Tally.** **Results** shows the signed outcome.
8. **Admin → Attack simulator:** tamper with a ballot or forge the result. The audit flags exactly which checks fail. Then **Restore**.

## Deploy on Vercel

1. Push the repository to GitHub.
2. In Vercel, choose **Add New → Project**, import the repo, and deploy. `vercel.json` serves `web/` as static files and routes `/api/*` to the Python function in `api/index.py`.
3. Optionally set `QVOTE_ADMIN_PASSWORD` in the project's environment variables.

On Vercel the database lives in `/tmp`. Serverless instances are short-lived, so the demo election resets when an instance restarts and isn't shared between instances. That's fine for a demo. A real deployment would use a hosted database such as Postgres.

## Honest limitations

- **Server-side encryption:** ballots are encrypted on the server for this demo. A production system would encrypt in the voter's browser, so the server never sees the plaintext choice.
- **Anonymity relies on trust:** anonymity depends on the credential issuer not logging which voter received which credential. Real systems remove this trust with blind signatures or mix-nets.
- **Single authority key:** one authority holds the decryption key. Production systems split it between trustees (threshold decryption), so no single party can decrypt early.
- **Pure-Python PQC:** ML-KEM and ML-DSA run as pure-Python implementations (`kyber-py`, `dilithium-py`). They are correct, but slower than optimised C, and they are not hardened against side-channel attacks.
- **Shor simulation:** in the Shor demo, the quantum period-finding step is simulated classically on a deliberately tiny RSA key.

## Project layout

```
qvote/            backend: crypto (pqc, shor, passwords), service, storage, benchmark, FastAPI app
web/              frontend: no-build single-page app (HTML, CSS, ES modules)
api/index.py      Vercel entry point
tests/            pytest suite: crypto, service, attacks, HTTP API
docs/API.md       API reference
archive/          the earlier E91 QKD simulation project
```
