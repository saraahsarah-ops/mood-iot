"use client";
import { getRiskEmoji, getRiskLabel } from "@/lib/types";
import Link from "next/link";

interface PatientCardProps {
  name: string;
  score: number;
  coaching: string;
  onClick?: () => void;
}

export default function PatientCard({ name, score, coaching, onClick }: PatientCardProps) {
  // Try to extract patient ID if onClick is not provided
  // Workaround since the original code only passes `onClick` from `page.tsx` but `page.tsx` uses router.push.
  // We'll wrap it in a Link if it's meant to be accessible. Since `onClick` is handled via router.push in page.tsx, 
  // we'll change the wrapper to a button if we only have onClick, or use a Link if we can.
  // We will just change it to a generic button for accessibility since `onClick` is what is used.
  const scoreColor =
    score >= 70 ? "text-danger-500" : score >= 40 ? "text-warning-500" : "text-success-500";
  const barColor =
    score >= 70 ? "bg-danger-500" : score >= 40 ? "bg-warning-500" : "bg-success-500";
  const barBg =
    score >= 70 ? "bg-danger-50" : score >= 40 ? "bg-warning-50" : "bg-success-50";
  const badgeBg =
    score >= 70 ? "bg-danger-50 text-danger-500" : score >= 40 ? "bg-warning-50 text-warning-500" : "bg-success-50 text-success-500";

  return (
    <button
      onClick={onClick}
      aria-label={`Fiche de ${name}, score de ${score} sur 100`}
      className="group flex w-full cursor-pointer items-center gap-4 rounded-2xl border border-gray-100 bg-white p-4 shadow-card text-left transition-all duration-200 hover:border-gray-200 hover:shadow-card-hover focus:outline-none focus:ring-2 focus:ring-primary-500"
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
        <div 
          className={`mt-2 h-1.5 w-full overflow-hidden rounded-full ${barBg}`}
          role="progressbar" 
          aria-valuenow={score} 
          aria-valuemin={0} 
          aria-valuemax={100}
        >
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
    </button>
  );
}
