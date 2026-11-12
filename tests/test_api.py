import pytest
from fastapi.testclient import TestClient

from qvote.api import create_app
from qvote.service import ElectionService
from qvote.storage import Database


@pytest.fixture
def client():
    return TestClient(create_app(ElectionService(Database(":memory:"), admin_password="test-admin")))


def admin_headers(client):
    token = client.post("/api/admin/login", json={"password": "test-admin"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_full_flow_over_http(client):
    login = client.post("/api/voter/login", json={"voter_id": "v001", "password": "qv-001"})
    assert login.status_code == 200
    token = login.json()["token"]
    cred = client.post("/api/voter/credential", headers={"Authorization": f"Bearer {token}"}).json()["credential"]
    cast = client.post("/api/voter/cast", json={"credential": cred, "candidate_id": "c1"})
    assert cast.status_code == 200
    code = cast.json()["receipt"]["receipt_code"]
    assert client.post("/api/verify/receipt", json={"receipt_code": code}).json()["found"]
    assert client.get("/api/bulletin").json()["total"] == 1

    h = admin_headers(client)
    assert client.post("/api/admin/election/close", headers=h).status_code == 200
    res = client.post("/api/admin/election/tally", headers=h).json()
    assert res["counts"][0]["votes"] == 1 and res["signature_valid"]
    assert client.get("/api/audit").json()["all_passed"]


def test_admin_routes_need_token(client):
    assert client.post("/api/admin/election/open").status_code == 401
    assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
    assert client.get("/api/admin/voters", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_errors_are_json(client):
    r = client.post("/api/voter/cast", json={"credential": "0" * 64, "candidate_id": "c1"})
    assert r.status_code == 403 and "detail" in r.json()
    assert client.get("/api/does-not-exist").status_code == 404


def test_attack_endpoint_round_trip(client):
    h = admin_headers(client)
    client.post("/api/admin/simulate", json={"count": 4}, headers=h)
    assert client.post("/api/admin/attack", json={"kind": "inject_ballot"}, headers=h).json()["applied"]
    assert not client.get("/api/audit").json()["all_passed"]
    client.post("/api/admin/attack/restore", headers=h)
    assert client.get("/api/audit").json()["all_passed"]
    assert client.post("/api/admin/attack", json={"kind": "nuke"}, headers=h).status_code == 400


def test_lab_endpoints(client):
    bench = client.get("/api/lab/benchmark").json()
    assert {r["scheme"] for r in bench["rows"]} >= {"ML-KEM-768", "ML-DSA-65", "RSA-2048"}
    assert client.post("/api/lab/shor", json={}).json()["success"]


def test_keys_never_expose_secrets(client):
    keys = client.get("/api/admin/keys", headers=admin_headers(client)).json()
    svc = client.app.state.service
    election = svc.db.one("SELECT kem_sk, sig_sk FROM elections WHERE active = 1")
    text = str(keys)
    # ML-DSA secret keys begin with the public seed rho (shared with the public key); bytes 32-64 are the secret K.
    assert election["kem_sk"][:32].hex() not in text and election["sig_sk"][32:64].hex() not in text
    assert keys["kem"]["secret_key_bytes"] == 2400 and len(keys["kem"]["public_key_preview"]) == 64
