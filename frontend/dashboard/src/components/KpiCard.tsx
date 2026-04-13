"use client";
import { useState } from "react";

interface PatientInfo {
  id: string;
  name: string;
  score: number;
}

interface KpiCardProps {
  label: string;
  value: number | string;
  emoji: string;
  color: "danger" | "warning" | "success" | "primary";
  trend?: { value: number; label: string };
  patients?: PatientInfo[];
  onPatientClick?: (id: string) => void;
}

const colorConfig = {
  danger: {
    bg: "bg-danger-50",
    iconBg: "bg-danger-500/10",
    iconText: "text-danger-500",
    valueText: "text-danger-500",
    border: "border-danger-100",
  },
  warning: {
    bg: "bg-warning-50",
    iconBg: "bg-warning-500/10",
    iconText: "text-warning-500",
    valueText: "text-warning-500",
    border: "border-warning-100",
  },
  success: {
    bg: "bg-success-50",
    iconBg: "bg-success-500/10",
    iconText: "text-success-500",
    valueText: "text-success-500",
    border: "border-success-100",
  },
  primary: {
    bg: "bg-primary-50",
    iconBg: "bg-primary-500/10",
    iconText: "text-primary-500",
    valueText: "text-primary-500",
    border: "border-primary-100",
  },
};

export default function KpiCard({ label, value, emoji, color, trend, patients, onPatientClick }: KpiCardProps) {
  const c = colorConfig[color];
  const [expanded, setExpanded] = useState(false);
  const hasPatients = patients && patients.length > 0;

  return (
    <div
      className={`group rounded-2xl border border-gray-100 bg-white shadow-card transition-all duration-200 hover:shadow-card-hover ${hasPatients ? "cursor-pointer" : ""}`}
      onClick={() => hasPatients && setExpanded(!expanded)}
    >
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[13px] font-medium text-gray-400">{label}</p>
            <p className={`mt-2 text-3xl font-extrabold tracking-tight ${c.valueText}`}>
              {value}
            </p>
            {trend && (
              <p className={`mt-1.5 text-xs font-medium ${trend.value >= 0 ? "text-success-500" : "text-danger-500"}`}>
                {trend.value >= 0 ? "+" : ""}{trend.value}% {trend.label}
              </p>
            )}
          </div>
          <div className="flex flex-col items-center gap-1.5">
            <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${c.iconBg}`}>
              <span className="text-xl">{emoji}</span>
            </div>
            {hasPatients && (
              <span className={`text-[10px] font-medium transition-transform duration-200 ${c.iconText} ${expanded ? "rotate-180" : ""}`}>
                ▼
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Expandable patient list */}
      {hasPatients && expanded && (
        <div className={`border-t ${c.border} px-5 pb-4 pt-3`}>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
            Patientes ({patients.length})
          </p>
          <div className="flex flex-col gap-1.5">
            {patients.map((p) => (
              <button
                key={p.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onPatientClick?.(p.id);
                }}
                className={`flex items-center justify-between rounded-lg px-3 py-2 text-left transition-colors ${c.bg} hover:opacity-80`}
              >
                <span className="text-[12px] font-medium text-gray-700">{p.name}</span>
                <span className={`text-[12px] font-bold ${c.valueText}`}>{p.score}/100</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
