// components/upload/ResultsTable.tsx
"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { SeverityBadge } from "@/components/shared/SeverityBadge";
import { fmtProbability, fmtTimestamp, fmtMs } from "@/lib/utils";
import type { PredictionResult } from "@/types";

interface Props { results: PredictionResult[] }

const PAGE_SIZE = 15;

export function ResultsTable({ results }: Props) {
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState<"all" | "attack" | "normal">("all");

  const filtered =
    filter === "all"    ? results :
    filter === "attack" ? results.filter((r) => r.is_anomaly) :
                          results.filter((r) => !r.is_anomaly);

  const pages    = Math.ceil(filtered.length / PAGE_SIZE);
  const pageData = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      {/* Filter bar */}
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <p className="text-sm text-slate-400">
          Showing <span className="font-medium text-white">{filtered.length}</span> results
        </p>
        <div className="flex gap-1">
          {(["all", "attack", "normal"] as const).map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(0); }}
              className={`rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-all ${
                filter === f
                  ? "bg-cyan-500/15 text-cyan-400 ring-1 ring-cyan-500/30"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-500">
              <th className="px-4 py-2.5 font-medium">#</th>
              <th className="px-4 py-2.5 font-medium">Label</th>
              <th className="px-4 py-2.5 font-medium">Probability</th>
              <th className="px-4 py-2.5 font-medium">Severity</th>
              <th className="px-4 py-2.5 font-medium">Inference</th>
              <th className="px-4 py-2.5 font-medium">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {pageData.map((row, i) => (
              <tr
                key={row.prediction_id}
                className={`transition-colors hover:bg-slate-800/30 ${
                  row.is_anomaly ? "bg-red-500/3" : ""
                }`}
              >
                <td className="px-4 py-2.5 font-mono text-slate-600">
                  {page * PAGE_SIZE + i + 1}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`font-semibold ${
                      row.is_anomaly ? "text-red-400" : "text-emerald-400"
                    }`}
                  >
                    {row.label}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-slate-300">
                  {fmtProbability(row.probability)}
                </td>
                <td className="px-4 py-2.5">
                  <SeverityBadge severity={row.severity} />
                </td>
                <td className="px-4 py-2.5 font-mono text-slate-500">
                  {fmtMs(row.inference_ms)}
                </td>
                <td className="px-4 py-2.5 text-slate-600">
                  {fmtTimestamp(row.timestamp)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-800 px-4 py-2.5">
          <p className="text-xs text-slate-600">
            Page {page + 1} of {pages}
          </p>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded p-1 text-slate-500 hover:text-slate-300 disabled:opacity-30"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
              disabled={page === pages - 1}
              className="rounded p-1 text-slate-500 hover:text-slate-300 disabled:opacity-30"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
