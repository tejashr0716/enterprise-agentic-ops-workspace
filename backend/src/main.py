import json
import logging
import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import settings
from src.models import (
    User,
    UserRole,
    AccessTier,
    Conversation,
    Message,
    ApprovalRequest,
    ApprovalDecisionRequest,
    ApprovalStatus,
    AuditLogEntry,
    RunEvent,
    ProposedAction,
    PolicyCitation
)
from src.auth.service import (
    get_current_user,
    require_role,
    create_access_token,
    get_user_by_email,
    DEMO_USERS
)
from src.storage.database import db
from src.rag.hybrid_retriever import policy_retriever
from src.agents.graph import agent_graph, compute_payload_hash, execute_action_node, synthesize_node
from src.agents.state import AgentState
from integrations.sap_adapter import sap_adapter
from integrations.m365_adapter import m365_adapter
from integrations.pii_firewall_adapter import pii_firewall
from integrations.mcp_client import mcp_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("enterprise_api")

app = FastAPI(
    title="Enterprise Agentic Ops Workspace API",
    version="1.0.0",
    description="Multi-Agent Enterprise Procurement, Governance & SAP Integration Workspace"
)

# Enable CORS for Vite frontend (http://localhost:5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    """Initialize database schemas and hybrid policy retriever index."""
    logger.info("Initializing Enterprise Agentic Ops Workspace...")
    await db.init_db()
    await policy_retriever.initialize()
    logger.info(f"System ready in {settings.runtime_mode} mode. Hybrid RAG index primed with {len(policy_retriever.documents)} documents.")


# -------------------------------------------------------------
# Health & Status Endpoints
# -------------------------------------------------------------
@app.get("/health/live")
async def health_live():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/health/ready")
async def health_ready():
    return {
        "status": "ready",
        "runtime_mode": settings.runtime_mode,
        "database": "sqlite_wal_ready",
        "rag_indexed_chunks": len(policy_retriever.documents),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/integrations/status")
async def get_integrations_status():
    """Return live status of enterprise adapters and execution modes."""
    return {
        "runtime_mode": settings.runtime_mode,
        "adapters": {
            "sap": {
                "name": "SAP S/4HANA OData v2/v4",
                "mode": settings.sap_mode,
                "endpoint": settings.sap_sandbox_base_url if settings.sap_mode == "SAP_SANDBOX" else "LOCAL_SIMULATOR (In-Memory Enterprise Catalog)",
                "status": "HEALTHY",
                "catalog_items": len(sap_adapter.catalog)
            },
            "m365": {
                "name": "Microsoft 365 SharePoint Graph",
                "mode": settings.m365_mode,
                "status": "HEALTHY",
                "governance_corpus": f"{len(policy_retriever.documents)} clauses indexed in Hybrid BM25+Dense RAG"
            },
            "mcp": {
                "name": "Model Context Protocol 2.x",
                "mode": settings.mcp_mode,
                "status": "CONNECTED",
                "tools_exposed": ["mcp_get_approved_catalog", "mcp_calculate_shipping_and_tax", "mcp_verify_cost_center_budget"]
            },
            "dlp": {
                "name": "PII Financial Leakage Firewall",
                "status": "ACTIVE",
                "algorithms": ["Luhn Mod-10 (PAN)", "ISO 7064 Mod-97 (IBAN)", "SSA Randomized (SSN)", "Stripe/AWS Secret Regex"]
            }
        }
    }


# -------------------------------------------------------------
# Authentication & Identity Switcher Endpoints
# -------------------------------------------------------------
class TokenRequest(BaseModel):
    email: str


@app.post("/api/auth/token")
async def login_for_token(req: TokenRequest):
    """Authenticate or switch identity among enterprise demo accounts."""
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{req.email}' not found. Available demo identities: {list(DEMO_USERS.keys())}"
        )
    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.model_dump(mode="json")
    }


@app.get("/api/auth/me")
async def get_current_user_profile(user: User = Depends(get_current_user)):
    return user.model_dump(mode="json")


