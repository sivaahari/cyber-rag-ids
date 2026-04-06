// app/reports/page.tsx
"use client";

import { useEffect, useState } from "react";
import { FileText, Trash2, Eye, RefreshCw, AlertTriangle } from "lucide-react";
import toast from "react-hot-toast";

import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorAlert }     from "@/components/shared/ErrorAlert";
import { ResultsTable }   from "@/components/upload/ResultsTable";
import { SeverityBadge }  from "@/components/shared/SeverityBadge";

import { deleteReport, fetchReport, fetchReports } from "@/lib/api";
import { fmtDate, fmtNumber, fmtPercent } from "@/lib/utils";
import type { PredictionResult, ReportSummary } from "@/types";

export default function ReportsPage() {
  const [reports,  setReports]  = useState<ReportSummary[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail,   setDetail]   = useState<PredictionResult[] | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReports();
      setReports(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load reports");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadReports(); }, []);

  const handleView = async (id: string) => {
    if (selected === id) { setSelected(null); setDetail(null); return; }
    setSelected(id);
    setDetail(null);
    setDetailLoading(true);
    try {
      const data = await fetchReport(id) as { results: PredictionResult[] };
      setDetail(data.results ?? []);
    } catch (e) {
      toast.error("Failed to load report details");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this report permanently?")) return;
    try {
      await deleteReport(id);
      setReports((prev) => prev.filter((r) => r.report_id !== id));
      if (selected === id) { setSelected(null); setDetail(null); }
      toast.success("Report deleted");
    } catch {
      toast.error("Failed to delete report");
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Analysis Reports</h1>
          <p className="text-sm text-slate-500">
            Saved batch analysis results from CSV &amp; PCAP uploads
          </p>
        </div>
        <button
          onClick={loadReports}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-400 ring-1 ring-slate-700 hover:bg-slate-800 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <LoadingSpinner size="sm" /> Loading reports…
        </div>
      )}
      {error && <ErrorAlert message={error} />}

      {!loading && reports.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <div className="rounded-full bg-slate-800 p-4">
            <FileText className="h-8 w-8 text-slate-600" />
          </div>
          <p className="text-sm text-slate-500">
            No reports yet. Upload a CSV or PCAP file to generate one.
          </p>
        </div>
      )}

      {/* Reports list */}
      {reports.length > 0 && (
        <div className="space-y-2">
          {reports.map((report) => {
            const isOpen = selected === report.report_id;
            return (
              <div
                key={report.report_id}
                className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden"
              >
                {/* Report row */}
                <div className="flex items-center gap-4 px-4 py-3">
                  <FileText className="h-4 w-4 shrink-0 text-slate-500" />

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">
                      {report.filename}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {fmtDate(report.created_at)} ·{" "}
                      {fmtNumber(report.total_flows)} flows ·{" "}
                      {fmtPercent(report.anomaly_rate)} anomaly rate
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    {report.anomaly_count > 0 ? (
                      <div className="flex items-center gap-1.5 text-xs text-red-400">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {report.anomaly_count}
                      </div>
                    ) : (
                      <div className="text-xs text-emerald-400">Clean</div>
                    )}

                    <button
                      onClick={() => handleView(report.report_id)}
                      className={`flex items-center gap-1 rounded px-2 py-1 text-xs transition-all ${
                        isOpen
                          ? "bg-cyan-500/15 text-cyan-400"
                          : "text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      <Eye className="h-3 w-3" />
                      {isOpen ? "Hide" : "View"}
                    </button>

                    <button
                      onClick={() => handleDelete(report.report_id)}
                      className="rounded p-1 text-slate-600 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Expanded detail */}
                {isOpen && (
                  <div className="border-t border-slate-800 p-4">
                    {detailLoading ? (
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <LoadingSpinner size="sm" /> Loading results…
                      </div>
                    ) : detail ? (
                      <ResultsTable results={detail} />
                    ) : null}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
