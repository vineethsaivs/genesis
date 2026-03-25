import { useState, useEffect, useCallback, useRef } from 'react';

import type { AgentStatus, AgentEvent, EvolutionPhase, TestResult } from './lib/types';
import { useWebSocket } from './hooks/useWebSocket';
import { useSkillTree } from './hooks/useSkillTree';
import { useDemoMode } from './hooks/useDemoMode';
import ChatPanel from './components/ChatPanel';
import AgentFeed from './components/AgentFeed';
import SkillTree from './components/SkillTree';
import CodeViewer from './components/CodeViewer';
import EvolutionBanner from './components/EvolutionBanner';
import SkillDetail from './components/SkillDetail';
import { api } from './lib/api';

interface Message {
  role: 'user' | 'agent';
  content: string;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus>('idle');
  const [demoMode, setDemoMode] = useState(false);
  const [currentCode, setCurrentCode] = useState<{ code: string; skillName: string } | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [evolutionPhase, setEvolutionPhase] = useState<EvolutionPhase | null>(null);
  const processedCountRef = useRef(0);
  const bannerTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { sendMessage, events, isConnected } = useWebSocket(!demoMode);
  const { graphData, setGraphData, selectedNode, setSelectedNode, addNode } = useSkillTree();
  const { demoEvents } = useDemoMode(demoMode, setGraphData);

