"use client";
import { getRiskEmoji, getRiskLabel } from "@/lib/types";

interface PatientCardProps {
  name: string;
  score: number;
  coaching: string;
  onClick?: () => void;
}

export default function PatientCard({ name, score, coaching, onClick }: PatientCardProps) {
  const scoreColor =
    score >= 70 ? "text-danger-500" : score >= 40 ? "text-warning-500" : "text-success-500";
  const barColor =
    score >= 70 ? "bg-danger-500" : score >= 40 ? "bg-warning-500" : "bg-success-500";
  const barBg =
    score >= 70 ? "bg-danger-50" : score >= 40 ? "bg-warning-50" : "bg-success-50";
  const badgeBg =
    score >= 70 ? "bg-danger-50 text-danger-500" : score >= 40 ? "bg-warning-50 text-warning-500" : "bg-success-50 text-success-500";

  return (
    <div
      onClick={onClick}
      className="group flex cursor-pointer items-center gap-4 rounded-2xl border border-gray-100 bg-white p-4 shadow-card transition-all duration-200 hover:border-gray-200 hover:shadow-card-hover"
    >
      {/* Avatar */}
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gray-100 text-lg">
        {getRiskEmoji(score)}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="font-semibold text-gray-800">{name}</p>
          <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase ${badgeBg}`}>
            {getRiskLabel(score)}
          </span>
        </div>
        <p className="mt-0.5 truncate text-[13px] text-gray-400">{coaching}</p>
        {/* Score bar */}
        <div className={`mt-2 h-1.5 w-full overflow-hidden rounded-full ${barBg}`}>
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      {/* Score */}
      <div className="text-right">
        <p className={`text-2xl font-extrabold tracking-tight ${scoreColor}`}>{score}</p>
        <p className="text-[11px] text-gray-400">/100</p>
      </div>

      {/* Arrow */}
      <svg className="h-4 w-4 shrink-0 text-gray-300 transition-transform group-hover:translate-x-0.5 group-hover:text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
      </svg>
    </div>
  );
}
