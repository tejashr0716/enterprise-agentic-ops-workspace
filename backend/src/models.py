import uuid
from decimal import Decimal
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    REQUESTER = "REQUESTER"
    APPROVER = "APPROVER"
    EXECUTIVE_APPROVER = "EXECUTIVE_APPROVER"
    EXTERNAL_CONTRACTOR = "EXTERNAL_CONTRACTOR"


class AccessTier(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"


class User(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    department: str
    spending_limit_usd: Decimal = Decimal("0.00")
    access_tier: AccessTier = AccessTier.INTERNAL


class PolicyCitation(BaseModel):
    document_id: str
    document_title: str
    version: str
    section: str
    excerpt: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    access_tier: AccessTier = AccessTier.INTERNAL


class VendorQuote(BaseModel):
    quote_id: str
    vendor_id: str
    vendor_name: str
    sku: str
    item_description: str
    unit_price: Decimal
    currency: str = "USD"
    lead_time_days: int
    source_system: str = "SAP S/4HANA (DEMO DATA)"


class ProposedAction(BaseModel):
    action_id: str = Field(default_factory=lambda: f"act-{uuid.uuid4().hex[:8]}")
    action_type: str = "SAP_CREATE_PURCHASE_ORDER"
    vendor_name: str
    vendor_id: str
    item_description: str
    sku: str
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., gt=0)
    total_amount: Decimal = Field(..., gt=0)
    currency: str = "USD"
    cost_center: str
    policy_reference: str
    target_environment: str = "LOCAL_SIMULATOR"
    payload_hash: str = ""


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:8]}")
    run_id: str
    conversation_id: str
    requester_id: str
    requester_name: str
    proposed_action: ProposedAction
    status: ApprovalStatus = ApprovalStatus.PENDING
    required_role: UserRole = UserRole.APPROVER
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision_by: Optional[str] = None
    decision_by_name: Optional[str] = None
    decision_at: Optional[str] = None
    decision_reason: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="'APPROVE' or 'REJECT'")
    reason: str = Field(..., min_length=3, description="Mandatory justification for audit")


class Message(BaseModel):
    id: str = Field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:8]}")
    conversation_id: str
    sender: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str
    policy_citations: List[PolicyCitation] = Field(default_factory=list)
    proposed_action: Optional[ProposedAction] = None
    approval_request: Optional[ApprovalRequest] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: f"conv-{uuid.uuid4().hex[:8]}")
    user_id: str
    title: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RunEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:8]}")
    run_id: str
    event_type: str = Field(
        ...,
        description="'token', 'agent_handoff', 'tool_call', 'approval_required', 'stream_end', 'error', 'heartbeat'"
    )
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: Dict[str, Any] = Field(default_factory=dict)


class AuditLogEntry(BaseModel):
    id: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str
    actor_id: str
    actor_name: str
    actor_role: str
    action_type: str
    target_environment: str
    status: str
    summary: str
    masked_payload_json: str
