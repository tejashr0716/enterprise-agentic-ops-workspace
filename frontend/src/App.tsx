import React, { useState, useEffect } from 'react';
import { api } from './services/api';
import {
  User,
  Conversation,
  Message,
  ApprovalRequest,
  IntegrationStatusResponse,
  RunEvent
} from './types';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatCanvas } from './components/ChatCanvas';
import { InspectorPanel } from './components/InspectorPanel';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [demoUsers, setDemoUsers] = useState<User[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [integrationsStatus, setIntegrationsStatus] = useState<IntegrationStatusResponse | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  // Streaming State
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeEvents, setActiveEvents] = useState<RunEvent[]>([]);
  const [streamingText, setStreamingText] = useState('');

  // 1. Initial Load
  const init = async () => {
    try {
      const users = await api.listDemoUsers();
      setDemoUsers(users);

      // Default login to Alice if no token
      const defaultEmail = 'alice.requester@company.internal';
      let user: User;
      try {
        if (!api.getToken()) {
          const authRes = await api.login(defaultEmail);
          user = authRes.user;
        } else {
          user = await api.getCurrentUser();
        }
      } catch {
        const authRes = await api.login(defaultEmail);
        user = authRes.user;
      }
      setCurrentUser(user);

      // Load Integrations Status & Pending Approvals
      const [statusRes, apprs] = await Promise.all([
        api.getIntegrationStatus().catch(() => null),
        api.listPendingApprovals().catch(() => [])
      ]);
      setIntegrationsStatus(statusRes);
      setPendingApprovals(apprs);

      // Load Conversations
      const convs = await api.listConversations();
      setConversations(convs);

      if (convs.length > 0) {
        setActiveConversationId(convs[0].id);
        const convDetails = await api.getConversation(convs[0].id);
        setMessages(convDetails.messages);
      } else {
        // Create initial session
        const newConv = await api.createConversation('Hardware Requisition Session');
        setConversations([newConv]);
        setActiveConversationId(newConv.id);
        setMessages([]);
      }
    } catch (err) {
      console.error('Initialization error:', err);
    }
  };

  useEffect(() => {
    init();
  }, []);

  // 2. Switch User Identity
  const handleSwitchUser = async (email: string) => {
    try {
      const res = await api.login(email);
      setCurrentUser(res.user);
      const apprs = await api.listPendingApprovals();
      setPendingApprovals(apprs);
      // Reload current conversation messages to update approval card capabilities
      if (activeConversationId) {
        const convDetails = await api.getConversation(activeConversationId);
        setMessages(convDetails.messages);
      }
    } catch (err) {
      console.error('User switch failed:', err);
    }
  };

  // 3. New Conversation
  const handleNewConversation = async () => {
    try {
      const count = conversations.length + 1;
      const newConv = await api.createConversation(`Requisition Session #${count}`);
      setConversations([newConv, ...conversations]);
      setActiveConversationId(newConv.id);
      setMessages([]);
    } catch (err) {
      console.error('Failed to create conversation:', err);
    }
  };

  // 4. Select Conversation
  const handleSelectConversation = async (id: string) => {
    if (id === activeConversationId || isStreaming) return;
    setActiveConversationId(id);
    try {
      const convDetails = await api.getConversation(id);
      setMessages(convDetails.messages);
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  };

  // 5. Send Message & Stream
  const handleSendMessage = async (text: string) => {
    if (!activeConversationId || isStreaming) return;

    // Add optimistic user message
    const tempUserMsg: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: activeConversationId,
      sender: 'user',
      content: text,
      timestamp: new Date().toISOString()
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    setIsStreaming(true);
    setActiveEvents([]);
    setStreamingText('');

    await api.streamRun(
      activeConversationId,
      text,
      (event: RunEvent) => {
        if (event.event_type === 'token') {
          const piece = event.data?.token || '';
          setStreamingText((prev) => prev + piece);
        } else {
          setActiveEvents((prev) => [...prev, event]);
        }
      },
      (error: string) => {
        console.error('Streaming error:', error);
        setIsStreaming(false);
      },
      async () => {
        // Stream completed
        setIsStreaming(false);
        setActiveEvents([]);
        setStreamingText('');
        // Reload persisted messages and pending approvals
        try {
          const [convDetails, apprs] = await Promise.all([
            api.getConversation(activeConversationId),
            api.listPendingApprovals()
          ]);
          setMessages(convDetails.messages);
          setPendingApprovals(apprs);
        } catch (e) {
          console.error('Post-stream reload error:', e);
        }
      }
    );
  };

  // 6. Decide Approval
  const handleDecideApproval = async (
    approvalId: string,
    decision: 'APPROVE' | 'REJECT',
    reason: string
  ) => {
    await api.decideApproval(approvalId, decision, reason);
    // Refresh approvals and conversation
    const [apprs, convDetails] = await Promise.all([
      api.listPendingApprovals(),
      activeConversationId ? api.getConversation(activeConversationId) : Promise.resolve(null)
    ]);
    setPendingApprovals(apprs);
    if (convDetails) {
      setMessages(convDetails.messages);
    }
  };

  // 7. Refresh Approvals
  const handleRefreshApprovals = async () => {
    try {
      const apprs = await api.listPendingApprovals();
      setPendingApprovals(apprs);
    } catch (err) {
      console.error('Refresh approvals failed:', err);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 font-sans">
      <Header
        currentUser={currentUser}
        demoUsers={demoUsers}
        onSwitchUser={handleSwitchUser}
        pendingApprovalsCount={pendingApprovals.length}
        integrationsStatus={integrationsStatus}
        onRefreshApprovals={handleRefreshApprovals}
        onToggleInspector={() => setInspectorOpen((prev) => !prev)}
        inspectorOpen={inspectorOpen}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          integrationsStatus={integrationsStatus}
        />

        <ChatCanvas
          messages={messages}
          currentUser={currentUser}
          onSendMessage={handleSendMessage}
          onDecideApproval={handleDecideApproval}
          isStreaming={isStreaming}
          activeEvents={activeEvents}
          streamingText={streamingText}
        />

        <InspectorPanel
          isOpen={inspectorOpen}
          onClose={() => setInspectorOpen(false)}
        />
      </div>
    </div>
  );
};
export default App;
