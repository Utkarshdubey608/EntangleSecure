"""Election domain logic: authority keys, voter roll, anonymous credentials, encrypted
ballots on a hash-chained bulletin board, signed tally, public audit and an attack simulator."""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import re
import secrets
import time
from datetime import datetime, timezone

from .crypto import pqc, shor
from .crypto.passwords import check_password, hash_password
from .storage import Database

PALETTE = ["#22d3ee", "#a78bfa", "#34d399", "#f59e0b", "#f472b6", "#60a5fa", "#fb7185", "#a3e635"]
MAX_CANDIDATES = 8
MAX_VOTERS = 500

DEMO_TITLE = "Student Council Election 2026"
DEMO_DESCRIPTION = "Election of the student council president. Ballots are encrypted with ML-KEM-768 and every receipt is signed with ML-DSA-65."
DEMO_CANDIDATES = [
    {"name": "Aarav Mehta", "party": "Innovation Front"},
    {"name": "Diya Sharma", "party": "Green Campus Alliance"},
    {"name": "Kabir Singh", "party": "Student Voice Party"},
    {"name": "Ananya Iyer", "party": "Independent"},
]
DEMO_VOTERS = [
    "Rohan Gupta", "Priya Nair", "Arjun Reddy", "Sneha Kulkarni", "Vikram Joshi", "Meera Pillai",
    "Aditya Rao", "Isha Banerjee", "Karan Malhotra", "Pooja Desai", "Nikhil Verma", "Riya Kapoor",
    "Siddharth Jain", "Tanvi Shah", "Yash Patil", "Neha Chauhan", "Rahul Bose", "Kavya Menon",
    "Harsh Agarwal", "Simran Kaur", "Manav Sethi", "Aditi Mishra", "Dev Khanna", "Shreya Ghosh",
    "Varun Saxena", "Nandini Das", "Ayaan Qureshi", "Ishita Bhatt", "Omkar Pawar", "Zara Khan",
]
SIMULATION_WEIGHTS = [0.38, 0.27, 0.21, 0.14, 0.1, 0.1, 0.1, 0.1]
ATTACKS = ("modify_ballot", "delete_ballot", "inject_ballot", "forge_result")
PQC_COMPARISON = (
    "ML-KEM's security rests on the Module Learning With Errors lattice problem. Shor's algorithm only works "
    "when the problem hides a periodic structure, as factoring and discrete logarithms do; lattice problems don't, "
    "and no efficient quantum algorithm for them is known. Grover's search gives at most a square-root speed-up "
    "against brute force, which ML-KEM-768's parameters already absorb (NIST security category 3, comparable to AES-192)."
)


class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def entry_hash(eid: str, seq: int, prev_hash: str, kem_ct: bytes, nonce: bytes, ct: bytes, cast_at: str) -> str:
    return pqc.sha3(b"qvote-entry-v1", eid.encode(), seq.to_bytes(8, "big"), bytes.fromhex(prev_hash), kem_ct, nonce, ct, cast_at.encode()).hex()


def receipt_message(eid: str, seq: int, ehash: str) -> bytes:
    return f"qvote-receipt-v1|{eid}|{seq}|{ehash}".encode()


def head_message(eid: str, count: int, head: str) -> bytes:
    return f"qvote-head-v1|{eid}|{count}|{head}".encode()


def results_message(payload: str) -> bytes:
    return b"qvote-results-v1|" + payload.encode()


