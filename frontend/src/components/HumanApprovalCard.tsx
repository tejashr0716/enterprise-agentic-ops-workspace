import React, { useState } from 'react';
import { ApprovalRequest, User } from '../types';
import { CheckCircle, XCircle, AlertTriangle, Fingerprint, Lock, ShieldAlert } from 'lucide-react';

interface HumanApprovalCardProps {
  approval: ApprovalRequest;
  currentUser: User | null;
  onDecide: (approvalId: string, decision: 'APPROVE' | 'REJECT', reason: string) => Promise<void>;
}

export const HumanApprovalCard: React.FC<HumanApprovalCardProps> = ({
  approval,
  currentUser,
  onDecide
}) => {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const action = approval.proposed_action;
  const isRequester = currentUser?.id === approval.requester_id;
  const isExecutiveRequired = approval.required_role === 'EXECUTIVE_APPROVER';
  const hasExecutiveRole = currentUser?.role === 'EXECUTIVE_APPROVER';
  const hasApproverRole = currentUser?.role === 'APPROVER' || currentUser?.role === 'EXECUTIVE_APPROVER';

  const canApprove =
    !isRequester &&
    ((isExecutiveRequired && hasExecutiveRole) || (!isExecutiveRequired && hasApproverRole));

  const handleDecision = async (decision: 'APPROVE' | 'REJECT') => {
    if (!reason.trim() || reason.trim().length < 3) {
      setErrorMsg('Mandatory audit justification is required (minimum 3 characters).');
      return;
    }
    setErrorMsg(null);
    setSubmitting(true);
    try {
      await onDecide(approval.id, decision, reason.trim());
      setReason('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Decision failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="my-3 p-4 rounded-xl border border-amber-800/60 bg-amber-950/20 shadow-md">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-amber-900/40">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          <span className="font-semibold text-sm text-amber-200">
            Human-in-the-Loop Authorization Required
          </span>
        </div>
        <span
          className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium ${
            approval.status === 'PENDING'
              ? 'bg-amber-900/80 text-amber-300 border border-amber-700'
              : approval.status === 'APPROVED'
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
              : 'bg-rose-950 text-rose-300 border border-rose-800'
          }`}
        >
          {approval.status}
        </span>
      </div>

      {/* Payload Details */}
      <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
        <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-[10px] uppercase">Requisition Item</div>
          <div className="font-semibold text-slate-100 truncate mt-0.5">{action.item_description}</div>
          <div className="text-[10px] text-slate-500 font-mono">SKU: {action.sku}</div>
        </div>

        <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-[10px] uppercase">Supplier / Vendor</div>
          <div className="font-semibold text-slate-100 truncate mt-0.5">{action.vendor_name}</div>
          <div className="text-[10px] text-slate-500 font-mono">ID: {action.vendor_id}</div>
        </div>

        <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-[10px] uppercase">Total Amount</div>
          <div className="font-bold text-amber-400 text-sm mt-0.5">
            ${action.total_amount} {action.currency}
          </div>
          <div className="text-[10px] text-slate-500">
            {action.quantity} units @ ${action.unit_price}
          </div>
        </div>

        <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-[10px] uppercase">Cost Center</div>
          <div className="font-mono text-slate-200 mt-0.5">{action.cost_center}</div>
          <div className="text-[10px] text-slate-500">Target: {action.target_environment}</div>
        </div>

        <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 col-span-2">
          <div className="text-slate-400 text-[10px] uppercase">SharePoint Governance Clause</div>
          <div className="text-slate-300 italic truncate mt-0.5">{action.policy_reference}</div>
          <div className="text-[10px] text-slate-500">Authority Required: {approval.required_role}</div>
        </div>
      </div>

      {/* Cryptographic SHA-256 Fingerprint */}
      <div className="mt-2.5 flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-slate-950/70 border border-slate-800/80 text-[11px] font-mono text-slate-400">
        <Fingerprint className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
        <span className="text-slate-500">Payload Hash:</span>
        <span className="text-indigo-300 truncate">{action.payload_hash || 'SHA-256 Pending'}</span>
      </div>

      {/* Decision Section or Status Confirmation */}
      {approval.status === 'PENDING' ? (
        <div className="mt-4 pt-3 border-t border-amber-900/30 flex flex-col gap-2.5">
          {isRequester ? (
            <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 flex-shrink-0 text-rose-400" />
              <span>
                <strong>Self-Approval Prohibited:</strong> You created this requisition ({approval.requester_name}). An independent approver (e.g. <em>Bob Martinez</em> or <em>Carol Danvers</em>) must authorize this transaction.
              </span>
            </div>
          ) : !canApprove ? (
            <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/60 text-amber-300 text-xs flex items-center gap-2">
              <Lock className="w-4 h-4 flex-shrink-0 text-amber-400" />
              <span>
                <strong>Insufficient Authority:</strong> This requisition requires{' '}
                <strong>{approval.required_role}</strong> authority. Switch to an executive or appropriate manager in the top identity bar.
              </span>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium text-slate-300">
                Mandatory Authorization Justification (Recorded to Immutable Audit Trail):
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g., Approved budget allocation from FY26 Q1 Infrastructure CapEx..."
                rows={2}
                className="w-full text-xs p-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />

              {errorMsg && (
                <div className="text-xs text-rose-400 font-medium">{errorMsg}</div>
              )}

              <div className="flex items-center gap-3 mt-1">
                <button
                  onClick={() => handleDecision('APPROVE')}
                  disabled={submitting}
                  className="flex-1 py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition-colors shadow disabled:opacity-50"
                >
                  <CheckCircle className="w-4 h-4" />
                  {submitting ? 'Executing via SAP...' : 'Authorize Requisition (SAP S/4HANA)'}
                </button>
                <button
                  onClick={() => handleDecision('REJECT')}
                  disabled={submitting}
                  className="py-2 px-3 rounded-lg bg-rose-700 hover:bg-rose-600 active:bg-rose-800 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition-colors shadow disabled:opacity-50"
                >
                  <XCircle className="w-4 h-4" />
                  Reject Request
                </button>
              </div>
            </div>
          )}
        </div>
      ) : approval.status === 'APPROVED' ? (
        <div className="mt-3 p-2.5 rounded-lg bg-emerald-950/60 border border-emerald-800/80 text-emerald-200 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <div>
            <div>
              <strong>Authorized by:</strong> {approval.decision_by_name || 'Authorized Approver'} at{' '}
              {approval.decision_at ? new Date(approval.decision_at).toLocaleTimeString() : 'N/A'}
            </div>
            <div className="text-[11px] text-emerald-300/80 mt-0.5">
              Reason: &ldquo;{approval.decision_reason}&rdquo;
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-3 p-2.5 rounded-lg bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs flex items-center gap-2">
          <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <div>
            <div>
              <strong>Rejected by:</strong> {approval.decision_by_name || 'Approver'}
            </div>
            <div className="text-[11px] text-rose-300/80 mt-0.5">
              Reason: &ldquo;{approval.decision_reason}&rdquo;
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
