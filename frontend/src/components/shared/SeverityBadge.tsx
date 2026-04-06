// components/shared/SeverityBadge.tsx
import { cn, SEVERITY_COLORS } from "@/lib/utils";
import type { SeverityLevel } from "@/types";

interface Props {
  severity:  SeverityLevel;
  className?: string;
}

export function SeverityBadge({ severity, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5",
        "text-xs font-semibold uppercase tracking-wide",
        SEVERITY_COLORS[severity],
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {severity}
    </span>
  );
}
