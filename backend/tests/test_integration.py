import pytest
import asyncio
from decimal import Decimal
from src.storage.database import db
from src.agents.graph import agent_graph, execute_action_node, synthesize_node, compute_payload_hash
from src.agents.state import AgentState
from src.models import (
    User,
    UserRole,
    AccessTier,
    Conversation,
    Message,
    ApprovalRequest,
    ApprovalStatus,
    ProposedAction,
    AuditLogEntry
)


@pytest.mark.asyncio
async def test_sqlite_wal_database_lifecycle():
    await db.init_db()

    # 1. Create conversation
    conv = Conversation(
        id="conv-int-01",
        user_id="usr-alice-01",
        title="Integration Test Session"
    )
    await db.create_conversation(conv)
    fetched = await db.get_conversation("conv-int-01")
    assert fetched is not None
    assert fetched.title == "Integration Test Session"

    # 2. Add message
    msg = Message(
        id="msg-int-01",
        conversation_id="conv-int-01",
        sender="user",
        content="Requisition 5 ergonomic workstations"
    )
    await db.add_message(msg)
    messages = await db.get_messages("conv-int-01")
    assert len(messages) == 1
    assert messages[0].content == "Requisition 5 ergonomic workstations"


@pytest.mark.asyncio
async def test_end_to_end_agent_graph_execution_and_pause():
    await db.init_db()

    run_id = "run-e2e-01"
    conv_id = "conv-e2e-01"

    initial_state: AgentState = {
        "run_id": run_id,
        "conversation_id": conv_id,
        "correlation_id": "corr-e2e-01",
        "user_id": "usr-alice-01",
        "user_name": "Alice Chen",
        "user_email": "alice.requester@company.internal",
        "user_role": "REQUESTER",
        "user_dept": "IT Systems Engineering",
        "user_tier": "INTERNAL",
        "spending_limit_usd": 0.00,
        "input_text": "Please requisition 5 ergonomic workstations for IT engineering team.",
        "events": []
    }

    # Execute LangGraph
    final_state = await agent_graph.ainvoke(initial_state, config={"configurable": {"thread_id": conv_id}})

    # Verify execution paused for approval
    assert final_state["intent"] == "PROCUREMENT_REQUISITION"
    assert final_state["approval_required"] is True
    assert final_state["approval_status"] == "PENDING"
    assert final_state["approval_id"] is not None
    assert len(final_state["policy_citations"]) >= 1
    assert len(final_state["vendor_quotes"]) >= 1

    # Verify approval was persisted to database
    appr = await db.get_approval(final_state["approval_id"])
    assert appr is not None
    assert appr.status == ApprovalStatus.PENDING
    assert appr.requester_id == "usr-alice-01"

    # Verify durable checkpoint was persisted to SQLite WAL
    checkpoint = await db.get_checkpoint(run_id)
    assert checkpoint is not None
    assert checkpoint["status"] == "WAITING_APPROVAL"


@pytest.mark.asyncio
async def test_workflow_resumption_and_erp_execution_surviving_restart():
    await db.init_db()

    run_id = "run-restart-01"
    conv_id = "conv-restart-01"

    action_data = {
        "action_id": "act-restart-01",
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_name": "Dell Technologies India Ltd",
        "vendor_id": "SAP-VEN-99104",
        "sku": "WS-ERGO-01",
        "item_description": "Ergonomic Sit-Stand Workstation",
        "quantity": 5,
        "unit_price": "450.00",
        "total_amount": "2250.00",
        "currency": "USD",
        "cost_center": "8820",
        "policy_reference": "Spending Matrix v5.1 Section 2.1",
        "target_environment": "LOCAL_SIMULATOR",
        "payload_hash": ""
    }
    action_data["payload_hash"] = compute_payload_hash(action_data)

    appr_obj = ApprovalRequest(
        id="appr-restart-01",
        run_id=run_id,
        conversation_id=conv_id,
        requester_id="usr-alice-01",
        requester_name="Alice Chen",
        proposed_action=ProposedAction(**action_data),
        status=ApprovalStatus.PENDING,
        required_role=UserRole.APPROVER
    )
    await db.save_approval_request(appr_obj)

    # Save checkpoint to simulate pre-restart state
    saved_state = {
        "run_id": run_id,
        "conversation_id": conv_id,
        "correlation_id": "corr-restart-01",
        "user_id": "usr-alice-01",
        "user_name": "Alice Chen",
        "intent": "PROCUREMENT_REQUISITION",
        "proposed_action": action_data,
        "approval_id": "appr-restart-01",
        "approval_status": "PENDING",
        "events": []
    }
    await db.save_checkpoint(run_id, conv_id, saved_state, status="WAITING_APPROVAL")

    # SIMULATE SERVER RESTART: Fetch checkpoint fresh from disk
    restored_checkpoint = await db.get_checkpoint(run_id)
    assert restored_checkpoint is not None

    # Simulate Approver decision
    restored_state: AgentState = dict(restored_checkpoint)
    restored_state["approval_status"] = "APPROVED"
    restored_state["decision_by"] = "Bob Martinez"

    # Resume execution
    exec_res = await execute_action_node(restored_state)
    restored_state.update(exec_res)

    assert restored_state["execution_result"] is not None
    assert restored_state["execution_result"]["sap_purchase_order"].startswith("PO-")
    assert restored_state["execution_result"]["status"] == "SUCCESS"

    # Synthesize post-approval confirmation
    synth_res = await synthesize_node(restored_state)
    assert "SAP Purchase Order Number" in synth_res["output_text"]
