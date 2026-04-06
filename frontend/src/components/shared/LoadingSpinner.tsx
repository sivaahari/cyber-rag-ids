// components/shared/LoadingSpinner.tsx
import { cn } from "@/lib/utils";

interface Props { className?: string; size?: "sm" | "md" | "lg" }

export function LoadingSpinner({ className, size = "md" }: Props) {
  const sizes = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-10 w-10" };
  return (
    <div
      className={cn(
        "animate-spin rounded-full border-2 border-slate-700 border-t-cyan-400",
        sizes[size],
        className
      )}
    />
  );
}
