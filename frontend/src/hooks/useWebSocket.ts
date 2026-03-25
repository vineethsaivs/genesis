import { useState, useEffect, useRef, useCallback } from 'react';

import type { AgentEvent } from '../lib/types';

const WS_URL = 'ws://localhost:8000/ws/agent';
const MAX_RECONNECT_DELAY = 30000;

export function useWebSocket(enabled: boolean) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<AgentEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(1000);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setError(null);
        reconnectDelayRef.current = 1000;
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data) as AgentEvent;
          setEvents((prev) => [...prev, data]);
          setLastEvent(data);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        wsRef.current = null;

        const delay = Math.min(reconnectDelayRef.current, MAX_RECONNECT_DELAY);
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelayRef.current = delay * 2;
          connect();
        }, delay);
      };

      ws.onerror = () => {
        if (!mountedRef.current) return;
        setError('WebSocket connection failed');
        ws.close();
      };
    } catch {
      setError('Failed to create WebSocket');
    }
  }, [enabled]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onopen = null;
        wsRef.current.onmessage = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const sendMessage = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { sendMessage, events, lastEvent, isConnected, error };
}
