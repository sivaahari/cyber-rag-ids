// components/upload/DropZone.tsx
"use client";

import { useCallback, useState } from "react";
import { Upload, FileText, Wifi } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  onFile:   (file: File) => void;
  accept:   string;           // e.g. ".csv" or ".pcap,.pcapng"
  label:    string;
  disabled?: boolean;
}

export function DropZone({ onFile, accept, label, disabled }: Props) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) onFile(file);
    },
    [onFile, disabled]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFile(file);
    e.target.value = "";   // reset so same file can be re-uploaded
  };

  const Icon = accept.includes("csv") ? FileText : Wifi;

  return (
    <label
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed",
        "cursor-pointer px-6 py-12 text-center transition-all duration-200",
        dragging && !disabled
          ? "border-cyan-400 bg-cyan-400/5"
          : "border-slate-700 bg-slate-900 hover:border-slate-600 hover:bg-slate-800/50",
        disabled && "cursor-not-allowed opacity-50"
      )}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <div className="rounded-full bg-slate-800 p-4 ring-1 ring-slate-700">
        <Icon className={cn("h-8 w-8", dragging ? "text-cyan-400" : "text-slate-500")} />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-300">
          {label}
        </p>
        <p className="mt-1 text-xs text-slate-600">
          Drag & drop or click to browse · {accept}
        </p>
      </div>
      <div className="rounded-lg bg-cyan-500/10 px-4 py-1.5 text-xs font-medium text-cyan-400 ring-1 ring-cyan-500/30">
        Choose File
      </div>
      <input
        type="file"
        accept={accept}
        onChange={handleChange}
        disabled={disabled}
        className="sr-only"
      />
    </label>
  );
}
