// ============================================================
// hooks/useChat.ts
// Chat state management — message history, sending, loading.
// ============================================================

"use client";

import { useCallback, useState } from "react";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage, ChatResponse, PredictionResult } from "@/types";

interface UseChatReturn {
  messages:     ChatMessage[];
  lastResponse: ChatResponse | null;
  isLoading:    boolean;
  error:        string | null;
  sendMessage:  (q: string, ctx?: PredictionResult) => Promise<void>;
  clearChat:    () => void;
}

export function useChat(): UseChatReturn {
  const [messages,     setMessages]     = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [isLoading,    setIsLoading]    = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  const sendMessage = useCallback(
    async (question: string, predictionContext?: PredictionResult) => {
      if (!question.trim() || isLoading) return;

      const userMsg: ChatMessage = { role: "user", content: question };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const response = await sendChatMessage({
          question,
          history:             messages,
          prediction_context:  predictionContext,
        });

        const assistantMsg: ChatMessage = {
          role:    "assistant",
          content: response.answer,
        };

        setMessages((prev) => [...prev, assistantMsg]);
        setLastResponse(response);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Chat request failed";
        setError(msg);
        // Remove the user message on error so they can retry:
        setMessages((prev) => prev.slice(0, -1));
      } finally {
        setIsLoading(false);
      }
    },
    [messages, isLoading]
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    setLastResponse(null);
    setError(null);
  }, []);

  return { messages, lastResponse, isLoading, error, sendMessage, clearChat };
}
