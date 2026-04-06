// ============================================================
// hooks/useWebSocket.ts
// WebSocket hook for real-time LSTM anomaly streaming.
// Manages connection lifecycle, reconnect logic, and message parsing.
// ============================================================

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PredictionResult, WSMessage } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
const RECONNECT_DELAY_MS = 3000;
const MAX_FEED_SIZE       = 100;

export type WSStatus = "connecting" | "connected" | "disconnected" | "error";

export interface LiveFeedEntry extends PredictionResult {
  id: string;
}

interface UseWebSocketReturn {
  status:       WSStatus;
  feed:         LiveFeedEntry[];
  totalSeen:    number;
  anomalyCount: number;
  connect:      () => void;
  disconnect:   () => void;
  clearFeed:    () => void;
}

export function useWebSocket(): UseWebSocketReturn {
  const wsRef          = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef     = useRef(true);

  const [status,       setStatus]       = useState<WSStatus>("disconnected");
  const [feed,         setFeed]         = useState<LiveFeedEntry[]>([]);
  const [totalSeen,    setTotalSeen]    = useState(0);
  const [anomalyCount, setAnomalyCount] = useState(0);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    if (wsRef.current) {
      wsRef.current.onclose = null;   // prevent reconnect on manual close
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("disconnected");
  }, []);

  const connect = useCallback(() => {
    // Don't open a second connection:
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus("connecting");

    const ws = new WebSocket(`${WS_URL}/ws/live-stream`);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setStatus("connected");
      // Keepalive ping every 30 s:
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        } else {
          clearInterval(ping);
        }
      }, 30_000);
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const msg: WSMessage = JSON.parse(event.data as string);

        if (msg.event === "prediction") {
          const result = msg.payload as unknown as PredictionResult;
          const entry: LiveFeedEntry = {
            ...result,
            id: `${result.prediction_id}-${Date.now()}`,
          };

          setFeed((prev) => [entry, ...prev].slice(0, MAX_FEED_SIZE));
          setTotalSeen((n) => n + 1);
          if (result.is_anomaly) setAnomalyCount((n) => n + 1);
        }
      } catch {
        // Silently ignore malformed messages
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setStatus("error");
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setStatus("disconnected");
      // Auto-reconnect after delay:
      reconnectTimer.current = setTimeout(() => {
        if (mountedRef.current) connect();
      }, RECONNECT_DELAY_MS);
    };
  }, []);    // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup on unmount:
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [disconnect]);

  const clearFeed = useCallback(() => {
    setFeed([]);
    setTotalSeen(0);
    setAnomalyCount(0);
  }, []);

  return { status, feed, totalSeen, anomalyCount, connect, disconnect, clearFeed };
}
