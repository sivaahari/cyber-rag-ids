// app/chat/page.tsx
"use client";

import { useState } from "react";
import { Trash2, Info } from "lucide-react";

import { ChatWindow }   from "@/components/chat/ChatWindow";
import { ChatInput }    from "@/components/chat/ChatInput";
import { ErrorAlert }   from "@/components/shared/ErrorAlert";
import { SeverityBadge }from "@/components/shared/SeverityBadge";

import { useChat }      from "@/hooks/useChat";
import type { PredictionResult } from "@/types";

export default function ChatPage() {
  const { messages, lastResponse, isLoading, error, sendMessage, clearChat } = useChat();
  const [injectedAlert, setInjectedAlert] = useState<PredictionResult | null>(null);

  // Demo alert for testing RAG context injection:
  const demoAlert: PredictionResult = {
    prediction_id: "demo-alert-001",
    label:         "ATTACK",
    probability:   0.94,
    severity:      "CRITICAL",
    threshold:     0.5,
    is_anomaly:    true,
    timestamp:     new Date().toISOString(),
    inference_ms:  1.8,
  };

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-white">RAG Cyber Advisor</h1>
          <p className="text-sm text-slate-500">
            Powered by {"{"}llama3.2{"}"} + LangChain + local knowledge base
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Inject demo alert context */}
          <button
            onClick={() =>
              setInjectedAlert((prev) => (prev ? null : demoAlert))
            }
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition-all ${
              injectedAlert
                ? "bg-red-500/15 text-red-400 ring-red-500/30"
                : "bg-slate-800 text-slate-400 ring-slate-700 hover:bg-slate-700"
            }`}
          >
            <Info className="h-3.5 w-3.5" />
            {injectedAlert ? "Clear Alert" : "Inject Alert Context"}
          </button>

          <button
            onClick={clearChat}
            disabled={messages.length === 0}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 ring-1 ring-slate-800 hover:bg-slate-800 hover:text-slate-300 transition-all disabled:opacity-30"
          >
            <Trash2 className="h-3.5 w-3.5" /> Clear
          </button>
        </div>
      </div>

      {/* Injected alert banner */}
      {injectedAlert && (
        <div className="mb-3 flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/5 px-4 py-3">
          <div className="flex-1">
            <p className="text-xs font-semibold text-red-400">
              Active Alert Context — Advisor will reference this detection
            </p>
            <p className="text-[10px] text-slate-500 mt-0.5">
              ID: {injectedAlert.prediction_id} · Prob: {(injectedAlert.probability * 100).toFixed(1)}%
            </p>
          </div>
          <SeverityBadge severity={injectedAlert.severity} />
        </div>
      )}

      {/* Error */}
      {error && (
        <ErrorAlert message={error} className="mb-3" />
      )}

      {/* Chat window — flex-1 scrollable */}
      <div className="flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/50 px-4 py-4 mb-4">
        <ChatWindow
          messages={messages}
          lastResponse={lastResponse}
          isLoading={isLoading}
        />
      </div>

      {/* Input */}
      <ChatInput
        onSend={(q) => sendMessage(q, injectedAlert ?? undefined)}
        isLoading={isLoading}
      />
    </div>
  );
}
