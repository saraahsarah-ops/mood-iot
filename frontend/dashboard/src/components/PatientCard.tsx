"use client";
import { getRiskEmoji, getRiskLabel } from "@/lib/types";

interface PatientCardProps {
  name: string;
  score: number;
  coaching: string;
  onClick?: () => void;
}

export default function PatientCard({ name, score, coaching, onClick }: PatientCardProps) {
  const borderColor =
    score >= 70 ? "border-danger" : score >= 40 ? "border-warning" : "border-success";

  return (
    <div
      onClick={onClick}
      className={`flex cursor-pointer items-center justify-between rounded-xl border-l-4 bg-white p-4 shadow-sm transition hover:shadow-md ${borderColor}`}
    >
      <div className="flex-1">
        <p className="font-semibold text-gray-800">
          {getRiskEmoji(score)} {name}
        </p>
        <p className="mt-1 text-sm text-gray-500 line-clamp-1">{coaching}</p>
      </div>
      <div className="ml-4 text-right">
        <p className="text-2xl font-bold text-gray-800">{score}</p>
        <p className="text-xs text-gray-400">{getRiskLabel(score)}</p>
      </div>
    </div>
  );
}
