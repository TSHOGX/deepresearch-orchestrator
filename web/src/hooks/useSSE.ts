"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SSEEvent, EventType } from "@/types";
import { getStreamUrl } from "@/lib/api";

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  onClose?: () => void;
  reconnectOnError?: boolean;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
}

interface UseSSEReturn {
  isConnected: boolean;
  error: Error | null;
  lastEvent: SSEEvent | null;
  connect: () => void;
  disconnect: () => void;
}

export function useSSE(
  sessionId: string | null,
  options: UseSSEOptions = {}
): UseSSEReturn {
  const {
    onEvent,
    onError,
    onOpen,
    onClose,
    reconnectOnError = true,
    reconnectDelay = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
    reconnectAttemptsRef.current = 0;
  }, []);

  const connect = useCallback(() => {
    if (!sessionId) return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = getStreamUrl(sessionId);
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
      reconnectAttemptsRef.current = 0;
      onOpen?.();
    };

    eventSource.onerror = (e) => {
      const err = new Error("SSE connection error");
      setError(err);
      setIsConnected(false);
      onError?.(err);

      // Attempt reconnection
      if (
        reconnectOnError &&
        reconnectAttemptsRef.current < maxReconnectAttempts
      ) {
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectDelay);
      } else {
        eventSource.close();
        eventSourceRef.current = null;
        onClose?.();
      }
    };

    // Handle all event types
    const eventTypes: EventType[] = [
      "plan_draft",
      "plan_updated",
      "phase_change",
      "agent_started",
      "agent_progress",
      "agent_completed",
      "agent_failed",
      "checkpoint_saved",
      "synthesis_started",
      "synthesis_progress",
      "report_ready",
      "error",
      "heartbeat",
      "session_cancelled",
    ];

    eventTypes.forEach((eventType) => {
      eventSource.addEventListener(eventType, (e: MessageEvent) => {
        try {
          const event = JSON.parse(e.data) as SSEEvent;
          setLastEvent(event);
          onEvent?.(event);
        } catch (err) {
          console.error("Failed to parse SSE event:", err);
        }
      });
    });
  }, [
    sessionId,
    onEvent,
    onError,
    onOpen,
    onClose,
    reconnectOnError,
    reconnectDelay,
    maxReconnectAttempts,
  ]);

  // Auto-connect when sessionId changes
  useEffect(() => {
    if (sessionId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [sessionId, connect, disconnect]);

  return {
    isConnected,
    error,
    lastEvent,
    connect,
    disconnect,
  };
}
