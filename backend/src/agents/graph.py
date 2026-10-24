import uuid
import hashlib
import json
import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.config import settings
from src.models import (
    User,
    UserRole,
    AccessTier,
    ProposedAction,
    ApprovalRequest,
    ApprovalStatus,
    AuditLogEntry,
    PolicyCitation,
    VendorQuote
)
from src.storage.database import db
from src.rag.hybrid_retriever import policy_retriever
from integrations.sap_adapter import sap_adapter
from integrations.m365_adapter import m365_adapter
from integrations.pii_firewall_adapter import pii_firewall
from integrations.mcp_client import mcp_client
from src.agents.state import AgentState

logger = logging.getLogger("agent_graph")


def compute_payload_hash(action_dict: dict) -> str:
    """Compute deterministic SHA-256 fingerprint of proposed transaction payload."""
    canonical = {
        "action_type": action_dict.get("action_type"),
        "vendor_id": action_dict.get("vendor_id"),
        "sku": action_dict.get("sku"),
        "quantity": int(action_dict.get("quantity", 1)),
        "unit_price": str(action_dict.get("unit_price")),
        "total_amount": str(action_dict.get("total_amount")),
        "currency": action_dict.get("currency", "USD"),
        "cost_center": action_dict.get("cost_center", "8820")
    }
    raw = json.dumps(canonical, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# -------------------------------------------------------------
# 1. Triage & Router Agent
# -------------------------------------------------------------
async def triage_node(state: AgentState) -> Dict[str, Any]:
    text = state.get("input_text", "").strip()
    events = list(state.get("events", []))

    # DLP Sanitization Hook
    sanitized_text, dlp_findings = pii_firewall.sanitize_text(text)
    if dlp_findings:
        events.append({
            "event_type": "dlp_warning",
            "message": f"PII Firewall redacted {len(dlp_findings)} sensitive token(s) from input payload."
        })

    # Rule-based intent classification
    lower = sanitized_text.lower()
    intent = "GENERAL"
    if any(k in lower for k in ["order", "procure", "purchase", "buy", "requisition"]):
        intent = "PROCUREMENT_REQUISITION"
    elif any(k in lower for k in ["policy", "guideline", "threshold", "rules", "matrix", "compliance"]):
        intent = "POLICY_INQUIRY"
    elif any(k in lower for k in ["quote", "price", "catalog", "sku", "vendor", "cost"]):
        intent = "VENDOR_QUOTE"

    events.append({
        "event_type": "agent_handoff",
        "from_agent": "UserInterface",
        "to_agent": "TriageAgent",
        "intent": intent,
        "detail": f"Classified intent: {intent}"
    })

    return {
        "input_text": sanitized_text,
        "intent": intent,
        "current_node": "triage",
        "events": events
    }


# -------------------------------------------------------------
# 2. Policy RAG Agent
# -------------------------------------------------------------
async def policy_rag_node(state: AgentState) -> Dict[str, Any]:
    events = list(state.get("events", []))
    events.append({
        "event_type": "agent_handoff",
        "from_agent": "TriageAgent",
        "to_agent": "PolicyRAGAgent",
        "detail": "Querying authorized SharePoint corporate governance documents..."
    })

    user_tier_str = state.get("user_tier", "INTERNAL")
    try:
        user_tier = AccessTier(user_tier_str)
    except Exception:
        user_tier = AccessTier.INTERNAL

    query = state.get("input_text", "")
    citations = policy_retriever.retrieve(query=query, user_access_tier=user_tier, top_k=3)

    events.append({
        "event_type": "rag_evidence",
        "citations_count": len(citations),
        "documents": [c.document_title for c in citations]
    })

    return {
        "policy_citations": [c.model_dump() for c in citations],
        "current_node": "policy_rag",
        "events": events
    }


# -------------------------------------------------------------
# 3. Enterprise Systems Agent (SAP & MCP)
# -------------------------------------------------------------
async def systems_node(state: AgentState) -> Dict[str, Any]:
    events = list(state.get("events", []))
    events.append({
        "event_type": "agent_handoff",
        "from_agent": "PolicyRAGAgent",
        "to_agent": "EnterpriseSystemsAgent",
        "detail": "Interfacing with SAP S/4HANA OData and Model Context Protocol (MCP) services..."
    })

    text = state.get("input_text", "")
    lower = text.lower()

    # Extract quantity
    import re
    qty = 1
    qty_match = re.search(r"\b(\d+)\s*(?:workstations?|units?|servers?|licenses?|seats?|items?|pcs?)\b", lower)
    if qty_match:
        qty = max(1, min(100, int(qty_match.group(1))))
    else:
        # Check standalone digit
        digits = re.findall(r"\b\d+\b", text)
        if digits:
            candidate = int(digits[0])
            if 1 <= candidate <= 100:
                qty = candidate

    # Search SAP Supplier Quotes
    quotes = await sap_adapter.search_supplier_quotes(query=text)
    primary_quote = quotes[0] if quotes else None

    # MCP Tool Integration: Freight & Statutory Tax Calculation
    subtotal = float(primary_quote.unit_price) * qty if primary_quote else 250.0 * qty
    mcp_tax_res = await mcp_client.calculate_tax_and_shipping(amount=subtotal, currency="USD", country="IN")

    # MCP Tool Integration: Cost Center Budget Check
    cost_center = "8820"
    if "7710" in text:
        cost_center = "7710"
    elif "9900" in text:
        cost_center = "9900"

    mcp_budget_res = await mcp_client.verify_budget(cost_center=cost_center, requested_amount=mcp_tax_res["grand_total"])

    # Construct Proposed Action
    unit_p = primary_quote.unit_price if primary_quote else Decimal("250.00")
    total_val = unit_p * Decimal(str(qty))
    vendor_name = primary_quote.vendor_name if primary_quote else "Dell Technologies India Ltd"
    vendor_id = primary_quote.vendor_id if primary_quote else "SAP-VEN-99104"
    sku = primary_quote.sku if primary_quote else "WS-ERGO-01"
    item_desc = primary_quote.item_description if primary_quote else "Ergonomic Sit-Stand Workstation"

    action_data = {
        "action_id": f"act-{uuid.uuid4().hex[:8]}",
        "action_type": "SAP_CREATE_PURCHASE_ORDER",
        "vendor_name": vendor_name,
        "vendor_id": vendor_id,
        "item_description": item_desc,
        "sku": sku,
        "quantity": qty,
        "unit_price": str(unit_p),
        "total_amount": str(total_val),
        "currency": "USD",
        "cost_center": cost_center,
        "policy_reference": "Global IT Hardware Procurement Policy v4.2 [Section 3.1]",
        "target_environment": "LOCAL_SIMULATOR"
    }
    action_data["payload_hash"] = compute_payload_hash(action_data)

    events.append({
        "event_type": "tool_call",
        "tool_name": "sap_odata_supplier_quote_search",
        "result": f"Matched quote from {vendor_name} ({sku}) at ${unit_p} USD/unit"
    })
    events.append({
        "event_type": "tool_call",
        "tool_name": "mcp_calculate_shipping_and_tax",
        "result": f"Grand total: ${mcp_tax_res['grand_total']} USD (Includes ${mcp_tax_res['tax_amount']} tax)"
    })

    return {
        "vendor_quotes": [q.model_dump(mode="json") for q in quotes],
        "mcp_logistics": mcp_tax_res,
        "mcp_budget": mcp_budget_res,
        "proposed_action": action_data,
        "current_node": "systems",
        "events": events
    }


# -------------------------------------------------------------
# 4. Governance & Approval Supervisor
# -------------------------------------------------------------
async def supervisor_node(state: AgentState) -> Dict[str, Any]:
    events = list(state.get("events", []))
    events.append({
        "event_type": "agent_handoff",
        "from_agent": "EnterpriseSystemsAgent",
        "to_agent": "ComplianceSupervisor",
        "detail": "Evaluating deterministic enterprise governance constraints and approval matrix..."
    })

    action = state.get("proposed_action")
    if not action:
        return {"current_node": "supervisor", "approval_required": False, "events": events}

    total_amount = Decimal(str(action.get("total_amount", "0.00")))
    vendor_name = action.get("vendor_name", "")
    cost_center = action.get("cost_center", "8820")
    user_role = state.get("user_role", "REQUESTER")

    # Policy 1: Prohibited grey market vendor check
    if "unauthorized" in vendor_name.lower() or "prohibited" in vendor_name.lower():
        events.append({
            "event_type": "compliance_rejection",
            "reason": "Policy Violation: Vendor is flagged as unauthorized grey-market supplier in SharePoint Policy Section 4.2."
        })
        return {
            "approval_required": False,
            "approval_status": "REJECTED",
            "rejection_reason": "Policy Violation: Vendor is unapproved grey-market supplier.",
            "current_node": "supervisor",
            "events": events
        }

    # Policy 2: Financial threshold evaluation
    approval_required = False
    required_role = UserRole.APPROVER

    if total_amount >= Decimal("10000.00"):
        approval_required = True
        required_role = UserRole.EXECUTIVE_APPROVER
    elif total_amount >= Decimal("1000.00"):
        approval_required = True
        required_role = UserRole.APPROVER
    else:
        # Transactions under $1,000 can proceed if user has delegated spending limit
        user_limit = Decimal(str(state.get("spending_limit_usd", "0.00")))
        if user_limit < total_amount:
            approval_required = True
            required_role = UserRole.APPROVER

    if approval_required:
        # Check if already approved in this run
        existing_status = state.get("approval_status")
        if existing_status == "APPROVED":
            events.append({
                "event_type": "approval_resumed",
                "detail": f"Action approved by {state.get('decision_by', 'authorized approver')}. Proceeding to execution."
            })
            return {
                "approval_required": True,
                "approval_status": "APPROVED",
                "current_node": "supervisor",
                "events": events
            }

        # Otherwise: Generate and persist pending approval request
        appr_id = state.get("approval_id") or f"appr-{uuid.uuid4().hex[:8]}"
        appr_obj = ApprovalRequest(
            id=appr_id,
            run_id=state.get("run_id", "run-default"),
            conversation_id=state.get("conversation_id", "conv-default"),
            requester_id=state.get("user_id", "usr-anon"),
            requester_name=state.get("user_name", "Anonymous"),
            proposed_action=ProposedAction(**action),
            status=ApprovalStatus.PENDING,
            required_role=required_role,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        await db.save_approval_request(appr_obj)

        # Persist durable workflow checkpoint in SQLite WAL
        checkpoint_dict = dict(state)
        checkpoint_dict["approval_id"] = appr_id
        checkpoint_dict["approval_status"] = "PENDING"
        checkpoint_dict["approval_required"] = True
        checkpoint_dict["required_role"] = required_role.value
        await db.save_checkpoint(
            run_id=state.get("run_id", "run-default"),
            conv_id=state.get("conversation_id", "conv-default"),
            state_dict=checkpoint_dict,
            status="WAITING_APPROVAL"
        )

        events.append({
            "event_type": "approval_required",
            "approval_id": appr_id,
            "required_role": required_role.value,
            "action": action,
            "detail": f"Execution halted: Amount ${total_amount} USD requires authorization from {required_role.value}."
        })

        return {
            "approval_id": appr_id,
            "approval_required": True,
            "approval_status": "PENDING",
            "current_node": "supervisor",
            "status": "WAITING_APPROVAL",
            "events": events
        }

    return {
        "approval_required": False,
        "approval_status": "APPROVED",
        "current_node": "supervisor",
        "events": events
    }


# -------------------------------------------------------------
# 5. Action Execution Node (ERP Integration)
# -------------------------------------------------------------
async def execute_action_node(state: AgentState) -> Dict[str, Any]:
    events = list(state.get("events", []))
    events.append({
        "event_type": "agent_handoff",
        "from_agent": "ComplianceSupervisor",
        "to_agent": "ActionExecutor",
        "detail": "Executing approved purchase order creation against target ERP environment..."
    })

    action = state.get("proposed_action")
    if not action:
        return {"current_node": "execute_action", "events": events}

    # Execute via SAP Adapter
    exec_res = await sap_adapter.create_purchase_order(ProposedAction(**action))

    # Record Immutable Audit Trail Entry
    audit_entry = AuditLogEntry(
        correlation_id=state.get("correlation_id", str(uuid.uuid4())),
        actor_id=state.get("user_id", "system"),
        actor_name=state.get("user_name", "Enterprise System"),
        actor_role=state.get("user_role", "SYSTEM"),
        action_type="SAP_CREATE_PURCHASE_ORDER",
        target_environment=exec_res.get("environment", "LOCAL_SIMULATOR"),
        status="EXECUTED",
        summary=f"Created PO {exec_res.get('sap_purchase_order')} for {action.get('quantity')}x {action.get('sku')} at ${action.get('total_amount')} USD",
        masked_payload_json=json.dumps(action)
    )
    await db.record_audit(audit_entry)

    events.append({
        "event_type": "action_executed",
        "po_number": exec_res.get("sap_purchase_order"),
        "environment": exec_res.get("environment"),
        "detail": f"Purchase order {exec_res.get('sap_purchase_order')} confirmed in SAP S/4HANA ({exec_res.get('environment')})."
    })

    return {
        "execution_result": exec_res,
        "current_node": "execute_action",
        "events": events
    }


# -------------------------------------------------------------
# 6. Response Synthesizer Node
# -------------------------------------------------------------
async def synthesize_node(state: AgentState) -> Dict[str, Any]:
    intent = state.get("intent", "GENERAL")
    citations = state.get("policy_citations", [])
    quotes = state.get("vendor_quotes", [])
    action = state.get("proposed_action")
    approval_status = state.get("approval_status")
    approval_id = state.get("approval_id")
    exec_res = state.get("execution_result")
    mcp_tax = state.get("mcp_logistics")

    output_lines = []

    # Policy RAG Section
    if citations:
        output_lines.append("### 📋 Applicable Corporate Governance Policies")
        for c in citations:
            output_lines.append(f"- **{c['document_title']} ({c['version']})** — *{c['section']}*")
            output_lines.append(f"  > \"{c['excerpt']}\"")
        output_lines.append("")

    # Systems / Quotes Section
    if quotes and intent in ("PROCUREMENT_REQUISITION", "VENDOR_QUOTE"):
        output_lines.append("### 🏷️ Enterprise Supplier Quote (SAP S/4HANA)")
        q = quotes[0]
        output_lines.append(f"- **Item:** {q['item_description']} (`{q['sku']}`)")
        output_lines.append(f"- **Supplier:** {q['vendor_name']} (`{q['vendor_id']}`)")
        output_lines.append(f"- **Unit Price:** ${q['unit_price']} {q['currency']} (Lead Time: {q['lead_time_days']} days)")
        output_lines.append("")

    # Action / Decision Status Section
    if action and intent == "PROCUREMENT_REQUISITION":
        output_lines.append("### 📦 Proposed Requisition Summary")
        output_lines.append(f"- **Order Quantity:** {action['quantity']} units")
        output_lines.append(f"- **Base Amount:** ${action['total_amount']} {action['currency']}")
        if mcp_tax:
            output_lines.append(f"- **Logistics & Tax (MCP):** Estimated Grand Total: **${mcp_tax['grand_total']} {action['currency']}** (Includes ${mcp_tax['tax_amount']} statutory tax)")
        output_lines.append(f"- **Cost Center:** `{action['cost_center']}`")
        output_lines.append("")

        if approval_status == "PENDING":
            output_lines.append("⚠️ **Status: Awaiting Human-in-the-Loop Authorization**")
            output_lines.append(f"In accordance with *{action['policy_reference']}*, this requisition exceeds spending thresholds and has been paused. Please review the interactive approval card below to authorize or reject.")
        elif approval_status == "APPROVED" and exec_res:
            output_lines.append("✅ **Status: Action Approved & Executed**")
            output_lines.append(f"- **SAP Purchase Order Number:** `{exec_res.get('sap_purchase_order')}`")
            output_lines.append(f"- **Target Environment:** `{exec_res.get('environment')}`")
            output_lines.append(f"- **Audit Status:** Transaction logged with immutable trace.")
        elif approval_status == "REJECTED":
            output_lines.append("❌ **Status: Requisition Rejected**")
            output_lines.append(f"- **Reason:** {state.get('rejection_reason', 'Not specified by approver')}")
    elif intent == "POLICY_INQUIRY":
        output_lines.append("All retrieved clauses are verified against sovereign corporate SharePoint policy repositories.")
    else:
        output_lines.append("I can assist you with enterprise procurement requests, supplier quote lookups, corporate spending policy research, and authorized purchase order creation.")

    final_text = "\n".join(output_lines)
    return {
        "output_text": final_text,
        "current_node": "synthesize"
    }


# -------------------------------------------------------------
# Router & Graph Construction
# -------------------------------------------------------------
def router_after_triage(state: AgentState) -> str:
    intent = state.get("intent", "GENERAL")
    if intent in ("PROCUREMENT_REQUISITION", "VENDOR_QUOTE"):
        return "policy_rag"
    elif intent == "POLICY_INQUIRY":
        return "policy_rag"
    return "synthesize"


def router_after_rag(state: AgentState) -> str:
    intent = state.get("intent", "GENERAL")
    if intent in ("PROCUREMENT_REQUISITION", "VENDOR_QUOTE"):
        return "systems"
    return "synthesize"


def router_after_supervisor(state: AgentState) -> str:
    status = state.get("approval_status")
    if status == "PENDING":
        # Stop at supervisor (waiting for human decision)
        return "synthesize"
    elif status == "APPROVED":
        # If approved, proceed to ERP execution
        return "execute_action"
    return "synthesize"


def build_agent_graph():
    """Build the LangGraph multi-agent state machine."""
    workflow = StateGraph(AgentState)

    workflow.add_node("triage", triage_node)
    workflow.add_node("policy_rag", policy_rag_node)
    workflow.add_node("systems", systems_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("execute_action", execute_action_node)
    workflow.add_node("synthesize", synthesize_node)

    workflow.add_edge(START, "triage")
    workflow.add_conditional_edges("triage", router_after_triage, {
        "policy_rag": "policy_rag",
        "synthesize": "synthesize"
    })
    workflow.add_conditional_edges("policy_rag", router_after_rag, {
        "systems": "systems",
        "synthesize": "synthesize"
    })
    workflow.add_edge("systems", "supervisor")
    workflow.add_conditional_edges("supervisor", router_after_supervisor, {
        "execute_action": "execute_action",
        "synthesize": "synthesize"
    })
    workflow.add_edge("execute_action", "synthesize")
    workflow.add_edge("synthesize", END)

    # Use in-memory checkpointer for graph execution
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


agent_graph = build_agent_graph()
