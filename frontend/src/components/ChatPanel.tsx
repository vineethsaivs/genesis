import { useState, useRef, useEffect } from 'react';
import { ArrowUp, Loader2 } from 'lucide-react';

import type { AgentStatus } from '../lib/types';

interface Message {
  role: 'user' | 'agent';
  content: string;
}

interface ChatPanelProps {
  messages: Message[];
  onSend: (msg: string) => void;
  agentStatus: AgentStatus;
}

const EXAMPLE_CHIPS = [
  'Compare RTX 5090 prices across sites',
  'Find trending GitHub repos this week',
  'Analyze this CSV for patterns',
];

export default function ChatPanel({ messages, onSend, agentStatus }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isBusy = agentStatus !== 'idle' && agentStatus !== 'complete' && agentStatus !== 'error';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isBusy) return;
    onSend(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  };

  return (
    <div className="flex flex-col h-full" style={{ borderRight: '1px solid var(--border-primary)' }}>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
              Try an example
            </p>
            <div className="flex flex-col gap-2 w-full px-2">
              {EXAMPLE_CHIPS.map((chip) => (
                <button
                  key={chip}
                  onClick={() => onSend(chip)}
                  className="text-left px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer"
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-primary)',
                    color: 'var(--text-secondary)',
                    fontSize: '12px',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent-cyan)';
                    e.currentTarget.style.color = 'var(--text-primary)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-primary)';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                  }}
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                style={{ animation: 'fade-in 0.2s ease-out' }}
              >
                <div
                  className="px-3 py-2 rounded-lg text-sm"
                  style={{
                    maxWidth: msg.role === 'user' ? '85%' : '95%',
                    background:
                      msg.role === 'user'
                        ? 'var(--accent-cyan-dim)'
                        : 'var(--bg-secondary)',
                    border:
                      msg.role === 'user'
                        ? '1px solid rgba(6, 182, 212, 0.2)'
                        : '1px solid var(--border-primary)',
                    color: 'var(--text-primary)',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isBusy && (
              <div className="flex items-center gap-2 px-3 py-2" style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                <Loader2 size={14} className="animate-spin" />
                Agent working...
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3" style={{ borderTop: '1px solid var(--border-primary)' }}>
        <div
          className="flex items-end gap-2 rounded-lg px-3 py-2"
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-primary)',
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask GENESIS anything..."
            disabled={isBusy}
            rows={1}
            className="flex-1 bg-transparent border-none outline-none resize-none text-sm"
            style={{
              color: 'var(--text-primary)',
              fontSize: '13px',
              fontFamily: 'var(--font-sans)',
              maxHeight: '120px',
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isBusy}
            className="flex items-center justify-center w-7 h-7 rounded-md transition-colors shrink-0 cursor-pointer"
            style={{
              background: input.trim() && !isBusy ? 'var(--accent-cyan)' : 'var(--bg-tertiary)',
              color: input.trim() && !isBusy ? '#000' : 'var(--text-muted)',
            }}
          >
            <ArrowUp size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
