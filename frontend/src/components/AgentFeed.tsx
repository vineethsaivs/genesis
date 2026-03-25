import { useRef, useEffect } from 'react';

import type { AgentEvent, AgentStatus } from '../lib/types';
import { STATUS_COLORS } from '../lib/types';

interface AgentFeedProps {
  events: AgentEvent[];
}

function relativeTime(timestamp?: string): string {
  if (!timestamp) return '';
  const diff = Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000);
  if (diff < 5) return 'now';
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  return `${Math.floor(diff / 3600)}h`;
}

export default function AgentFeed({ events }: AgentFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const displayEvents = events.slice(-100);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayEvents.length]);

  return (
    <div className="flex flex-col h-full">
      <div
        className="px-3 py-2 text-xs font-medium shrink-0"
        style={{
          color: 'var(--text-muted)',
          borderTop: '1px solid var(--border-primary)',
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
        }}
      >
        Activity
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {displayEvents.length === 0 ? (
          <div
            className="flex items-center justify-center h-full"
            style={{
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
            }}
          >
            Waiting for activity...
          </div>
        ) : (
          displayEvents.map((event, i) => (
            <div
              key={i}
              className="flex items-center gap-2 py-1.5 px-3"
              style={{ animation: 'slide-up 0.2s ease-out' }}
            >
              <span
                className="shrink-0 rounded-full"
                style={{
                  width: '8px',
                  height: '8px',
                  background:
                    STATUS_COLORS[(event.status ?? 'idle') as AgentStatus] ?? STATUS_COLORS.idle,
                }}
              />
              <span
                className="flex-1 truncate"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  color: 'var(--text-secondary)',
                }}
              >
                {event.message ?? event.event}
              </span>
              <span
                className="shrink-0"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                }}
              >
                {relativeTime(event.timestamp)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
