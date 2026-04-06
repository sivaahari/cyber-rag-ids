// components/dashboard/AnomalyFeed.tsx
"use client";

import { AlertTriangle, Wifi } from "lucide-react";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { fmtProbability, fmtTimestamp } from "@/lib/utils";
import type { LiveFeedEntry, WSStatus } from "@/hooks/useWebSocket";

interface Props {
  feed:   LiveFeedEntry[];
  status: WSStatus;
}

export function AnomalyFeed({ feed, status }: Props) {
  const statusColor = {
    connected:    "bg-emerald-400",
    connecting:   "bg-yellow-400 animate-pulse",
    disconnected: "bg-slate-600",
    error:        "bg-red-400",
  }[status];

  const anomalies = feed.filter((e) => e.is_anomaly);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-400" />
          <h2 className="text-sm font-semibold text-white">Anomaly Feed</h2>
          {anomalies.length > 0 && (
            <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-bold text-red-400 ring-1 ring-red-500/30">
              {anomalies.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Wifi className="h-3 w-3" />
          <span className={`h-2 w-2 rounded-full ${statusColor}`} />
          <span className="capitalize">{status}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 min-h-0 max-h-64">
        {anomalies.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <div className="h-8 w-8 rounded-full bg-emerald-400/10 flex items-center justify-center">
              <span className="text-emerald-400 text-lg">✓</span>
            </div>
            <p className="text-xs text-slate-600 text-center">
              No anomalies detected
              <br />
              {status === "disconnected" ? "— connect live stream to monitor" : "— traffic looks normal"}
            </p>
          </div>
        ) : (
          anomalies.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-400" />
                <div className="min-w-0">
                  <p className="text-xs font-mono text-red-300 truncate">
                    ID: {entry.prediction_id.slice(0, 8)}…
                  </p>
                  <p className="text-[10px] text-slate-500">
                    {fmtTimestamp(entry.timestamp)} · {fmtProbability(entry.probability)}
                  </p>
                </div>
              </div>
              <SeverityBadge severity={entry.severity} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