def credential_hash(credential: str) -> str:
    return hashlib.sha3_256(bytes.fromhex(credential)).hexdigest()


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ElectionService:
    def __init__(self, db: Database, admin_password: str = "quantum-admin"):
        self.db = db
        self.admin_password = admin_password

    # ------------------------------------------------------------------ helpers
    def _active(self):
        row = self.db.one("SELECT * FROM elections WHERE active = 1")
        if row is None:
            raise ServiceError(404, "No election has been created yet.")
        return row

    @staticmethod
    def _candidates(row) -> list[dict]:
        return json.loads(row["candidates_json"])

    @staticmethod
    def _manifest(row) -> bytes:
        return canonical({
            "election_id": row["id"], "title": row["title"], "description": row["description"],
            "candidates": json.loads(row["candidates_json"]), "created_at": row["created_at"],
            "kem_alg": pqc.KEM_ALG, "sig_alg": pqc.SIG_ALG,
            "kem_public_key": pqc.fingerprint(row["kem_pk"]), "sig_public_key": pqc.fingerprint(row["sig_pk"]),
        })

    def _session(self, token: str | None, kind: str):
        if not token:
            raise ServiceError(401, "Please sign in first.")
        row = self.db.one("SELECT * FROM sessions WHERE token = ? AND kind = ?", (token, kind))
        if row is None:
            raise ServiceError(401, "Your session has expired. Please sign in again.")
        return row

    def _ballots(self, eid: str):
        return self.db.all("SELECT * FROM ballots WHERE election_id = ? ORDER BY seq", (eid,))

    def _check_chain(self, election) -> dict:
        eid, prev, expected_seq = election["id"], election["genesis_hash"], 1
        link_break = content_break = sig_break = None
        rows = self._ballots(eid)
        for b in rows:
            if link_break is None and (b["seq"] != expected_seq or b["prev_hash"] != prev):
                link_break = b["seq"]
            if content_break is None and entry_hash(eid, b["seq"], b["prev_hash"], b["kem_ct"], b["nonce"], b["ct"], b["cast_at"]) != b["entry_hash"]:
                content_break = b["seq"]
            if sig_break is None and not pqc.verify(election["sig_pk"], receipt_message(eid, b["seq"], b["entry_hash"]), b["receipt_sig"]):
                sig_break = b["seq"]
            prev, expected_seq = b["entry_hash"], b["seq"] + 1
        return {"count": len(rows), "head": prev, "link_break": link_break, "content_break": content_break, "sig_break": sig_break}

    def _head_signature_ok(self, election, chain: dict) -> bool | None:
        if election["status"] in ("setup", "open"):
            return None
        sig_ok = pqc.verify(election["sig_pk"], head_message(election["id"], election["closed_count"], election["closed_head"]), election["head_sig"])
        return bool(sig_ok and chain["head"] == election["closed_head"] and chain["count"] == election["closed_count"])

    # ------------------------------------------------------------------ admin
    def admin_login(self, password: str) -> dict:
        if not hmac.compare_digest(str(password).encode(), self.admin_password.encode()):
            raise ServiceError(401, "Incorrect admin password.")
        token = secrets.token_hex(32)
        self.db.run("INSERT INTO sessions VALUES (?, 'admin', 'admin', NULL, ?)", (token, now()))
        return {"token": token}

    def require_admin(self, token: str | None) -> None:
        self._session(token, "admin")

    def create_election(self, title: str, description: str, candidates: list[dict]) -> dict:
        title, description = str(title or "").strip(), str(description or "").strip()
        if not 3 <= len(title) <= 120:
            raise ServiceError(400, "The election title must be between 3 and 120 characters.")
        if len(description) > 500:
            raise ServiceError(400, "The description must be at most 500 characters.")
        cleaned, seen = [], set()
        for c in candidates or []:
            name, party = str(c.get("name", "")).strip(), str(c.get("party", "")).strip() or "Independent"
            if not name:
                continue
            if name.lower() in seen:
                raise ServiceError(400, f"Candidate '{name}' is listed twice.")
            if len(name) > 80 or len(party) > 80:
                raise ServiceError(400, "Candidate and party names must be at most 80 characters.")
            seen.add(name.lower())
            cleaned.append({"id": f"c{len(cleaned) + 1}", "name": name, "party": party, "color": PALETTE[len(cleaned) % len(PALETTE)]})
        if not 2 <= len(cleaned) <= MAX_CANDIDATES:
            raise ServiceError(400, f"An election needs between 2 and {MAX_CANDIDATES} candidates.")

        kem, sig = pqc.kem_keygen(), pqc.sig_keygen()
        eid = "el_" + secrets.token_hex(6)
        row = {"id": eid, "title": title, "description": description, "candidates_json": json.dumps(cleaned),
               "created_at": now(), "kem_pk": kem.public, "sig_pk": sig.public}
        manifest = self._manifest(row)
        manifest_sig = pqc.sign(sig.secret, manifest)
        genesis = pqc.sha3(b"qvote-genesis", eid.encode(), manifest).hex()
        with self.db.lock, self.db.transaction() as tx:
            tx.execute("UPDATE elections SET active = 0")
            tx.execute("DELETE FROM sessions WHERE kind = 'voter'")
            tx.execute(
                "INSERT INTO elections (id, active, title, description, candidates_json, status, created_at, kem_pk, kem_sk, sig_pk, sig_sk, manifest_sig, genesis_hash)"
                " VALUES (?, 1, ?, ?, ?, 'setup', ?, ?, ?, ?, ?, ?, ?)",
                (eid, title, description, row["candidates_json"], row["created_at"], kem.public, kem.secret, sig.public, sig.secret, manifest_sig, genesis),
            )
        return self.election_view()

    def add_voters(self, names: list[str]) -> dict:
        election = self._active()
        names = [str(n).strip() for n in names or [] if str(n).strip()]
        if not names:
            raise ServiceError(400, "Enter at least one voter name.")
        if any(len(n) > 80 for n in names):
            raise ServiceError(400, "Voter names must be at most 80 characters.")
        with self.db.lock:
            existing = self.db.one("SELECT COUNT(*) AS n FROM voters WHERE election_id = ?", (election["id"],))["n"]
            if existing + len(names) > MAX_VOTERS:
                raise ServiceError(400, f"The voter roll is limited to {MAX_VOTERS} voters.")
            created = []
            with self.db.transaction() as tx:
                for i, name in enumerate(names, start=existing + 1):
                    voter_id, password = f"V{i:03d}", f"qv-{i:03d}"
                    digest, salt = hash_password(password)
                    tx.execute("INSERT INTO voters VALUES (?, ?, ?, ?, ?, ?, 0)", (election["id"], voter_id, name, digest, salt, password))
                    created.append({"voter_id": voter_id, "name": name, "credential_issued": False, "demo_password": password})
        return {"voters": created}

    def list_voters(self) -> dict:
        election = self._active()
        rows = self.db.all("SELECT voter_id, name, credential_issued, demo_password FROM voters WHERE election_id = ? ORDER BY voter_id", (election["id"],))
        return {"voters": [{"voter_id": r["voter_id"], "name": r["name"], "credential_issued": bool(r["credential_issued"]), "demo_password": r["demo_password"]} for r in rows]}

    def _transition(self, expected: str, new: str, **fields) -> None:
        election = self._active()
        if election["status"] != expected:
            raise ServiceError(409, f"The election is '{election['status']}'; this action needs it to be '{expected}'.")
        sets = ", ".join(f"{k} = ?" for k in ["status", *fields])
        self.db.run(f"UPDATE elections SET {sets} WHERE id = ?", (new, *fields.values(), election["id"]))

    def open_election(self) -> dict:
        with self.db.lock:
            if self.db.one("SELECT COUNT(*) AS n FROM voters WHERE election_id = ?", (self._active()["id"],))["n"] == 0:
                raise ServiceError(409, "Register at least one voter before opening the election.")
            self._transition("setup", "open", opened_at=now())
        return self.election_view()

    def close_election(self) -> dict:
        with self.db.lock:
            election = self._active()
            if election["status"] != "open":
                raise ServiceError(409, f"The election is '{election['status']}'; only an open election can be closed.")
            chain = self._check_chain(election)
            sig = pqc.sign(election["sig_sk"], head_message(election["id"], chain["count"], chain["head"]))
            self._transition("open", "closed", closed_at=now(), closed_head=chain["head"], closed_count=chain["count"], head_sig=sig)
        return self.election_view()

    def tally(self) -> dict:
        with self.db.lock:
            election = self._active()
            if election["status"] != "closed":
                raise ServiceError(409, "Close the election before tallying.")
            eid, candidates = election["id"], self._candidates(election)
            counts = {c["id"]: 0 for c in candidates}
            invalid = 0
            ballots = self._ballots(eid)
            for b in ballots:
                try:
                    vote = json.loads(pqc.decrypt_ballot(election["kem_sk"], b["kem_ct"], b["nonce"], b["ct"], eid.encode()))
                    if vote.get("e") != eid or vote.get("c") not in counts:
                        raise ValueError("ballot for another election or unknown candidate")
                    counts[vote["c"]] += 1
                except Exception:
                    invalid += 1
            chain = self._check_chain(election)
            tallied_at = now()
            payload = canonical({
                "election_id": eid, "counts": counts, "total_valid": sum(counts.values()), "invalid": invalid,
                "ballot_count": len(ballots), "bulletin_head": chain["head"], "tallied_at": tallied_at,
            }).decode()
            signature = pqc.sign(election["sig_sk"], results_message(payload))
            with self.db.transaction() as tx:
                tx.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?)", (eid, payload, signature, tallied_at))
                tx.execute("UPDATE elections SET status = 'tallied', tallied_at = ? WHERE id = ?", (tallied_at, eid))
        return self.results()

    def keys_info(self) -> dict:
        e = self._active()
        return {
            "election_id": e["id"],
            "kem": {"algorithm": pqc.KEM_ALG, "standard": "NIST FIPS 203", "fingerprint": pqc.fingerprint(e["kem_pk"]),
                    "public_key_bytes": len(e["kem_pk"]), "secret_key_bytes": len(e["kem_sk"]), "public_key_preview": e["kem_pk"][:32].hex()},
            "sig": {"algorithm": pqc.SIG_ALG, "standard": "NIST FIPS 204", "fingerprint": pqc.fingerprint(e["sig_pk"]),
                    "public_key_bytes": len(e["sig_pk"]), "secret_key_bytes": len(e["sig_sk"]), "public_key_preview": e["sig_pk"][:32].hex()},
            "symmetric": {"aead": pqc.AEAD_ALG, "kdf": pqc.KDF_ALG, "hash": pqc.HASH_ALG},
            "manifest_signature_preview": e["manifest_sig"][:24].hex(), "manifest_signature_bytes": len(e["manifest_sig"]),
            "genesis_hash": e["genesis_hash"],
            "note": "Secret keys never leave the server. In production they would live in an HSM or be split between trustees.",
        }

    def simulate(self, count: int) -> dict:
        try:
            count = int(count)
        except (TypeError, ValueError):
            raise ServiceError(400, "Count must be a whole number.") from None
        if not 1 <= count <= 100:
            raise ServiceError(400, "Simulate between 1 and 100 votes at a time.")
        election = self._active()
        if election["status"] != "open":
            raise ServiceError(409, "The election must be open to simulate votes.")
        voters = self.db.all("SELECT voter_id FROM voters WHERE election_id = ? AND credential_issued = 0 ORDER BY voter_id DESC LIMIT ?", (election["id"], count))
        if not voters:
            raise ServiceError(409, "Every registered voter has already voted. Add more voters first.")
        candidates = self._candidates(election)
        weights = SIMULATION_WEIGHTS[: len(candidates)]
        rng = random.Random()
        for v in voters:
            credential = self._issue_credential(election["id"], v["voter_id"])["credential"]
            self.cast(credential, rng.choices(candidates, weights=weights)[0]["id"])
        return {"cast": len(voters)}

    def reset_demo(self) -> dict:
        self.create_election(DEMO_TITLE, DEMO_DESCRIPTION, DEMO_CANDIDATES)
        self.add_voters(DEMO_VOTERS)
        return self.open_election()

    # ------------------------------------------------------------------ attack simulator
    def attack(self, kind: str) -> dict:
        if kind not in ATTACKS:
            raise ServiceError(400, f"Unknown attack. Choose one of: {', '.join(ATTACKS)}.")
        with self.db.lock:
            election = self._active()
            eid = election["id"]
            ballots = self._ballots(eid)
            if kind != "forge_result" and kind != "inject_ballot" and not ballots:
                raise ServiceError(409, "There are no ballots to tamper with yet. Cast or simulate some votes first.")
            result_row = self.db.one("SELECT * FROM results WHERE election_id = ?", (eid,))
            if kind == "forge_result" and result_row is None:
                raise ServiceError(409, "There is no published result to forge yet. Tally the election first.")
            self._snapshot(eid, ballots, result_row)

            if kind == "modify_ballot":
                target = ballots[len(ballots) // 2]
                ct = bytearray(target["ct"])
                ct[0] ^= 0x01
                self.db.run("UPDATE ballots SET ct = ? WHERE election_id = ? AND seq = ?", (bytes(ct), eid, target["seq"]))
                description = f"An insider flipped one bit of encrypted ballot #{target['seq']} directly in the database."
            elif kind == "delete_ballot":
                target = ballots[len(ballots) // 2]
                self.db.run("DELETE FROM ballots WHERE election_id = ? AND seq = ?", (eid, target["seq"]))
                description = f"An insider deleted ballot #{target['seq']} from the bulletin board."
            elif kind == "inject_ballot":
                candidates = self._candidates(election)
                plaintext = canonical({"e": eid, "c": candidates[0]["id"], "n": secrets.token_hex(16)})
                enc = pqc.encrypt_ballot(election["kem_pk"], plaintext, eid.encode())
                last = ballots[-1] if ballots else None
                seq = (last["seq"] if last else 0) + 1
                prev = last["entry_hash"] if last else election["genesis_hash"]
                cast_at = now()
                ehash = entry_hash(eid, seq, prev, enc.kem_ciphertext, enc.nonce, enc.ciphertext, cast_at)
                fake_sig = secrets.token_bytes(len(ballots[0]["receipt_sig"]) if ballots else 3309)
                self.db.run("INSERT INTO ballots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (eid, seq, prev, ehash, enc.kem_ciphertext, enc.nonce, enc.ciphertext, cast_at, fake_sig))
                description = (f"An attacker stuffed a valid-looking ballot for {candidates[0]['name']} at #{seq}, with a correct hash link, "
                               "but without a real credential or the authority's signing key.")
            else:
                payload = json.loads(result_row["payload"])
                ranked = sorted(payload["counts"], key=payload["counts"].get)
                low, high = ranked[0], ranked[-1]
                payload["counts"][low], payload["counts"][high] = payload["counts"][high] + 1, payload["counts"][low]
                payload["total_valid"] = sum(payload["counts"].values())
                self.db.run("UPDATE results SET payload = ? WHERE election_id = ?", (canonical(payload).decode(), eid))
                names = {c["id"]: c["name"] for c in self._candidates(election)}
                description = f"An insider rewrote the published result so that {names[low]} wins instead of {names[high]}, reusing the old signature."
        return {"applied": True, "kind": kind, "description": description}

    def _snapshot(self, eid: str, ballots, result_row) -> None:
        if self.db.one("SELECT 1 FROM attack_snapshots WHERE election_id = ?", (eid,)):
            return
        rows = [{k: (b[k].hex() if isinstance(b[k], bytes) else b[k]) for k in b.keys()} for b in ballots]
        res = None if result_row is None else {"payload": result_row["payload"], "signature": result_row["signature"].hex(), "tallied_at": result_row["tallied_at"]}
        self.db.run("INSERT INTO attack_snapshots VALUES (?, ?, ?)", (eid, json.dumps(rows), json.dumps(res)))

    def restore(self) -> dict:
        with self.db.lock:
            eid = self._active()["id"]
            snap = self.db.one("SELECT * FROM attack_snapshots WHERE election_id = ?", (eid,))
            if snap is None:
                return {"restored": False, "description": "Nothing to restore: no attack has been applied."}
            blob_cols = {"kem_ct", "nonce", "ct", "receipt_sig"}
            with self.db.transaction() as tx:
                tx.execute("DELETE FROM ballots WHERE election_id = ?", (eid,))
                for r in json.loads(snap["ballots_json"]):
                    vals = {k: (bytes.fromhex(v) if k in blob_cols else v) for k, v in r.items()}
                    tx.execute("INSERT INTO ballots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (vals["election_id"], vals["seq"], vals["prev_hash"], vals["entry_hash"], vals["kem_ct"], vals["nonce"], vals["ct"], vals["cast_at"], vals["receipt_sig"]))
                tx.execute("DELETE FROM results WHERE election_id = ?", (eid,))
                res = json.loads(snap["results_json"]) if snap["results_json"] else None
                if res:
                    tx.execute("INSERT INTO results VALUES (?, ?, ?, ?)", (eid, res["payload"], bytes.fromhex(res["signature"]), res["tallied_at"]))
                tx.execute("DELETE FROM attack_snapshots WHERE election_id = ?", (eid,))
        return {"restored": True, "description": "The database was restored to its state before the attacks."}

    # ------------------------------------------------------------------ voter
    def voter_login(self, voter_id: str, password: str) -> dict:
        election = self._active()
        voter_id = str(voter_id or "").strip().upper()
        row = self.db.one("SELECT * FROM voters WHERE election_id = ? AND voter_id = ?", (election["id"], voter_id))
        if row is None or not check_password(str(password or ""), row["pw_hash"], row["pw_salt"]):
            raise ServiceError(401, "Voter ID or password is incorrect.")
        token = secrets.token_hex(32)
        self.db.run("INSERT INTO sessions VALUES (?, 'voter', ?, ?, ?)", (token, voter_id, election["id"], now()))
        return {"token": token, "voter": {"voter_id": voter_id, "name": row["name"], "credential_issued": bool(row["credential_issued"])}}

    def issue_credential(self, token: str | None) -> dict:
        session = self._session(token, "voter")
        election = self._active()
        if session["election_id"] != election["id"]:
            raise ServiceError(401, "Your session belongs to a previous election. Please sign in again.")
        if election["status"] != "open":
            raise ServiceError(400, f"Voting is not open (the election is '{election['status']}').")
        return self._issue_credential(election["id"], session["subject"])

    def _issue_credential(self, eid: str, voter_id: str) -> dict:
        credential = secrets.token_hex(32)
        chash = credential_hash(credential)
        with self.db.lock, self.db.transaction() as tx:
            updated = tx.execute("UPDATE voters SET credential_issued = 1 WHERE election_id = ? AND voter_id = ? AND credential_issued = 0", (eid, voter_id)).rowcount
            if updated != 1:
                raise ServiceError(409, "You have already received your ballot credential. Each voter can vote only once.")
            # The credential table deliberately stores no voter id: the ballot cannot be traced back.
            tx.execute("INSERT INTO credentials VALUES (?, ?, 0)", (eid, chash))
        return {"credential": credential, "credential_fingerprint": chash[:16]}

    def cast(self, credential: str, candidate_id: str) -> dict:
        credential = str(credential or "").strip().lower()
        if not _HEX64.match(credential):
            raise ServiceError(403, "This ballot credential is not valid.")
        with self.db.lock:
            election = self._active()
            eid = election["id"]
            if election["status"] != "open":
                raise ServiceError(400, f"Voting is not open (the election is '{election['status']}').")
            if candidate_id not in {c["id"] for c in self._candidates(election)}:
                raise ServiceError(400, "Unknown candidate.")
            chash = credential_hash(credential)
            if self.db.one("SELECT 1 FROM credentials WHERE election_id = ? AND cred_hash = ? AND used = 0", (eid, chash)) is None:
                raise ServiceError(403, "This ballot credential is invalid or has already been used.")

            plaintext = canonical({"e": eid, "c": candidate_id, "n": secrets.token_hex(16)})
            enc = pqc.encrypt_ballot(election["kem_pk"], plaintext, eid.encode())
            trace = list(enc.trace)

            t = time.perf_counter()
            last = self.db.one("SELECT seq, entry_hash FROM ballots WHERE election_id = ? ORDER BY seq DESC LIMIT 1", (eid,))
            seq = (last["seq"] if last else 0) + 1
            prev = last["entry_hash"] if last else election["genesis_hash"]
            cast_at = now()
            ehash = entry_hash(eid, seq, prev, enc.kem_ciphertext, enc.nonce, enc.ciphertext, cast_at)
            trace.append(pqc.TraceStep(f"Hash-chain append ({pqc.HASH_ALG})", f"Entry #{seq} linked to the previous entry {prev[:12]}…", (time.perf_counter() - t) * 1e3))

            t = time.perf_counter()
            receipt_sig = pqc.sign(election["sig_sk"], receipt_message(eid, seq, ehash))
            trace.append(pqc.TraceStep(f"Receipt signed ({pqc.SIG_ALG})", "The authority signs your receipt so it can never deny accepting this ballot", (time.perf_counter() - t) * 1e3, len(receipt_sig)))

            with self.db.transaction() as tx:
                if tx.execute("UPDATE credentials SET used = 1 WHERE election_id = ? AND cred_hash = ? AND used = 0", (eid, chash)).rowcount != 1:
                    raise ServiceError(403, "This ballot credential is invalid or has already been used.")
                tx.execute("INSERT INTO ballots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (eid, seq, prev, ehash, enc.kem_ciphertext, enc.nonce, enc.ciphertext, cast_at, receipt_sig))
        return {
            "receipt": {"election_id": eid, "seq": seq, "receipt_code": ehash, "cast_at": cast_at, "sig_alg": pqc.SIG_ALG,
                        "authority_signature": receipt_sig.hex(), "signature_bytes": len(receipt_sig)},
            "crypto_trace": [s.to_dict() for s in trace],
        }

    # ------------------------------------------------------------------ public
    def election_view(self) -> dict:
        e = self._active()
        eid = e["id"]
        registered = self.db.one("SELECT COUNT(*) AS n FROM voters WHERE election_id = ?", (eid,))["n"]
        issued = self.db.one("SELECT COUNT(*) AS n FROM voters WHERE election_id = ? AND credential_issued = 1", (eid,))["n"]
        cast = self.db.one("SELECT COUNT(*) AS n FROM ballots WHERE election_id = ?", (eid,))["n"]
        return {
            "id": eid, "title": e["title"], "description": e["description"], "status": e["status"],
            "candidates": self._candidates(e),
            "created_at": e["created_at"], "opened_at": e["opened_at"], "closed_at": e["closed_at"], "tallied_at": e["tallied_at"],
            "stats": {"registered": registered, "credentials_issued": issued, "ballots_cast": cast, "turnout": round(cast / registered, 4) if registered else 0.0},
            "authority": {
                "kem_alg": pqc.KEM_ALG, "sig_alg": pqc.SIG_ALG,
                "kem_public_key_fingerprint": pqc.fingerprint(e["kem_pk"]), "sig_public_key_fingerprint": pqc.fingerprint(e["sig_pk"]),
                "kem_public_key_bytes": len(e["kem_pk"]), "sig_public_key_bytes": len(e["sig_pk"]),
                "manifest_signature_valid": pqc.verify(e["sig_pk"], self._manifest(e), e["manifest_sig"]),
            },
        }

    def bulletin(self, limit: int = 50, offset: int = 0) -> dict:
        e = self._active()
        limit, offset = max(1, min(int(limit), 200)), max(0, int(offset))
        rows = self.db.all("SELECT * FROM ballots WHERE election_id = ? ORDER BY seq DESC LIMIT ? OFFSET ?", (e["id"], limit, offset))
        chain = self._check_chain(e)
        return {
            "entries": [{
                "seq": r["seq"], "entry_hash": r["entry_hash"], "prev_hash": r["prev_hash"],
                "kem_ciphertext_preview": r["kem_ct"][:16].hex(), "ciphertext_preview": r["ct"][:16].hex(),
                "kem_ciphertext_bytes": len(r["kem_ct"]), "ciphertext_bytes": len(r["ct"]), "cast_at": r["cast_at"],
            } for r in rows],
            "total": chain["count"], "head_hash": chain["head"], "genesis_hash": e["genesis_hash"],
            "chain_valid": chain["link_break"] is None and chain["content_break"] is None,
            "head_signature_valid": self._head_signature_ok(e, chain),
        }

    def results(self) -> dict:
        e = self._active()
        row = self.db.one("SELECT * FROM results WHERE election_id = ?", (e["id"],))
        if e["status"] != "tallied" or row is None:
            return {"status": e["status"], "sealed": True}
        payload = json.loads(row["payload"])
        total = payload["total_valid"]
        counts = []
        for c in self._candidates(e):
            votes = int(payload["counts"].get(c["id"], 0))
            counts.append({"candidate_id": c["id"], "name": c["name"], "party": c["party"], "color": c["color"],
                           "votes": votes, "percent": round(100 * votes / total, 1) if total else 0.0})
        top = max((c["votes"] for c in counts), default=0)
        return {
            "status": "tallied", "sealed": False, "counts": counts, "total_valid": total, "invalid": payload["invalid"],
            "winners": [c["candidate_id"] for c in counts if top > 0 and c["votes"] == top],
            "tallied_at": payload["tallied_at"], "bulletin_head": payload["bulletin_head"],
            "signature_valid": pqc.verify(e["sig_pk"], results_message(row["payload"]), row["signature"]),
            "signature_preview": row["signature"][:24].hex(), "signature_bytes": len(row["signature"]),
        }

    def verify_receipt(self, code: str) -> dict:
        code = re.sub(r"[\s\-:]", "", str(code or "")).lower()
        if not _HEX64.match(code):
            return {"found": False}
        e = self._active()
        b = self.db.one("SELECT * FROM ballots WHERE election_id = ? AND entry_hash = ?", (e["id"], code))
        if b is None:
            return {"found": False}
        chain = self._check_chain(e)
        chain_ok = chain["link_break"] is None and chain["content_break"] is None
        head_ok = self._head_signature_ok(e, chain)
        return {
            "found": True, "seq": b["seq"], "entry_hash": b["entry_hash"], "cast_at": b["cast_at"],
            "receipt_signature_valid": pqc.verify(e["sig_pk"], receipt_message(e["id"], b["seq"], b["entry_hash"]), b["receipt_sig"]),
            "chain_valid": chain_ok,
            "included_in_final_head": None if head_ok is None else bool(head_ok and chain_ok and b["seq"] <= e["closed_count"]),
        }

    def audit(self) -> dict:
        e = self._active()
        eid = e["id"]
        chain = self._check_chain(e)
        n = chain["count"]
        used = self.db.one("SELECT COUNT(*) AS n FROM credentials WHERE election_id = ? AND used = 1", (eid,))["n"]
        manifest_ok = pqc.verify(e["sig_pk"], self._manifest(e), e["manifest_sig"])
        head_ok = self._head_signature_ok(e, chain)

        checks = [
            {"id": "manifest", "label": f"Election manifest signed by the authority ({pqc.SIG_ALG})", "passed": manifest_ok,
             "detail": "Title, candidates and public keys match what the authority signed." if manifest_ok else "The manifest no longer matches the authority's signature."},
            {"id": "chain", "label": "Bulletin board hash chain is unbroken", "passed": chain["link_break"] is None,
             "detail": f"All {n} entries link back to the genesis hash." if chain["link_break"] is None else f"The chain breaks at entry #{chain['link_break']}: an entry is missing or out of order."},
            {"id": "ballot_integrity", "label": f"Every encrypted ballot matches its {pqc.HASH_ALG} entry hash", "passed": chain["content_break"] is None,
             "detail": f"None of the {n} ciphertexts has been altered." if chain["content_break"] is None else f"Ballot #{chain['content_break']} was modified after it was cast."},
            {"id": "receipts", "label": f"Every ballot carries the authority's receipt signature ({pqc.SIG_ALG})", "passed": chain["sig_break"] is None,
             "detail": f"{n}/{n} receipt signatures verify." if chain["sig_break"] is None else f"Ballot #{chain['sig_break']} has no valid authority signature: it was not accepted through the voting process."},
            {"id": "head_signature", "label": "Final bulletin head signed when voting closed", "passed": head_ok,
             "detail": "The board is still open; the authority signs its final state when voting closes." if head_ok is None
             else ("The board is exactly the one the authority sealed." if head_ok else "The board differs from the state the authority sealed at closing.")},
            {"id": "count_consistency", "label": "Ballots on the board equal credentials used", "passed": used == n,
             "detail": f"{n} ballots for {used} used credentials." + ("" if used == n else " Ballots were removed or stuffed.")},
        ]
        res = self.db.one("SELECT * FROM results WHERE election_id = ?", (eid,))
        if e["status"] == "tallied" and res is not None:
            payload = json.loads(res["payload"])
            sig_ok = pqc.verify(e["sig_pk"], results_message(res["payload"]), res["signature"])
            matches = payload.get("bulletin_head") == chain["head"] and payload.get("ballot_count") == n
            ok = sig_ok and matches
            detail = ("The published result is signed and was computed from this exact board." if ok
                      else "The published result does not match the authority's signature." if not sig_ok
                      else "The result was computed from a different board than the one published now.")
        else:
            ok, detail = None, "Results are published after the tally."
        checks.append({"id": "results_signature", "label": f"Published result signed by the authority ({pqc.SIG_ALG})", "passed": ok, "detail": detail})
        return {"all_passed": all(c["passed"] is not False for c in checks), "checks": checks}

    def shor_demo(self, vote: str | None = None) -> dict:
        e = self._active()
        candidates = self._candidates(e)
        by_id = {c["id"]: c for c in candidates}
        rng = random.Random()
        chosen = by_id.get(vote) or rng.choice(candidates)
        key = shor.make_toy_rsa(rng)
        m = candidates.index(chosen) + 2
        c = key.encrypt(m)
        p, q, a, steps = shor.factor_with_period(key.n, rng)
        phi = (p - 1) * (q - 1)
        d = pow(key.e, -1, phi)
        m2 = pow(c, d, key.n)
        decrypted = candidates[m2 - 2] if 2 <= m2 < len(candidates) + 2 else None
        steps = [
            {"title": "Intercept a legacy ballot", "detail": f"The ballot was encrypted with RSA public key (N, e) = ({key.n}, {key.e}): ciphertext {c}. "
             "An attacker can record it today and decrypt it later ('harvest now, decrypt later')."},
            *steps,
            {"title": "Rebuild the private key", "detail": f"φ(N) = ({p} − 1)({q} − 1) = {phi}, so d = e⁻¹ mod φ(N) = {d}."},
            {"title": "Decrypt the ballot", "detail": f"m = {c}^{d} mod {key.n} = {m2}, which encodes {decrypted['name'] if decrypted else 'an unknown candidate'}."},
        ]
        return {
            "rsa": {"p": key.p, "q": key.q, "n": key.n, "e": key.e},
            "vote": {"candidate_id": chosen["id"], "name": chosen["name"], "plaintext_int": m, "ciphertext_int": c},
            "steps": steps,
            "recovered": {"p": p, "q": q, "phi": phi, "d": d, "base": a},
            "decrypted": {"plaintext_int": m2, "candidate_id": decrypted["id"] if decrypted else None, "name": decrypted["name"] if decrypted else None},
            "success": bool(decrypted and decrypted["id"] == chosen["id"]),
            "scale_note": "Real RSA uses a 2048-bit N (617 digits). Recent estimates (Gidney, 2025) put that within reach of a quantum computer "
                          "with under a million noisy qubits running for about a week. No such machine exists yet, but recorded ballots stay readable forever.",
            "pqc_comparison": PQC_COMPARISON,
        }
