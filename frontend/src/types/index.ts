export type UserRole = 'REQUESTER' | 'APPROVER' | 'EXECUTIVE_APPROVER' | 'EXTERNAL_CONTRACTOR';
export type AccessTier = 'PUBLIC' | 'INTERNAL' | 'RESTRICTED';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department: string;
  spending_limit_usd: string | number;
  access_tier: AccessTier;
}

export interface PolicyCitation {
  document_id: string;
  document_title: string;
  version: string;
  section: string;
  excerpt: string;
  relevance_score: number;
  access_tier: AccessTier;
}

export interface VendorQuote {
  quote_id: string;
  vendor_id: string;
  vendor_name: string;
  sku: string;
  item_description: string;
  unit_price: string | number;
  currency: string;
  lead_time_days: number;
  source_system: string;
}

export interface ProposedAction {
  action_id: string;
  action_type: string;
  vendor_name: string;
  vendor_id: string;
  item_description: string;
  sku: string;
  quantity: number;
  unit_price: string | number;
  total_amount: string | number;
  currency: string;
  cost_center: string;
  policy_reference: string;
  target_environment: string;
  payload_hash: string;
}

export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export interface ApprovalRequest {
  id: string;
  run_id: string;
  conversation_id: string;
  requester_id: string;
  requester_name: string;
  proposed_action: ProposedAction;
  status: ApprovalStatus;
  required_role: UserRole;
  created_at: string;
  decision_by?: string | null;
  decision_by_name?: string | null;
  decision_at?: string | null;
  decision_reason?: string | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  policy_citations?: PolicyCitation[];
  proposed_action?: ProposedAction | null;
  approval_request?: ApprovalRequest | null;
  timestamp: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface RunEventData {
  from_agent?: string;
  to_agent?: string;
  intent?: string;
  detail?: string;
  tool?: string;
  token?: string;
  reason?: string;
  approval_id?: string;
  required_role?: string;
  action?: ProposedAction;
  status?: string;
  error?: string;
  message_id?: string;
  [key: string]: any;
}

export interface RunEvent {
  event_id: string;
  run_id: string;
  event_type: 'token' | 'agent_handoff' | 'tool_call' | 'approval_required' | 'stream_end' | 'error' | 'heartbeat' | 'dlp_warning' | 'compliance_rejection';
  timestamp: string;
  data: RunEventData;
}

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  correlation_id: string;
  actor_id: string;
  actor_name: string;
  actor_role: string;
  action_type: string;
  target_environment: string;
  status: string;
  summary: string;
  masked_payload_json: string;
}

export interface IntegrationAdapterStatus {
  name: string;
  mode: string;
  status: string;
  endpoint?: string;
  catalog_items?: number;
  governance_corpus?: string;
  tools_exposed?: string[];
  algorithms?: string[];
}

export interface IntegrationStatusResponse {
  runtime_mode: string;
  adapters: {
    sap: IntegrationAdapterStatus;
    m365: IntegrationAdapterStatus;
    mcp: IntegrationAdapterStatus;
    dlp: IntegrationAdapterStatus;
  };
}
