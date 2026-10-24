import pytest
from httpx import AsyncClient, ASGITransport
from backend.src.main import app
from src.auth.service import create_access_token, DEMO_USERS
from src.storage.database import db
from src.models import (
    ApprovalRequest,
    ApprovalStatus,
    UserRole,
    ProposedAction
)
from src.agents.graph import compute_payload_hash


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_live_endpoint(client: AsyncClient):
    res = await client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_endpoint(client: AsyncClient):
    await db.init_db()
    res = await client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "sqlite_wal_ready"


@pytest.mark.asyncio
async def test_integrations_status_endpoint(client: AsyncClient):
    res = await client.get("/api/integrations/status")
    assert res.status_code == 200
    data = res.json()
    assert "adapters" in data
    assert "sap" in data["adapters"]
    assert "m365" in data["adapters"]
    assert "mcp" in data["adapters"]
    assert "dlp" in data["adapters"]


@pytest.mark.asyncio
async def test_auth_token_success(client: AsyncClient):
    res = await client.post("/api/auth/token", json={"email": "alice.requester@company.internal"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["full_name"] == "Alice Chen"


@pytest.mark.asyncio
async def test_auth_token_unknown_user(client: AsyncClient):
    res = await client.post("/api/auth/token", json={"email": "unknown.hacker@evil.com"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_auth_users_list(client: AsyncClient):
    res = await client.get("/api/auth/users")
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 4
    emails = [u["email"] for u in users]
    assert "alice.requester@company.internal" in emails
    assert "bob.manager@company.internal" in emails


@pytest.mark.asyncio
async def test_conversations_flow(client: AsyncClient):
    alice = DEMO_USERS["alice.requester@company.internal"]
    token = create_access_token(alice)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create conversation
    create_res = await client.post(
        "/api/conversations",
        json={"title": "Test Workstation Requisition"},
        headers=headers
    )
    assert create_res.status_code == 200
    conv_data = create_res.json()
    conv_id = conv_data["id"]

    # 2. Get conversation
    get_res = await client.get(f"/api/conversations/{conv_id}", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["conversation"]["id"] == conv_id
    assert isinstance(data["messages"], list)


@pytest.mark.asyncio
async def test_governance_documents_filtering(client: AsyncClient):
    # Contractor only sees PUBLIC
    contractor = DEMO_USERS["mallory.external@vendor.internal"]
    c_token = create_access_token(contractor)
    c_res = await client.get("/api/documents", headers={"Authorization": f"Bearer {c_token}"})
    assert c_res.status_code == 200
    c_docs = c_res.json()
    for d in c_docs:
        assert d["access_tier"] == "PUBLIC"

    # Executive sees all tiers
    vp = DEMO_USERS["carol.vp@company.internal"]
    vp_token = create_access_token(vp)
    vp_res = await client.get("/api/documents", headers={"Authorization": f"Bearer {vp_token}"})
    assert vp_res.status_code == 200
    vp_docs = vp_res.json()
    tiers = {d["access_tier"] for d in vp_docs}
    assert "RESTRICTED" in tiers or len(vp_docs) >= len(c_docs)


@pytest.mark.asyncio
async def test_audit_logs_endpoint(client: AsyncClient):
    alice = DEMO_USERS["alice.requester@company.internal"]
    token = create_access_token(alice)
    res = await client.get("/api/audit/logs?limit=10", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)


@pytest.mark.asyncio
async def test_approval_rejection_flow(client: AsyncClient):
    await db.init_db()

    # Pre-create conversation to satisfy SQLite foreign key
    from src.models import Conversation
    await db.create_conversation(Conversation(
        id="conv-rej-01",
        user_id="usr-alice-01",
        title="Rejection Flow Conv"
    ))

    action_data = {
        "action_id": "act-rej-01",
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_name": "Dell Technologies India Ltd",
        "vendor_id": "SAP-VEN-99104",
        "sku": "WS-ERGO-01",
        "item_description": "Ergonomic Workstation",
        "quantity": 2,
        "unit_price": "250.00",
        "total_amount": "500.00",
        "currency": "USD",
        "cost_center": "8820",
        "policy_reference": "Section 2.1",
        "target_environment": "LOCAL_SIMULATOR",
        "payload_hash": ""
    }
    action_data["payload_hash"] = compute_payload_hash(action_data)

    appr = ApprovalRequest(
        id="appr-rej-01",
        run_id="run-rej-01",
        conversation_id="conv-rej-01",
        requester_id="usr-alice-01",
        requester_name="Alice Chen",
        proposed_action=ProposedAction(**action_data),
        status=ApprovalStatus.PENDING,
        required_role=UserRole.APPROVER
    )
    await db.save_approval_request(appr)

    # Bob (manager) rejects the request
    bob = DEMO_USERS["bob.manager@company.internal"]
    bob_token = create_access_token(bob)
    dec_res = await client.post(
        f"/api/approvals/appr-rej-01/decision",
        json={"decision": "REJECT", "reason": "Department budget frozen for Q1."},
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "REJECTED"

    # Verify updated in DB
    refreshed = await db.get_approval("appr-rej-01")
    assert refreshed.status == ApprovalStatus.REJECTED
    assert refreshed.decision_reason == "Department budget frozen for Q1."
    assert refreshed.decision_by == bob.id


@pytest.mark.asyncio
async def test_approval_missing_mandatory_reason(client: AsyncClient):
    bob = DEMO_USERS["bob.manager@company.internal"]
    bob_token = create_access_token(bob)
    dec_res = await client.post(
        f"/api/approvals/appr-rej-01/decision",
        json={"decision": "REJECT", "reason": "ab"},  # min length is 3
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    assert dec_res.status_code == 422
