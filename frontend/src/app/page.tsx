// app/page.tsx — Dashboard
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Square, Trash2, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";

import { StatsCards }    from "@/components/dashboard/StatsCards";
import { TrafficChart }  from "@/components/dashboard/TrafficChart";
import { AnomalyFeed }   from "@/components/dashboard/AnomalyFeed";
import { SeverityDonut } from "@/components/dashboard/SeverityDonut";
import { LoadingSpinner }from "@/components/shared/LoadingSpinner";
import { ErrorAlert }    from "@/components/shared/ErrorAlert";

import { useWebSocket }  from "@/hooks/useWebSocket";
import { fetchHealth, fetchModelInfo, predictSingle } from "@/lib/api";
import { generateFakeFlow } from "@/lib/utils";

import type {
  DashboardStats, HealthResponse, ModelInfoResponse,
  SeverityLevel, TrafficDataPoint,
} from "@/types";

const MAX_CHART_POINTS = 30;

export default function DashboardPage() {
  // ── WebSocket ────────────────────────────────────────────────
  const { status, feed, totalSeen, anomalyCount, connect, disconnect, clearFeed }
    = useWebSocket();

  // ── System info ───────────────────────────────────────────────
  const [health,     setHealth]     = useState<HealthResponse | null>(null);
  const [modelInfo,  setModelInfo]  = useState<ModelInfoResponse | null>(null);
  const [infoError,  setInfoError]  = useState<string | null>(null);
  const [infoLoading,setInfoLoading]= useState(true);

  // ── Chart data ────────────────────────────────────────────────
  const [chartData,   setChartData]   = useState<TrafficDataPoint[]>([]);
  const [sevBreakdown, setSevBreakdown] = useState<Partial<Record<SeverityLevel, number>>>({});

  // ── Demo streaming ────────────────────────────────────────────
  const [demoRunning, setDemoRunning] = useState(false);
  const demoTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Load system info on mount ─────────────────────────────────
  useEffect(() => {
    Promise.all([fetchHealth(), fetchModelInfo()])
      .then(([h, m]) => { setHealth(h); setModelInfo(m); })
      .catch((e) => setInfoError(e.message))
      .finally(() => setInfoLoading(false));
  }, []);

  // ── Build chart data from feed ────────────────────────────────
  useEffect(() => {
    if (feed.length === 0) return;
    const latest = feed[0];
    const point: TrafficDataPoint = {
      time:   new Date().toLocaleTimeString("en-US", { hour12: false }).slice(0, 8),
      normal: latest.is_anomaly ? 0 : 1,
      attack: latest.is_anomaly ? 1 : 0,
      total:  1,
    };
    setChartData((prev) => [...prev.slice(-(MAX_CHART_POINTS - 1)), point]);

    // Update severity breakdown:
    if (latest.is_anomaly) {
      setSevBreakdown((prev) => ({
        ...prev,
        [latest.severity]: (prev[latest.severity] ?? 0) + 1,
      }));
    }
  }, [feed]);

  // ── Demo mode: send fake flows to backend every 800ms ─────────
  const startDemo = useCallback(async () => {
    setDemoRunning(true);
    toast.success("Demo mode started — sending simulated traffic");
    demoTimer.current = setInterval(async () => {
      const isAttack = Math.random() < 0.25;   // 25% attack rate
      try {
        await predictSingle(generateFakeFlow(isAttack) as any);
      } catch { /* ignore */ }
    }, 800);
  }, []);

  const stopDemo = useCallback(() => {
    if (demoTimer.current) clearInterval(demoTimer.current);
    setDemoRunning(false);
    toast("Demo stopped");
  }, []);

  useEffect(() => () => { if (demoTimer.current) clearInterval(demoTimer.current); }, []);

  // ── Stats ─────────────────────────────────────────────────────
  const stats: DashboardStats = {
    totalAnalysed:  totalSeen,
    anomalyCount,
    normalCount:    totalSeen - anomalyCount,
    anomalyRate:    totalSeen > 0 ? anomalyCount / totalSeen : 0,
    avgProbability: feed.length > 0
      ? feed.reduce((s, f) => s + f.probability, 0) / feed.length
      : 0,
    lastUpdated: feed[0]?.timestamp ?? new Date().toISOString(),
  };

  // ── Render ────────────────────────────────────────────────────
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">
            Security Dashboard
          </h1>
          <p className="text-sm text-slate-500">
            Real-time network anomaly detection &amp; threat monitoring
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          {/* WebSocket toggle */}
          <button
            onClick={status === "connected" ? disconnect : connect}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition-all ${
              status === "connected"
                ? "bg-red-500/10 text-red-400 ring-red-500/30 hover:bg-red-500/20"
                : "bg-cyan-500/10 text-cyan-400 ring-cyan-500/30 hover:bg-cyan-500/20"
            }`}
          >
            {status === "connected"
              ? <><Square  className="h-3.5 w-3.5" /> Disconnect</>
              : <><Play    className="h-3.5 w-3.5" /> Live Stream</>}
          </button>

          {/* Demo mode */}
          <button
            onClick={demoRunning ? stopDemo : startDemo}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition-all ${
              demoRunning
                ? "bg-orange-500/10 text-orange-400 ring-orange-500/30"
                : "bg-slate-800 text-slate-400 ring-slate-700 hover:bg-slate-700"
            }`}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${demoRunning ? "animate-spin" : ""}`} />
            {demoRunning ? "Stop Demo" : "Demo Mode"}
          </button>

          {/* Clear */}
          <button
            onClick={() => { clearFeed(); setChartData([]); setSevBreakdown({}); }}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 ring-1 ring-slate-800 hover:bg-slate-800 hover:text-slate-300 transition-all"
          >
            <Trash2 className="h-3.5 w-3.5" /> Clear
          </button>
        </div>
      </div>

      {/* System info banner */}
      {infoLoading && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <LoadingSpinner size="sm" /> Loading system info…
        </div>
      )}
      {infoError && <ErrorAlert message={infoError} />}
      {health && modelInfo && !infoLoading && (
        <div className="flex flex-wrap gap-3 rounded-xl border border-slate-800 bg-slate-900/50 px-4 py-2.5 text-xs">
          <span className="text-slate-500">
            Status: <span className={`font-medium ${
              health.status === "ok" ? "text-emerald-400" :
              health.status === "degraded" ? "text-yellow-400" : "text-red-400"
            }`}>{health.status.toUpperCase()}</span>
          </span>
          <span className="text-slate-700">·</span>
          <span className="text-slate-500">
            LSTM: <span className={`font-medium ${health.services.lstm === "ok" ? "text-emerald-400" : "text-red-400"}`}>{health.services.lstm}</span>
          </span>
          <span className="text-slate-700">·</span>
          <span className="text-slate-500">
            RAG: <span className={`font-medium ${health.services.rag === "ok" ? "text-emerald-400" : "text-yellow-400"}`}>{health.services.rag}</span>
          </span>
          <span className="text-slate-700">·</span>
          <span className="text-slate-500">
            Model: <span className="font-medium text-slate-300">{modelInfo.architecture} · {modelInfo.num_features} features · {modelInfo.device}</span>
          </span>
          <span className="text-slate-700">·</span>
          <span className="text-slate-500">
            Threshold: <span className="font-medium text-slate-300">{modelInfo.anomaly_threshold}</span>
          </span>
        </div>
      )}

      {/* Stats cards */}
      <StatsCards stats={stats} />

      {/* Charts row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TrafficChart data={chartData} />
        </div>
        <SeverityDonut data={sevBreakdown} />
      </div>

      {/* Anomaly feed */}
      <AnomalyFeed feed={feed} status={status} />
    </div>
  );
}
