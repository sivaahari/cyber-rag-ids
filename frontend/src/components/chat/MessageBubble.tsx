// components/chat/MessageBubble.tsx
"use client";

import { Shield, User } from "lucide-react";
import { cn, fmtMs } from "@/lib/utils";
import type { ChatMessage } from "@/types";

interface Props {
  message:     ChatMessage;
  responseMs?: number;
  sources?:    string[];
}

export function MessageBubble({ message, responseMs, sources }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-1",
          isUser
            ? "bg-slate-700 ring-slate-600"
            : "bg-cyan-500/20 ring-cyan-500/40"
        )}
      >
        {isUser
          ? <User   className="h-4 w-4 text-slate-300" />
          : <Shield className="h-4 w-4 text-cyan-400"  />}
      </div>

      {/* Bubble */}
      <div className={cn("max-w-[80%] space-y-1", isUser && "items-end flex flex-col")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "rounded-tr-sm bg-cyan-600/20 text-slate-200 ring-1 ring-cyan-500/30"
              : "rounded-tl-sm bg-slate-800 text-slate-200 ring-1 ring-slate-700"
          )}
        >
          {/* Render assistant markdown-ish content with pre-wrap */}
          {isUser ? (
            <p>{message.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none">
              <FormattedContent content={message.content} />
            </div>
          )}
        </div>

        {/* Sources + timing */}
        {!isUser && (sources?.length || responseMs) && (
          <div className="flex flex-wrap items-center gap-2 px-1">
            {sources?.map((src) => (
              <span
                key={src}
                className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-slate-500 ring-1 ring-slate-700"
              >
                {src}
              </span>
            ))}
            {responseMs && (
              <span className="text-[10px] text-slate-600">
                {fmtMs(responseMs)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Lightweight markdown renderer (no external library needed):
function FormattedContent({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    if (line.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="mt-3 mb-1 text-sm font-bold text-white">
          {line.slice(3)}
        </h3>
      );
    } else if (line.startsWith("### ")) {
      elements.push(
        <h4 key={i} className="mt-2 mb-0.5 text-xs font-semibold text-cyan-400 uppercase tracking-wide">
          {line.slice(4)}
        </h4>
      );
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <li key={i} className="ml-4 list-disc text-slate-300 text-xs">
          {renderInline(line.slice(2))}
        </li>
      );
    } else if (/^\d+\. /.test(line)) {
      const text = line.replace(/^\d+\. /, "");
      elements.push(
        <li key={i} className="ml-4 list-decimal text-slate-300 text-xs">
          {renderInline(text)}
        </li>
      );
    } else if (line.startsWith("```")) {
      // Skip code fence markers
    } else if (line.trim() === "") {
      elements.push(<br key={i} />);
    } else {
      elements.push(
        <p key={i} className="text-slate-300 text-xs leading-relaxed">
          {renderInline(line)}
        </p>
      );
    }
  });

  return <>{elements}</>;
}

function renderInline(text: string): React.ReactNode {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={i} className="rounded bg-slate-700 px-1 py-0.5 font-mono text-cyan-300 text-[10px]">{part.slice(1, -1)}</code>;
    return part;
  });
}
