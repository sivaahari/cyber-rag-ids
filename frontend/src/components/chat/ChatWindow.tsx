// components/chat/ChatWindow.tsx
"use client";

import { useEffect, useRef } from "react";
import { Shield } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import type { ChatMessage, ChatResponse } from "@/types";

interface Props {
  messages:     ChatMessage[];
  lastResponse: ChatResponse | null;
  isLoading:    boolean;
}

export function ChatWindow({ messages, lastResponse, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <div className="rounded-2xl bg-cyan-500/10 p-5 ring-1 ring-cyan-500/20">
          <Shield className="h-10 w-10 text-cyan-400" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-white">
            CyberGuard RAG Advisor
          </h3>
          <p className="mt-1 max-w-sm text-sm text-slate-500">
            Ask anything about network security, IDS alerts, threat intelligence,
            or incident response. I use a local knowledge base + LLM — no data leaves your machine.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 py-2">
      {messages.map((msg, i) => {
        const isLastAssistant =
          msg.role === "assistant" && i === messages.length - 1;
        return (
          <MessageBubble
            key={i}
            message={msg}
            responseMs={isLastAssistant ? lastResponse?.response_ms : undefined}
            sources={isLastAssistant ? lastResponse?.sources       : undefined}
          />
        );
      })}

      {isLoading && (
        <div className="flex gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 ring-1 ring-cyan-500/40">
            <Shield className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="rounded-2xl rounded-tl-sm bg-slate-800 px-4 py-3 ring-1 ring-slate-700">
            <div className="flex items-center gap-2">
              <LoadingSpinner size="sm" />
              <span className="text-xs text-slate-500 animate-pulse">
                Thinking…
              </span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