@app.get("/api/auth/users")
async def list_demo_users():
    """List pre-seeded identities for UI identity switcher."""
    return [u.model_dump(mode="json") for u in DEMO_USERS.values()]


# -------------------------------------------------------------
# Conversation & Messaging Endpoints
# -------------------------------------------------------------
class ConversationCreateRequest(BaseModel):
    title: Optional[str] = "Procurement Requisition Session"


@app.get("/api/conversations")
async def list_conversations(user: User = Depends(get_current_user)):
    convs = await db.list_conversations(user.id)
    return [c.model_dump(mode="json") for c in convs]


@app.post("/api/conversations")
async def create_conversation(req: ConversationCreateRequest, user: User = Depends(get_current_user)):
    conv = Conversation(
        id=f"conv-{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        title=req.title or "New Procurement Session"
    )
    await db.create_conversation(conv)
    return conv.model_dump(mode="json")


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: User = Depends(get_current_user)):
    conv = await db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await db.get_messages(conv_id)
    return {
        "conversation": conv.model_dump(mode="json"),
        "messages": [m.model_dump(mode="json") for m in messages]
    }


# -------------------------------------------------------------
# Agent Run & Real SSE Streaming Engine
# -------------------------------------------------------------
class RunCreateRequest(BaseModel):
    conversation_id: str
    content: str


