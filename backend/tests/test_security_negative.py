import pytest
import asyncio
from decimal import Decimal
from fastapi import HTTPException
from src.models import (
    User,
    UserRole,
    AccessTier,
    ApprovalRequest,
    ApprovalStatus,
    ProposedAction,
    ApprovalDecisionRequest
)
from src.auth.service import DEMO_USERS
from src.agents.graph import compute_payload_hash, supervisor_node
from src.agents.state import AgentState
from src.storage.database import db
from backend.src.main import decide_approval


@pytest.mark.asyncio
async def test_self_approval_prevention():
    await db.init_db()

    action_data = {
        "action_id": "act-sec-01",
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_name": "Dell Technologies India Ltd",
        "vendor_id": "SAP-VEN-99104",
        "sku": "WS-ERGO-01",
        "item_description": "Ergonomic Workstation",
        "quantity": 3,
        "unit_price": "450.00",
        "total_amount": "1350.00",
        "currency": "USD",
        "cost_center": "8820",
        "policy_reference": "Section 2.1",
        "target_environment": "LOCAL_SIMULATOR",
        "payload_hash": ""
    }
    action_data["payload_hash"] = compute_payload_hash(action_data)

    appr = ApprovalRequest(
        id="appr-sec-01",
        run_id="run-sec-01",
        conversation_id="conv-sec-01",
        requester_id="usr-alice-01",
        requester_name="Alice Chen",
        proposed_action=ProposedAction(**action_data),
        status=ApprovalStatus.PENDING,
        required_role=UserRole.APPROVER
    )
    await db.save_approval_request(appr)

    # Requester (Alice) attempts to approve her own request
    alice_user = DEMO_USERS["alice.requester@company.internal"]
    body = ApprovalDecisionRequest(decision="APPROVE", reason="I approve my own purchase.")

    with pytest.raises(HTTPException) as exc_info:
        await decide_approval(
            approval_id="appr-sec-01",
            body=body,
            current_user=alice_user
        )
    assert exc_info.value.status_code == 403
    assert "Self-approval prohibited" in exc_info.value.detail


@pytest.mark.asyncio
async def test_unauthorized_role_approval_rejection():
    await db.init_db()

    # Requisition > $10,000 requires EXECUTIVE_APPROVER
    action_data = {
        "action_id": "act-sec-02",
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_name": "Dell Technologies India Ltd",
        "vendor_id": "SAP-VEN-99104",
        "sku": "SRV-EDGE-X8",
        "item_description": "Dell PowerEdge Server Cluster",
        "quantity": 10,
        "unit_price": "3200.00",
        "total_amount": "32000.00",
        "currency": "USD",
        "cost_center": "8820",
        "policy_reference": "Spending Matrix v5.1 Section 2.1",
        "target_environment": "LOCAL_SIMULATOR",
        "payload_hash": ""
    }
    action_data["payload_hash"] = compute_payload_hash(action_data)

    appr = ApprovalRequest(
        id="appr-sec-02",
        run_id="run-sec-02",
        conversation_id="conv-sec-02",
        requester_id="usr-alice-01",
        requester_name="Alice Chen",
        proposed_action=ProposedAction(**action_data),
        status=ApprovalStatus.PENDING,
        required_role=UserRole.EXECUTIVE_APPROVER
    )
    await db.save_approval_request(appr)

    # Bob (regular APPROVER, limit $5,000) attempts to approve $32,000 purchase
    bob_user = DEMO_USERS["bob.manager@company.internal"]
    body = ApprovalDecisionRequest(decision="APPROVE", reason="Manager signoff.")

    with pytest.raises(HTTPException) as exc_info:
        await decide_approval(
            approval_id="appr-sec-02",
            body=body,
            current_user=bob_user
        )
    assert exc_info.value.status_code == 403
    assert "EXECUTIVE_APPROVER" in exc_info.value.detail


@pytest.mark.asyncio
async def test_payload_tampering_hash_verification():
    await db.init_db()

    action_data = {
        "action_id": "act-sec-03",
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_name": "Dell Technologies India Ltd",
        "vendor_id": "SAP-VEN-99104",
        "sku": "WS-ERGO-01",
        "item_description": "Ergonomic Workstation",
        "quantity": 3,
        "unit_price": "450.00",
        "total_amount": "1350.00",
        "currency": "USD",
        "cost_center": "8820",
        "policy_reference": "Section 2.1",
        "target_environment": "LOCAL_SIMULATOR",
        "payload_hash": "TAMPERED_OR_CORRUPTED_HASH_VALUE"
    }

    appr = ApprovalRequest(
        id="appr-sec-03",
        run_id="run-sec-03",
        conversation_id="conv-sec-03",
        requester_id="usr-alice-01",
        requester_name="Alice Chen",
        proposed_action=ProposedAction(**action_data),
        status=ApprovalStatus.PENDING,
        required_role=UserRole.APPROVER
    )
    await db.save_approval_request(appr)

    # Bob attempts to approve tampered payload
    bob_user = DEMO_USERS["bob.manager@company.internal"]
    body = ApprovalDecisionRequest(decision="APPROVE", reason="Looks fine to me.")

    with pytest.raises(HTTPException) as exc_info:
        await decide_approval(
            approval_id="appr-sec-03",
            body=body,
            current_user=bob_user
        )
    assert exc_info.value.status_code == 400
    assert "Payload Integrity Failure" in exc_info.value.detail


@pytest.mark.asyncio
async def test_prohibited_grey_market_vendor_rejection():
    # Attempting to procure from unauthorized vendor
    state: AgentState = {
        "run_id": "run-sec-04",
        "conversation_id": "conv-sec-04",
        "user_id": "usr-alice-01",
        "user_role": "REQUESTER",
        "proposed_action": {
            "action_id": "act-sec-04",
            "action_type": "SAP_CREATE_PURCHASE_ORDER",
            "vendor_name": "Unauthorized Grey Market Imports Ltd",
            "vendor_id": "SAP-VEN-00000",
            "sku": "HW-CLONE-UNAUTH",
            "item_description": "Unauthorized Grey Market Clone",
            "quantity": 1,
            "unit_price": "150.00",
            "total_amount": "150.00",
            "currency": "USD",
            "cost_center": "8820",
            "policy_reference": "SharePoint Policy Section 4.2",
            "target_environment": "LOCAL_SIMULATOR",
            "payload_hash": ""
        },
        "events": []
    }

    res = await supervisor_node(state)
    assert res["approval_status"] == "REJECTED"
    assert res["approval_required"] is False
    assert "grey-market" in res["rejection_reason"].lower()
