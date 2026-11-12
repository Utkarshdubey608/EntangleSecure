import pytest

from qvote.service import ElectionService, ServiceError
from qvote.storage import Database
from tests.conftest import vote


def test_demo_election_is_open_with_valid_manifest(svc):
    e = svc.election_view()
    assert e["status"] == "open" and e["stats"]["registered"] == 30 and len(e["candidates"]) == 4
    assert e["authority"]["manifest_signature_valid"]


def test_cast_returns_signed_receipt_and_trace(svc):
    r = vote(svc, 1, "c2")
    assert r["receipt"]["seq"] == 1 and len(r["receipt"]["receipt_code"]) == 64
    assert [s["step"].split(" ")[0] for s in r["crypto_trace"]] == ["ML-KEM-768", "HKDF-SHA3-256", "AES-256-GCM", "Hash-chain", "Receipt"]
    check = svc.verify_receipt(r["receipt"]["receipt_code"].upper())
    assert check["found"] and check["receipt_signature_valid"] and check["chain_valid"]
    assert check["included_in_final_head"] is None


def test_one_person_one_vote(svc):
    token = svc.voter_login("V002", "qv-002")["token"]
    cred = svc.issue_credential(token)["credential"]
    svc.cast(cred, "c1")
    with pytest.raises(ServiceError) as reuse:
        svc.cast(cred, "c1")
    assert reuse.value.status == 403
    with pytest.raises(ServiceError) as again:
        svc.issue_credential(token)
    assert again.value.status == 409


def test_credentials_are_not_linked_to_voters(svc):
    vote(svc, 3, "c1")
    cols = [r[1] for r in svc.db.all("PRAGMA table_info(credentials)")]
    assert "voter_id" not in cols
    assert "voter_id" not in [r[1] for r in svc.db.all("PRAGMA table_info(ballots)")]


def test_bad_inputs(svc):
    with pytest.raises(ServiceError) as wrong_pw:
        svc.voter_login("V001", "nope")
    assert wrong_pw.value.status == 401
    with pytest.raises(ServiceError):
        svc.cast("zz", "c1")
    token = svc.voter_login("V004", "qv-004")["token"]
    cred = svc.issue_credential(token)["credential"]
    with pytest.raises(ServiceError) as unknown:
        svc.cast(cred, "c99")
    assert unknown.value.status == 400
    assert svc.verify_receipt("not-a-receipt") == {"found": False}


def test_lifecycle_and_tally_counts_every_vote(svc):
    expected = {"c1": 3, "c2": 2, "c3": 1, "c4": 0}
    n = 1
    for cid, k in expected.items():
        for _ in range(k):
            vote(svc, n, cid)
            n += 1
    with pytest.raises(ServiceError):
        svc.tally()
    svc.close_election()
    with pytest.raises(ServiceError):
        vote(svc, 20, "c1")
    res = svc.tally()
    assert {c["candidate_id"]: c["votes"] for c in res["counts"]} == expected
    assert res["winners"] == ["c1"] and res["signature_valid"] and res["invalid"] == 0
    audit = svc.audit()
    assert audit["all_passed"] and all(c["passed"] is True for c in audit["checks"])


def test_results_sealed_until_tally(svc):
    vote(svc, 1, "c1")
    assert svc.results() == {"status": "open", "sealed": True}


@pytest.mark.parametrize("kind, failing", [
    ("modify_ballot", {"ballot_integrity"}),
    ("delete_ballot", {"chain", "head_signature", "count_consistency", "results_signature"}),
    ("inject_ballot", {"receipts", "head_signature", "count_consistency", "results_signature"}),
    ("forge_result", {"results_signature"}),
])
def test_every_attack_is_detected_and_restorable(svc, kind, failing):
    for i, cid in enumerate(["c1", "c2", "c1", "c3", "c1"], start=1):
        vote(svc, i, cid)
    svc.close_election()
    svc.tally()
    svc.attack(kind)
    audit = svc.audit()
    assert not audit["all_passed"]
    assert {c["id"] for c in audit["checks"] if c["passed"] is False} == failing
    assert svc.restore()["restored"]
    assert svc.audit()["all_passed"]


def test_tampered_ballot_is_rejected_by_tally(svc):
    for i in range(1, 4):
        vote(svc, i, "c1")
    svc.attack("modify_ballot")
    svc.close_election()
    res = svc.tally()
    assert res["invalid"] == 1 and res["total_valid"] == 2


def test_forged_result_is_visible_but_unsigned(svc):
    vote(svc, 1, "c1")
    vote(svc, 2, "c1")
    svc.close_election()
    svc.tally()
    svc.attack("forge_result")
    assert svc.results()["signature_valid"] is False


def test_simulate_and_validation(svc):
    assert svc.simulate(5) == {"cast": 5}
    assert svc.election_view()["stats"]["ballots_cast"] == 5
    with pytest.raises(ServiceError):
        svc.simulate(0)
    svc.simulate(25)
    with pytest.raises(ServiceError) as none_left:
        svc.simulate(1)
    assert none_left.value.status == 409


def test_create_election_validation():
    s = ElectionService(Database(":memory:"))
    with pytest.raises(ServiceError):
        s.create_election("Ok title", "", [{"name": "Only one"}])
    with pytest.raises(ServiceError):
        s.create_election("Ok title", "", [{"name": "A"}, {"name": "a"}])
    e = s.create_election("Club vote", "", [{"name": "A"}, {"name": "B", "party": "X"}])
    assert e["status"] == "setup" and e["candidates"][0]["party"] == "Independent"
    with pytest.raises(ServiceError):
        s.open_election()
    s.add_voters(["Voter One"])
    assert s.open_election()["status"] == "open"


def test_shor_demo_recovers_vote(svc):
    d = svc.shor_demo("c3")
    assert d["success"] and d["decrypted"]["candidate_id"] == "c3"
    assert d["recovered"]["p"] * d["recovered"]["q"] == d["rsa"]["n"]
