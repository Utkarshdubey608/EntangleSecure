import pytest

from qvote.service import ElectionService
from qvote.storage import Database


@pytest.fixture
def svc() -> ElectionService:
    s = ElectionService(Database(":memory:"), admin_password="test-admin")
    s.reset_demo()
    return s


def vote(svc: ElectionService, voter_no: int, candidate_id: str) -> dict:
    token = svc.voter_login(f"V{voter_no:03d}", f"qv-{voter_no:03d}")["token"]
    credential = svc.issue_credential(token)["credential"]
    return svc.cast(credential, candidate_id)
