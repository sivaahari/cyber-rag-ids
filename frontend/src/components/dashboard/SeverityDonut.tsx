// components/dashboard/SeverityDonut.tsx
"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { SEVERITY_CHART_COLOR } from "@/lib/utils";
import type { SeverityLevel } from "@/types";

interface Props {
  data: Partial<Record<SeverityLevel, number>>;
}

export function SeverityDonut({ data }: Props) {
  const chartData = (Object.entries(data) as [SeverityLevel, number][])
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value, color: SEVERITY_CHART_COLOR[name] }));

  const total = chartData.reduce((s, d) => s + d.value, 0);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-sm font-semibold text-white">Severity Breakdown</h2>
      {total === 0 ? (
        <div className="flex h-40 items-center justify-center">
          <p className="text-xs text-slate-600">No predictions yet</p>
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <ResponsiveContainer width={120} height={120}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={35}
                outerRadius={55}
                dataKey="value"
                strokeWidth={0}
              >
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  borderRadius: 6,
                  fontSize: 12,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-col gap-1.5">
            {chartData.map(({ name, value, color }) => (
              <div key={name} className="flex items-center gap-2 text-xs">
                <span
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: color }}
                />
                <span className="text-slate-400">{name}</span>
                <span className="ml-auto font-mono text-white">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