  // Skill tree sizing
  const skillTreeRef = useRef<HTMLDivElement>(null);
  const [treeSize, setTreeSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = skillTreeRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setTreeSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const activeEvents = demoMode ? demoEvents : events;

  const processEvent = useCallback(
    (event: AgentEvent) => {
      switch (event.event) {
        case 'agent_status':
          if (event.status) setAgentStatus(event.status);
          break;
        case 'evolution_start':
          if (bannerTimeoutRef.current) {
            clearTimeout(bannerTimeoutRef.current);
            bannerTimeoutRef.current = null;
          }
          setCurrentCode(null);
          setTestResults([]);
          setIsStreaming(true);
          setEvolutionPhase('analyzing');
          break;
        case 'code_stream':
          setEvolutionPhase('writing');
          if (event.chunk) {
            setCurrentCode((prev) => ({
              code: (prev?.code ?? '') + event.chunk!,
              skillName: event.skill_name ?? prev?.skillName ?? 'unknown',
            }));
          }
          break;
        case 'test_result':
          setEvolutionPhase('testing');
          setIsStreaming(false);
          if (event.details || event.skill_name) {
            setTestResults((prev) => [
              ...prev,
              {
                name: event.details ?? event.skill_name ?? 'test',
                passed: event.passed ?? true,
              },
            ]);
          }
          break;
        case 'skill_tree_update':
          setEvolutionPhase('registering');
          if (event.node) addNode(event.node, event.edge);
          if (bannerTimeoutRef.current) clearTimeout(bannerTimeoutRef.current);
          bannerTimeoutRef.current = setTimeout(() => {
            setEvolutionPhase(null);
          }, 1500);
          break;
        case 'task_complete':
          if (event.response) {
            setMessages((prev) => [...prev, { role: 'agent', content: event.response! }]);
          }
          if (bannerTimeoutRef.current) {
            clearTimeout(bannerTimeoutRef.current);
            bannerTimeoutRef.current = null;
          }
          setAgentStatus('idle');
          setIsStreaming(false);
          setEvolutionPhase(null);
          break;
        case 'error':
          setAgentStatus('error');
          setIsStreaming(false);
          setEvolutionPhase(null);
          if (event.message) {
            setMessages((prev) => [...prev, { role: 'agent', content: `Error: ${event.message}` }]);
          }
          break;
      }
    },
    [addNode]
  );

  useEffect(() => {
    const unprocessed = activeEvents.slice(processedCountRef.current);
    for (const event of unprocessed) {
      processEvent(event);
    }
    processedCountRef.current = activeEvents.length;
  }, [activeEvents, processEvent]);

  useEffect(() => {
    processedCountRef.current = 0;
  }, [demoMode]);

  useEffect(() => {
    return () => {
      if (bannerTimeoutRef.current) clearTimeout(bannerTimeoutRef.current);
    };
  }, []);

  const handleSend = useCallback(
    (text: string) => {
      setMessages((prev) => [...prev, { role: 'user', content: text }]);
      setAgentStatus('planning');
      setCurrentCode(null);
      setTestResults([]);
      sendMessage({ task: text });
    },
    [sendMessage]
  );

  const handleDeleteSkill = useCallback(
    (skillId: string) => {
      api.deleteSkill(skillId);
      setGraphData((prev) => ({
        nodes: prev.nodes.filter((n) => n.id !== skillId),
        links: prev.links.filter((l) => {
          const src = typeof l.source === 'object' ? (l.source as any).id : l.source;
          const tgt = typeof l.target === 'object' ? (l.target as any).id : l.target;
          return src !== skillId && tgt !== skillId;
        }),
      }));
    },
    [setGraphData]
  );

  return (
    <div className="h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-4 h-12 shrink-0"
        style={{ borderBottom: '1px solid var(--border-primary)' }}
      >
        <div className="flex items-center gap-3">
          <h1
            className="text-sm font-semibold tracking-wider"
            style={{ color: 'var(--accent-cyan)', letterSpacing: '0.15em' }}
          >
            GENESIS
          </h1>
          {demoMode && (
            <span
              className="px-1.5 py-0.5 rounded text-xs"
              style={{
                background: 'rgba(139, 92, 246, 0.15)',
                color: '#8b5cf6',
                border: '1px solid rgba(139, 92, 246, 0.3)',
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
              }}
            >
              DEMO
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setDemoMode((d) => !d)}
            className="flex items-center gap-2 px-2 py-1 rounded text-xs transition-colors cursor-pointer"
            style={{
              background: demoMode ? 'rgba(139, 92, 246, 0.15)' : 'var(--bg-tertiary)',
              color: demoMode ? '#8b5cf6' : 'var(--text-muted)',
              border: '1px solid',
              borderColor: demoMode ? 'rgba(139, 92, 246, 0.3)' : 'var(--border-primary)',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
            }}
          >
            Demo {demoMode ? 'ON' : 'OFF'}
          </button>
          <span
            className="w-2 h-2 rounded-full"
            title={demoMode ? 'Demo Mode' : isConnected ? 'Connected' : 'Disconnected'}
            style={{
              background: demoMode
                ? 'var(--accent-purple)'
                : isConnected
                  ? 'var(--accent-green)'
                  : 'var(--accent-red)',
              boxShadow: demoMode
                ? '0 0 6px rgba(139, 92, 246, 0.5)'
                : isConnected
                  ? '0 0 6px rgba(16, 185, 129, 0.5)'
                  : '0 0 6px rgba(239, 68, 68, 0.5)',
            }}
          />
        </div>
      </header>

      {/* Evolution Banner */}
      <EvolutionBanner
        skillName={currentCode?.skillName ?? ''}
        currentPhase={evolutionPhase ?? 'analyzing'}
        visible={evolutionPhase !== null}
      />

      {/* Main grid */}
      <div
        className="flex-1 min-h-0"
        style={{
          display: 'grid',
          gridTemplateColumns: '300px 1fr 320px',
        }}
      >
        {/* Left: Chat */}
        <ChatPanel messages={messages} onSend={handleSend} agentStatus={agentStatus} />

        {/* Center: Skill Tree */}
        <div
          ref={skillTreeRef}
          style={{
            borderRight: '1px solid var(--border-primary)',
            position: 'relative',
          }}
        >
          {treeSize.width > 0 && (
            <SkillTree
              graphData={graphData}
              onNodeClick={setSelectedNode}
              width={treeSize.width}
              height={treeSize.height}
            />
          )}
        </div>

        {/* Right column */}
        <div className="flex flex-col min-h-0">
          {/* Code Viewer */}
          <div
            style={{
              height: '55%',
              borderBottom: '1px solid var(--border-primary)',
            }}
          >
            <CodeViewer
              code={currentCode?.code ?? null}
              skillName={currentCode?.skillName ?? null}
              isStreaming={isStreaming}
              testResults={testResults}
            />
          </div>

          {/* Agent Feed */}
          <div style={{ height: '45%' }} className="min-h-0">
            <AgentFeed events={activeEvents} />
          </div>
        </div>
      </div>

      {/* Skill Detail overlay */}
      <SkillDetail
        skill={selectedNode}
        onClose={() => setSelectedNode(null)}
        onDelete={handleDeleteSkill}
      />
    </div>
  );
}
