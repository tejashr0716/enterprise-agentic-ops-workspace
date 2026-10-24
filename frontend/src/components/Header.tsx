import React from 'react';
import { User, IntegrationStatusResponse } from '../types';
import { Shield, UserCheck, Layers, AlertCircle } from 'lucide-react';

interface HeaderProps {
  currentUser: User | null;
  demoUsers: User[];
  onSwitchUser: (email: string) => void;
  pendingApprovalsCount: number;
  integrationsStatus: IntegrationStatusResponse | null;
  onRefreshApprovals: () => void;
  onToggleInspector: () => void;
  inspectorOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentUser,
  demoUsers,
  onSwitchUser,
  pendingApprovalsCount,
  integrationsStatus,
  onRefreshApprovals,
  onToggleInspector,
  inspectorOpen
}) => {
  const runtimeMode = integrationsStatus?.runtime_mode || 'LOCAL_SIMULATOR';

  return (
    <header className="bg-slate-900 border-b border-slate-800 text-slate-100 px-6 py-3 flex items-center justify-between select-none">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-semibold text-base leading-tight tracking-tight text-white">
              Enterprise Agentic Ops Workspace
            </h1>
            <p className="text-xs text-slate-400">
              Multi-Agentic Procurement & Governance Orchestration (NTT DATA AI)
            </p>
          </div>
        </div>

        {/* Runtime Environment Badge */}
        <div className="flex items-center gap-2 ml-4">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-amber-950/60 text-amber-300 border border-amber-800/60 shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
            ENV: {runtimeMode}
          </span>
          <span className="hidden lg:inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">
            <Shield className="w-3.5 h-3.5" />
            PII Firewall: Active
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Approvals notification badge */}
        <button
          onClick={onRefreshApprovals}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            pendingApprovalsCount > 0
              ? 'bg-amber-500/20 text-amber-200 border border-amber-500/40 hover:bg-amber-500/30'
              : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
          }`}
          title="Click to refresh pending approvals"
        >
          <AlertCircle className={`w-3.5 h-3.5 ${pendingApprovalsCount > 0 ? 'text-amber-400' : 'text-slate-400'}`} />
          Pending Approvals: <span className="font-bold">{pendingApprovalsCount}</span>
        </button>

        {/* User Identity Switcher */}
        <div className="flex items-center gap-2 bg-slate-800/90 border border-slate-700 rounded-lg px-3 py-1.5 text-xs">
          <UserCheck className="w-4 h-4 text-indigo-400" />
          <span className="text-slate-400 hidden sm:inline">Active Role:</span>
          <select
            value={currentUser?.email || ''}
            onChange={(e) => onSwitchUser(e.target.value)}
            className="bg-transparent text-slate-100 font-medium focus:outline-none cursor-pointer"
          >
            {demoUsers.map((u) => (
              <option key={u.id} value={u.email} className="bg-slate-900 text-slate-200">
                {u.full_name} ({u.role}) — Max ${u.spending_limit_usd}
              </option>
            ))}
          </select>
        </div>

        {/* Toggle Inspector Drawer */}
        <button
          onClick={onToggleInspector}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all ${
            inspectorOpen
              ? 'bg-indigo-600 text-white border-indigo-500 shadow'
              : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
          }`}
        >
          {inspectorOpen ? 'Hide Inspector' : 'Enterprise Inspector'}
        </button>
      </div>
    </header>
  );
};
