import React from 'react';
import { Conversation, IntegrationStatusResponse } from '../types';
import { Plus, MessageSquare, Database, Cloud, Cpu, ShieldCheck } from 'lucide-react';

interface SidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  integrationsStatus: IntegrationStatusResponse | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  integrationsStatus
}) => {
  return (
    <aside className="w-72 bg-slate-900 border-r border-slate-800 flex flex-col justify-between text-slate-300 h-full">
      <div className="p-4 flex flex-col gap-4 overflow-y-auto">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium rounded-lg text-sm transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          New Procurement Chat
        </button>

        {/* Conversation List */}
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-2 mb-1">
            Requisition Sessions
          </span>
          {conversations.length === 0 ? (
            <p className="text-xs text-slate-500 px-2 py-4 italic">No active sessions</p>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              return (
                <button
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs flex items-center gap-2.5 transition-all ${
                    isActive
                      ? 'bg-indigo-950/80 text-indigo-200 border border-indigo-800/60 font-medium'
                      : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-slate-400" />
                  <span className="truncate flex-1">{conv.title}</span>
                </button>
              );
            })
          )}
        </div>

        {/* Enterprise Integrations Pill Card */}
        <div className="mt-4 pt-4 border-t border-slate-800 flex flex-col gap-2.5">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1">
            Adapter Ecosystem
          </span>

          <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-2.5 text-xs flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium text-slate-300">
                <Database className="w-3.5 h-3.5 text-blue-400" />
                SAP S/4HANA OData
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                {integrationsStatus?.adapters.sap.mode || 'SIMULATOR'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium text-slate-300">
                <Cloud className="w-3.5 h-3.5 text-cyan-400" />
                M365 SharePoint Graph
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                HYBRID RAG
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium text-slate-300">
                <Cpu className="w-3.5 h-3.5 text-purple-400" />
                MCP 2.x Standard
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                CONNECTED
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium text-slate-300">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                PII Firewall (DLP)
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                LUHN MOD-10
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Candidate Attribution & Role Spec */}
      <div className="p-3 bg-slate-950 border-t border-slate-800 text-[11px] text-slate-400">
        <div className="font-semibold text-slate-200">Tejas H R (BE ISE 2026)</div>
        <div>Target: NTT DATA Full Stack Multi-Agent AI</div>
        <div className="text-[10px] text-slate-500 font-mono mt-0.5">Req ID: 395031 • Bengaluru, IN</div>
      </div>
    </aside>
  );
};
