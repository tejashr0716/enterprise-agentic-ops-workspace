import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { AuditLogEntry } from '../types';
import { BookOpen, Database, History, RefreshCw, X, Shield } from 'lucide-react';

interface InspectorPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const InspectorPanel: React.FC<InspectorPanelProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'policies' | 'sap' | 'audit'>('policies');
  const [documents, setDocuments] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [docs, logs] = await Promise.all([
        api.listDocuments().catch(() => []),
        api.getAuditLogs().catch(() => [])
      ]);
      setDocuments(docs);
      setAuditLogs(logs);
    } catch (err) {
      console.error('Failed to load inspector data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <aside className="w-96 bg-slate-900 border-l border-slate-800 flex flex-col h-full text-slate-300 z-20 shadow-2xl">
      {/* Drawer Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-indigo-400" />
          <h2 className="font-semibold text-sm text-slate-100">Enterprise Inspector</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            title="Refresh"
            className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
          </button>
          <button
            onClick={onClose}
            title="Close"
            className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 bg-slate-950/40 text-xs">
        <button
          onClick={() => setActiveTab('policies')}
          className={`flex-1 py-2.5 px-3 font-medium flex items-center justify-center gap-1.5 border-b-2 transition ${
            activeTab === 'policies'
              ? 'border-indigo-500 text-indigo-300 bg-slate-900/60'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          Governance
        </button>
        <button
          onClick={() => setActiveTab('sap')}
          className={`flex-1 py-2.5 px-3 font-medium flex items-center justify-center gap-1.5 border-b-2 transition ${
            activeTab === 'sap'
              ? 'border-indigo-500 text-indigo-300 bg-slate-900/60'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          SAP Catalog
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`flex-1 py-2.5 px-3 font-medium flex items-center justify-center gap-1.5 border-b-2 transition ${
            activeTab === 'audit'
              ? 'border-indigo-500 text-indigo-300 bg-slate-900/60'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <History className="w-3.5 h-3.5" />
          Audit Trail
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 text-xs space-y-3">
        {activeTab === 'policies' && (
          <div>
            <div className="text-[11px] text-slate-400 mb-3">
              Hybrid BM25 + Vector RAG Index primed with Microsoft SharePoint governance corpus:
            </div>
            {documents.length === 0 ? (
              <p className="text-slate-500 italic">No indexed documents found</p>
            ) : (
              documents.map((doc, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-1.5 mb-2.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200 truncate">{doc.title}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                      {doc.version}
                    </span>
                  </div>
                  <div className="text-indigo-400 font-medium text-[11px]">{doc.section}</div>
                  <div className="text-slate-300 text-[11px] italic bg-slate-900/80 p-2 rounded border border-slate-800/80">
                    &ldquo;{doc.text}&rdquo;
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                    <span>Doc ID: {doc.doc_id}</span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      Tier: {doc.access_tier}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'sap' && (
          <div>
            <div className="text-[11px] text-slate-400 mb-3">
              SAP S/4HANA OData Master Catalog (Simulated Enterprise ERP Dataset):
            </div>
            <div className="space-y-2.5">
              {[
                {
                  sku: 'WS-ERGO-01',
                  desc: 'Ergonomic Sit-Stand Workstation 48x30',
                  vendor: 'Dell Technologies India Ltd',
                  id: 'SAP-VEN-99104',
                  price: 450.0,
                  lead: 5
                },
                {
                  sku: 'SRV-EDGE-X8',
                  desc: 'Dell PowerEdge R750xs Dual Intel Xeon 64GB',
                  vendor: 'Dell Technologies India Ltd',
                  id: 'SAP-VEN-99104',
                  price: 3200.0,
                  lead: 12
                },
                {
                  sku: 'SW-LANG-PRO',
                  desc: 'Multi-Agent Enterprise Orchestrator Annual License',
                  vendor: 'LangScale AI Corp',
                  id: 'SAP-VEN-44201',
                  price: 1850.0,
                  lead: 1
                },
                {
                  sku: 'HW-CLONE-UNAUTH',
                  desc: 'Grey Market Prohibited Workstation Clone',
                  vendor: 'Unauthorized Grey Market Imports',
                  id: 'SAP-VEN-00000',
                  price: 150.0,
                  lead: 30
                }
              ].map((item) => (
                <div key={item.sku} className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-100">{item.desc}</span>
                    <span className="text-amber-400 font-bold">${item.price.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between text-slate-400 text-[11px]">
                    <span className="font-mono text-indigo-300">SKU: {item.sku}</span>
                    <span>Lead: {item.lead} days</span>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    Vendor: {item.vendor} ({item.id})
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'audit' && (
          <div>
            <div className="text-[11px] text-slate-400 mb-3">
              Immutable SQLite WAL Transaction Audit Trail:
            </div>
            {auditLogs.length === 0 ? (
              <p className="text-slate-500 italic">No audit records logged yet</p>
            ) : (
              auditLogs.map((log) => (
                <div key={log.id} className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 space-y-1 mb-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-indigo-400">{log.action_type}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                        log.status === 'SUCCESS' || log.status === 'APPROVED'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : log.status === 'REJECTED'
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      {log.status}
                    </span>
                  </div>
                  <div className="text-slate-200 text-xs">{log.summary}</div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-900">
                    <span>Actor: {log.actor_name}</span>
                    <span className="font-mono">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-[9px] text-slate-600 font-mono truncate">
                    Corr: {log.correlation_id}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
