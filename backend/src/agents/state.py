from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from decimal import Decimal
from pydantic import BaseModel
from src.models import PolicyCitation, VendorQuote, ProposedAction, ApprovalRequest


class AgentState(TypedDict, total=False):
    # Context Identifiers
    run_id: str
    conversation_id: str
    correlation_id: str

    # User Identity & Security Context
    user_id: str
    user_name: str
    user_email: str
    user_role: str
    user_dept: str
    user_tier: str
    spending_limit_usd: float

    # Execution State & Intent
    input_text: str
    intent: str
    plan: List[str]
    current_node: str
    status: str

    # RAG & Enterprise Evidence
    policy_citations: List[Dict[str, Any]]
    vendor_quotes: List[Dict[str, Any]]
    mcp_logistics: Optional[Dict[str, Any]]
    mcp_budget: Optional[Dict[str, Any]]

    # Proposed Transaction & Approval
    proposed_action: Optional[Dict[str, Any]]
    approval_id: Optional[str]
    approval_status: Optional[str]  # "PENDING", "APPROVED", "REJECTED"
    approval_required: bool
    rejection_reason: Optional[str]
    decision_by: Optional[str]

    # Execution & Output
    execution_result: Optional[Dict[str, Any]]
    output_text: str
    events: List[Dict[str, Any]]