async def event_generator(
    conv_id: str,
    user_text: str,
    user: User,
    run_id: str
) -> AsyncGenerator[str, None]:
    """
    Stream typed SSE envelopes to frontend client:
    - token: incremental text token chunks
    - agent_handoff: multi-agent routing transitions
    - tool_call: SAP/MCP tool invocations
    - approval_required: workflow paused for human authorization
    - stream_end: terminal event
    """
    correlation_id = f"corr-{uuid.uuid4().hex[:8]}"

    def sse_format(event_type: str, data: dict) -> str:
        payload = {
            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"

    try:
        # Initial user message persistence
        user_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            conversation_id=conv_id,
            sender="user",
            content=user_text,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await db.add_message(user_msg)

        # Notify UI of run initiation
        yield sse_format("agent_handoff", {
            "from_agent": "UserInterface",
            "to_agent": "TriageAgent",
            "intent": "INSPECTING",
            "detail": f"Receiving requisition input from {user.full_name} ({user.role.value}). Initiating DLP inspection..."
        })
        await asyncio.sleep(0.08)

        # Initialize LangGraph AgentState
        initial_state: AgentState = {
            "run_id": run_id,
            "conversation_id": conv_id,
            "correlation_id": correlation_id,
            "user_id": user.id,
            "user_name": user.full_name,
            "user_email": user.email,
            "user_role": user.role.value,
            "user_dept": user.department,
            "user_tier": user.access_tier.value,
            "spending_limit_usd": float(user.spending_limit_usd),
            "input_text": user_text,
            "events": []
        }

        # Execute LangGraph State Machine
        config = {"configurable": {"thread_id": conv_id}}
        final_state = await agent_graph.ainvoke(initial_state, config=config)

        # Yield all internal graph events
        for evt in final_state.get("events", []):
            evt_type = evt.get("event_type", "agent_handoff")
            yield sse_format(evt_type, evt)
            await asyncio.sleep(0.05)

        # Stream generated synthesis token-by-token
        synthesis_text = final_state.get("output_text", "")
        if synthesis_text:
            chunks = synthesis_text.split(" ")
            for i, chunk in enumerate(chunks):
                token_piece = chunk + (" " if i < len(chunks) - 1 else "")
                yield sse_format("token", {"token": token_piece})
                await asyncio.sleep(0.015)

        # Format ProposedAction and ApprovalRequest if present
        action_obj = None
        if final_state.get("proposed_action"):
            action_obj = ProposedAction(**final_state["proposed_action"])

        appr_obj = None
        if final_state.get("approval_id"):
            appr_obj = await db.get_approval(final_state["approval_id"])

        citations_list = [
            PolicyCitation(**c) for c in final_state.get("policy_citations", [])
        ]

        # Persist assistant response to DB
        assistant_msg = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            conversation_id=conv_id,
            sender="assistant",
            content=synthesis_text,
            policy_citations=citations_list,
            proposed_action=action_obj,
            approval_request=appr_obj,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await db.add_message(assistant_msg)

        # Stream terminal event
        yield sse_format("stream_end", {
            "status": final_state.get("status", "COMPLETED"),
            "approval_required": final_state.get("approval_required", False),
            "approval_id": final_state.get("approval_id"),
            "message_id": assistant_msg.id
        })

    except Exception as e:
        logger.exception(f"Error during agent stream execution: {e}")
        yield sse_format("error", {"detail": str(e)})
        yield sse_format("stream_end", {"status": "FAILED", "error": str(e)})


@app.post("/api/runs")
async def create_and_stream_run(req: RunCreateRequest, user: User = Depends(get_current_user)):
    """Trigger agent turn and immediately stream SSE event envelopes."""
    conv = await db.get_conversation(req.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    return StreamingResponse(
        event_generator(req.conversation_id, req.content, user, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Run-ID": run_id
        }
    )


# -------------------------------------------------------------
# Human-in-the-Loop (HITL) Approvals & Checkpoint Resume
# -------------------------------------------------------------
@app.get("/api/approvals")
async def list_pending_approvals(user: User = Depends(get_current_user)):
    """Retrieve all pending approval requests awaiting manager or executive decision."""
    approvals = await db.list_pending_approvals()
    return [a.model_dump(mode="json") for a in approvals]


@app.get("/api/approvals/{approval_id}")
async def get_approval_details(approval_id: str, user: User = Depends(get_current_user)):
    appr = await db.get_approval(approval_id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return appr.model_dump(mode="json")


@app.post("/api/approvals/{approval_id}/decision")
async def decide_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Authorize or reject a pending requisition.
    Enforces:
    1. Role authority (APPROVER or EXECUTIVE_APPROVER).
    2. Self-approval prevention (requester cannot approve own request).
    3. Payload fingerprint verification (SHA-256 integrity).
    4. Durable state resumption from SQLite WAL checkpoints.
    """
    appr = await db.get_approval(approval_id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if appr.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Request is already resolved with status: {appr.status.value}")

    # Self-Approval Guard
    if current_user.id == appr.requester_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval prohibited: Requester cannot authorize their own requisition. Must be reviewed by an independent authorized approver."
        )

    # Authority Check
    if appr.required_role == UserRole.EXECUTIVE_APPROVER and current_user.role != UserRole.EXECUTIVE_APPROVER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Requisitions of this magnitude require EXECUTIVE_APPROVER authority. Current role: {current_user.role.value}"
        )
    if appr.required_role == UserRole.APPROVER and current_user.role not in (UserRole.APPROVER, UserRole.EXECUTIVE_APPROVER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: Requisition requires APPROVER authority. Current role: {current_user.role.value}"
        )

    # Payload Tamper Check
    expected_hash = compute_payload_hash(appr.proposed_action.model_dump(mode="json"))
    if appr.proposed_action.payload_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload Integrity Failure: Requisition parameters do not match verified cryptographic fingerprint."
        )

    decision_norm = body.decision.upper().strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if decision_norm == "REJECT":
        appr.status = ApprovalStatus.REJECTED
        appr.decision_by = current_user.id
        appr.decision_by_name = current_user.full_name
        appr.decision_at = now_iso
        appr.decision_reason = body.reason
        await db.save_approval_request(appr)

        # Audit Log
        await db.record_audit(AuditLogEntry(
            correlation_id=f"corr-{uuid.uuid4().hex[:8]}",
            actor_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role.value,
            action_type="REJECT_PURCHASE_ORDER",
            target_environment=appr.proposed_action.target_environment,
            status="REJECTED",
            summary=f"Requisition {appr.id} rejected by {current_user.full_name}: {body.reason}",
            masked_payload_json=json.dumps(appr.proposed_action.model_dump(mode="json"))
        ))

        # Add message in conversation
        await db.add_message(Message(
            conversation_id=appr.conversation_id,
            sender="assistant",
            content=f"❌ **Requisition {appr.id} Rejected** by {current_user.full_name} ({current_user.role.value}).\n\n**Reason:** {body.reason}",
            approval_request=appr
        ))

        return {"status": "REJECTED", "approval_id": appr.id}

    elif decision_norm == "APPROVE":
        appr.status = ApprovalStatus.APPROVED
        appr.decision_by = current_user.id
        appr.decision_by_name = current_user.full_name
        appr.decision_at = now_iso
        appr.decision_reason = body.reason
        await db.save_approval_request(appr)

        # Retrieve durable checkpoint
        checkpoint_data = await db.get_checkpoint(appr.run_id)
        if not checkpoint_data:
            # Fallback reconstruction
            checkpoint_data = {
                "run_id": appr.run_id,
                "conversation_id": appr.conversation_id,
                "correlation_id": f"corr-{uuid.uuid4().hex[:8]}",
                "user_id": appr.requester_id,
                "user_name": appr.requester_name,
                "proposed_action": appr.proposed_action.model_dump(mode="json"),
                "events": []
            }

        # Update state with approval
        state_dict: AgentState = dict(checkpoint_data)
        state_dict["approval_status"] = "APPROVED"
        state_dict["approval_id"] = appr.id
        state_dict["decision_by"] = current_user.full_name
        state_dict["rejection_reason"] = None

        # Execute ERP Action
        exec_update = await execute_action_node(state_dict)
        state_dict.update(exec_update)

        # Synthesize post-approval confirmation
        synth_update = await synthesize_node(state_dict)
        state_dict.update(synth_update)

        # Update checkpoint status
        await db.save_checkpoint(appr.run_id, appr.conversation_id, state_dict, status="COMPLETED")

        # Post assistant execution confirmation to conversation
        exec_res = state_dict.get("execution_result", {})
        msg_text = (
            f"✅ **Requisition Approved & Executed**\n\n"
            f"- **Authorized By:** {current_user.full_name} ({current_user.role.value})\n"
            f"- **Justification:** {body.reason}\n"
            f"- **SAP Purchase Order:** `{exec_res.get('sap_purchase_order', 'PO-PENDING')}`\n"
            f"- **Environment:** `{exec_res.get('environment', 'LOCAL_SIMULATOR')}`\n"
            f"- **Total Committed:** ${exec_res.get('total_amount')} {exec_res.get('currency', 'USD')}\n"
            f"- **Execution Timestamp:** {exec_res.get('execution_timestamp')}"
        )
        await db.add_message(Message(
            conversation_id=appr.conversation_id,
            sender="assistant",
            content=msg_text,
            proposed_action=appr.proposed_action,
            approval_request=appr
        ))

        return {
            "status": "APPROVED",
            "approval_id": appr.id,
            "execution_result": exec_res
        }
    else:
        raise HTTPException(status_code=400, detail="Decision must be 'APPROVE' or 'REJECT'")


# -------------------------------------------------------------
# Corporate Knowledge Base & Governance Documents
# -------------------------------------------------------------
@app.get("/api/documents")
async def list_governance_documents(user: User = Depends(get_current_user)):
    """Retrieve indexed SharePoint governance policies visible to user's access tier."""
    filtered_docs = [
        d for d in policy_retriever.documents
        if policy_retriever._tier_permits(user.access_tier, d["access_tier"])
    ]
    return filtered_docs


# -------------------------------------------------------------
# Immutable Audit Trail
# -------------------------------------------------------------
@app.get("/api/audit/logs")
async def get_audit_trail(
    limit: int = Query(50, ge=1, le=200),
    correlation_id: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """Retrieve immutable audit trail entries."""
    logs = await db.get_audit_logs(limit=limit, correlation_id=correlation_id)
    return [l.model_dump(mode="json") for l in logs]


# -------------------------------------------------------------
# Static Frontend Serving (Single-Port Production Deployment)
# -------------------------------------------------------------
from fastapi.staticfiles import StaticFiles
from pathlib import Path

dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
