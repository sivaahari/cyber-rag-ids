// components/chat/ChatInput.tsx
"use client";

import { useRef, useState, KeyboardEvent } from "react";
import { Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onSend:    (q: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

const QUICK_PROMPTS = [
  "What is a SYN flood attack?",
  "How do I respond to a brute force alert?",
  "Explain the MITRE ATT&CK framework",
  "What does high serror_rate mean?",
];

export function ChatInput({ onSend, isLoading, disabled }: Props) {
  const [value, setValue] = useState("");
  const textareaRef       = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const q = value.trim();
    if (!q || isLoading || disabled) return;
    onSend(q);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  return (
    <div className="space-y-3">
      {/* Quick prompts */}
      <div className="flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => { setValue(p); textareaRef.current?.focus(); }}
            disabled={isLoading || disabled}
            className="rounded-full border border-slate-700 bg-slate-800/50 px-3 py-1 text-xs text-slate-400 transition-all hover:border-cyan-500/40 hover:text-cyan-400 disabled:opacity-40"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input area */}
      <div className="flex items-end gap-2 rounded-xl border border-slate-700 bg-slate-900 p-2 ring-1 ring-transparent focus-within:border-cyan-500/50 focus-within:ring-cyan-500/20 transition-all">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={isLoading || disabled}
          placeholder="Ask the cybersecurity advisor… (Enter to send, Shift+Enter for newline)"
          rows={1}
          className="flex-1 resize-none bg-transparent text-sm text-slate-200 placeholder-slate-600 outline-none disabled:opacity-50 min-h-[36px] max-h-40 py-1 px-1"
        />
        <button
          onClick={handleSend}
          disabled={!value.trim() || isLoading || disabled}
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-all",
            value.trim() && !isLoading && !disabled
              ? "bg-cyan-600 text-white hover:bg-cyan-500"
              : "bg-slate-800 text-slate-600"
          )}
        >
          {isLoading
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Send    className="h-4 w-4" />}
        </button>
      </div>
      <p className="text-[10px] text-slate-700 text-right">
        Powered by {"{"}llama3.2{"}"} + LangChain + ChromaDB · Local inference only
      </p>
    </div>
  );
}
