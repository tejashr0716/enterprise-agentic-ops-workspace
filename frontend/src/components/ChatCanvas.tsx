import React, { useState, useRef, useEffect } from 'react';
import { Message, User, RunEvent } from '../types';
import { HumanApprovalCard } from './HumanApprovalCard';
import { Send, Bot, User as UserIcon, BookOpen, ArrowRight, Activity, Terminal } from 'lucide-react';

interface ChatCanvasProps {
  messages: Message[];
  currentUser: User | null;
  onSendMessage: (text: string) => void;
  onDecideApproval: (approvalId: string, decision: 'APPROVE' | 'REJECT', reason: string) => Promise<void>;
  isStreaming: boolean;
  activeEvents: RunEvent[];
  streamingText: string;
}

export const ChatCanvas: React.FC<ChatCanvasProps> = ({
  messages,
  currentUser,
  onSendMessage,
  onDecideApproval,
  isStreaming,
  activeEvents,
  streamingText
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, activeEvents]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleQuickPrompt = (prompt: string) => {
    if (isStreaming) return;
    onSendMessage(prompt);
  };

  // Helper to format simple markdown-like elements
  const renderFormattedContent = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, idx) => {
      if (line.startsWith('### ')) {
        return (
          <h3 key={idx} className="font-semibold text-slate-100 text-sm mt-3 mb-1">
            {line.substring(4)}
          </h3>
        );
      }
      if (line.startsWith('- ')) {
        return (
          <li key={idx} className="ml-4 list-disc text-slate-200 my-0.5">
            {line.substring(2)}
          </li>
        );
      }
      if (line.startsWith('> ')) {
        return (
          <blockquote
            key={idx}
            className="border-l-2 border-indigo-500 pl-3 my-1.5 italic text-slate-300 text-xs bg-slate-900/60 py-1 rounded-r"
          >
            {line.substring(2)}
          </blockquote>
        );
      }
      if (!line.trim()) {
        return <div key={idx} className="h-1.5" />;
      }
      return (
        <p key={idx} className="my-1 text-slate-200">
          {line}
        </p>
      );
    });
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.length === 0 && !isStreaming ? (
          <div className="h-full flex flex-col items-center justify-center max-w-lg mx-auto text-center space-y-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-900/50 border border-indigo-700/60 flex items-center justify-center text-indigo-400">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100">
                Multi-Agent Enterprise Procurement Assistant
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-md">
                Orchestrates sovereign policy validation via SharePoint RAG, live SAP S/4HANA OData pricing, Model Context Protocol (MCP) tax engines, and Human-in-the-Loop authorization.
              </p>
            </div>

            <div className="w-full pt-4 space-y-2">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                Quick Demonstration Scenarios
              </span>
              {[
                'Requisition 5 ergonomic sit-stand workstations for Engineering team',
                'Inquire about spending thresholds for IT hardware and server assets',
                'Request quote for SRV-EDGE-X8 server cluster',
                'Simulate unauthorized grey-market clone procurement (Section 4.2 violation)'
              ].map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleQuickPrompt(q)}
                  className="w-full text-left p-2.5 rounded-lg bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 text-xs text-slate-300 hover:text-white transition flex items-center justify-between group"
                >
                  <span className="truncate">{q}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 flex-shrink-0" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.sender === 'user';
            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
              >
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                    isUser
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-800 text-indigo-400 border border-slate-700'
                  }`}
                >
                  {isUser ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                <div className="flex-1 space-y-2">
                  <div
                    className={`p-4 rounded-xl text-xs leading-relaxed ${
                      isUser
                        ? 'bg-indigo-600 text-white shadow'
                        : 'bg-slate-900 border border-slate-800/90 text-slate-200 shadow-sm'
                    }`}
                  >
                    {renderFormattedContent(msg.content)}
                  </div>

                  {/* Embedded Policy Citations Drawer */}
                  {msg.policy_citations && msg.policy_citations.length > 0 && (
                    <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 text-xs space-y-2">
                      <div className="flex items-center gap-1.5 text-indigo-400 font-semibold text-[11px]">
                        <BookOpen className="w-3.5 h-3.5" />
                        Grounded SharePoint Policy Citations ({msg.policy_citations.length}):
                      </div>
                      <div className="space-y-1.5">
                        {msg.policy_citations.map((c, i) => (
                          <div
                            key={i}
                            className="p-2 rounded bg-slate-950/80 border border-slate-800 text-[11px]"
                          >
                            <div className="flex justify-between items-center text-slate-400">
                              <span className="font-semibold text-slate-200">{c.document_title}</span>
                              <span className="font-mono text-[10px]">Score: {(c.relevance_score * 100).toFixed(0)}%</span>
                            </div>
                            <div className="text-indigo-300 font-mono text-[10px] mt-0.5">{c.section}</div>
                            <div className="text-slate-300 italic mt-1">&ldquo;{c.excerpt}&rdquo;</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Embedded Human Approval Card */}
                  {msg.approval_request && (
                    <HumanApprovalCard
                      approval={msg.approval_request}
                      currentUser={currentUser}
                      onDecide={onDecideApproval}
                    />
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Live SSE Streaming Canvas */}
        {isStreaming && (
          <div className="flex gap-3 max-w-3xl mr-auto w-full">
            <div className="w-8 h-8 rounded-lg bg-slate-800 text-indigo-400 border border-slate-700 flex items-center justify-center flex-shrink-0 animate-pulse">
              <Bot className="w-4 h-4" />
            </div>

            <div className="flex-1 space-y-2">
              {/* Active Agent Handoff Stream */}
              <div className="p-3 rounded-lg bg-slate-900/80 border border-indigo-900/40 text-xs space-y-1.5">
                <div className="flex items-center gap-2 text-indigo-300 font-semibold text-[11px]">
                  <Activity className="w-3.5 h-3.5 animate-spin" />
                  Multi-Agent State Machine In-Flight:
                </div>
                {activeEvents.map((evt, idx) => (
                  <div
                    key={idx}
                    className="text-[11px] font-mono text-slate-300 flex items-center gap-1.5 bg-slate-950/60 px-2 py-1 rounded"
                  >
                    <Terminal className="w-3 h-3 text-indigo-400" />
                    <span>[{evt.event_type}]</span>
                    <span className="text-slate-400 truncate">
                      {evt.data.detail || evt.data.reason || evt.data.tool || 'Processing...'}
                    </span>
                  </div>
                ))}
              </div>

              {/* Incremental Tokens */}
              {streamingText && (
                <div className="p-4 rounded-xl text-xs leading-relaxed bg-slate-900 border border-slate-800 text-slate-200">
                  {renderFormattedContent(streamingText)}
                  <span className="inline-block w-1.5 h-3.5 ml-1 bg-indigo-400 animate-pulse" />
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="p-4 bg-slate-900 border-t border-slate-800">
        <form onSubmit={handleSubmit} className="flex gap-2 max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isStreaming}
            placeholder={
              isStreaming
                ? 'Multi-agent orchestration in progress...'
                : 'Type requisition (e.g., "Requisition 4 ergonomic workstations for Engineering department")...'
            }
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="px-5 py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium rounded-xl text-xs flex items-center gap-1.5 transition disabled:opacity-40 shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
            Send
          </button>
        </form>
      </div>
    </div>
  );
};
