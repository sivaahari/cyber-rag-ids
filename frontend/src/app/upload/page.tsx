// app/upload/page.tsx
"use client";

import { useState } from "react";
import { FileText, Wifi, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import toast from "react-hot-toast";

import { DropZone }     from "@/components/upload/DropZone";
import { ResultsTable } from "@/components/upload/ResultsTable";
import { LoadingSpinner }from "@/components/shared/LoadingSpinner";
import { ErrorAlert }   from "@/components/shared/ErrorAlert";

import { uploadCSV, uploadPCAP } from "@/lib/api";
import { fmtNumber, fmtPercent, fmtMs } from "@/lib/utils";
import type { UploadResponse } from "@/types";

export default function UploadPage() {
  const [activeTab, setActiveTab]   = useState<"csv" | "pcap">("csv");
  const [uploading,  setUploading]  = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [result,     setResult]     = useState<UploadResponse | null>(null);

  const handleFile = async (file: File) => {
    setUploading(true);
    setError(null);
    setResult(null);

    const toastId = toast.loading(`Analysing ${file.name}…`);
    try {
      const res = activeTab === "csv"
        ? await uploadCSV(file)
        : await uploadPCAP(file);

      setResult(res);
      toast.success(
        `Done! ${res.anomaly_count} anomalies in ${res.rows_processed} flows`,
        { id: toastId }
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setError(msg);
      toast.error(msg, { id: toastId });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white">Upload & Analyse</h1>
        <p className="text-sm text-slate-500">
          Upload CSV or PCAP files for batch LSTM anomaly detection
        </p>
      </div>

      {/* Tab selector */}
      <div className="flex gap-1 rounded-xl border border-slate-800 bg-slate-900 p-1 w-fit">
        {(["csv", "pcap"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setResult(null); setError(null); }}
            className={`flex items-center gap-2 rounded-lg px-4 py-1.5 text-sm font-medium transition-all ${
              activeTab === tab
                ? "bg-cyan-500/15 text-cyan-400 ring-1 ring-cyan-500/30"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {tab === "csv"
              ? <FileText className="h-3.5 w-3.5" />
              : <Wifi     className="h-3.5 w-3.5" />}
            {tab.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Drop zone */}
      {!uploading && !result && (
        <div className="max-w-xl">
          <DropZone
            onFile={handleFile}
            accept={activeTab === "csv" ? ".csv" : ".pcap,.pcapng"}
            label={
              activeTab === "csv"
                ? "Upload NSL-KDD format CSV file"
                : "Upload Wireshark PCAP capture file"
            }
            disabled={uploading}
          />
          <p className="mt-2 text-xs text-slate-600">
            {activeTab === "csv"
              ? "Supports NSL-KDD format with or without header row. Max 50 MB."
              : "Supports .pcap and .pcapng files. Npcap must be installed. Max 100 MB."}
          </p>
        </div>
      )}

      {/* Loading */}
      {uploading && (
        <div className="flex flex-col items-center gap-4 py-12">
          <LoadingSpinner size="lg" />
          <div className="text-center">
            <p className="text-sm font-medium text-white">Analysing traffic…</p>
            <p className="text-xs text-slate-500 mt-1">
              Running LSTM inference on all flows
            </p>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <ErrorAlert
          message={error}
          onDismiss={() => setError(null)}
          className="max-w-xl"
        />
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { icon: FileText,       label: "Total Flows",  value: fmtNumber(result.rows_processed), color: "text-slate-300" },
              { icon: AlertTriangle,  label: "Anomalies",    value: fmtNumber(result.anomaly_count),  color: "text-red-400"   },
              { icon: CheckCircle,    label: "Normal",       value: fmtNumber(result.normal_count),   color: "text-emerald-400" },
              { icon: Clock,          label: "Processed in", value: fmtMs(result.processing_ms),      color: "text-cyan-400"  },
            ].map(({ icon: Icon, label, value, color }) => (
              <div key={label} className="rounded-xl border border-slate-800 bg-slate-900 px-4 py-3">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className={`h-3.5 w-3.5 ${color}`} />
                  <span className="text-xs text-slate-500">{label}</span>
                </div>
                <p className={`text-xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Anomaly rate pill */}
          <div className="flex items-center gap-3">
            <div className="h-2 flex-1 rounded-full bg-slate-800 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-red-500 transition-all"
                style={{ width: `${result.anomaly_rate * 100}%` }}
              />
            </div>
            <span className="text-sm font-mono text-slate-400 shrink-0">
              {fmtPercent(result.anomaly_rate)} anomaly rate
            </span>
          </div>

          {/* Results table */}
          <ResultsTable results={result.results} />

          {/* Re-upload */}
          <button
            onClick={() => setResult(null)}
            className="text-xs text-slate-600 hover:text-slate-400 transition-colors"
          >
            ← Upload another file
          </button>
        </div>
      )}
    </div>
  );
}
