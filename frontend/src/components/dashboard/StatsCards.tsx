// components/dashboard/StatsCards.tsx
import { Activity, AlertTriangle, CheckCircle, TrendingUp } from "lucide-react";
import { fmtNumber, fmtPercent } from "@/lib/utils";
import type { DashboardStats } from "@/types";

interface Props { stats: DashboardStats }

export function StatsCards({ stats }: Props) {
  const cards = [
    {
      label: "Total Analysed",
      value: fmtNumber(stats.totalAnalysed),
      sub:   "flows processed",
      icon:  Activity,
      color: "text-cyan-400",
      bg:    "bg-cyan-400/10",
      ring:  "ring-cyan-400/20",
    },
    {
      label: "Anomalies",
      value: fmtNumber(stats.anomalyCount),
      sub:   `${fmtPercent(stats.anomalyRate)} of traffic`,
      icon:  AlertTriangle,
      color: "text-red-400",
      bg:    "bg-red-400/10",
      ring:  "ring-red-400/20",
    },
    {
      label: "Normal",
      value: fmtNumber(stats.normalCount),
      sub:   `${fmtPercent(1 - stats.anomalyRate)} of traffic`,
      icon:  CheckCircle,
      color: "text-emerald-400",
      bg:    "bg-emerald-400/10",
      ring:  "ring-emerald-400/20",
    },
    {
      label: "Avg Probability",
      value: fmtPercent(stats.avgProbability),
      sub:   "attack confidence",
      icon:  TrendingUp,
      color: "text-orange-400",
      bg:    "bg-orange-400/10",
      ring:  "ring-orange-400/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="rounded-xl border border-slate-800 bg-slate-900 p-4"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                  {card.label}
                </p>
                <p className="mt-1.5 text-2xl font-bold text-white">
                  {card.value}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">{card.sub}</p>
              </div>
              <div className={`rounded-lg p-2 ring-1 ${card.bg} ${card.ring}`}>
                <Icon className={`h-5 w-5 ${card.color}`} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
