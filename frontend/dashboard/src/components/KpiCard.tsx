"use client";

interface KpiCardProps {
  label: string;
  value: number | string;
  emoji: string;
  color: "danger" | "warning" | "success" | "primary";
}

const colorMap = {
  danger: "border-danger bg-red-50 text-danger",
  warning: "border-warning bg-yellow-50 text-warning",
  success: "border-success bg-green-50 text-success",
  primary: "border-primary bg-blue-50 text-primary",
};

export default function KpiCard({ label, value, emoji, color }: KpiCardProps) {
  return (
    <div className={`rounded-xl border-l-4 bg-white p-5 shadow-sm ${colorMap[color]}`}>
      <p className="text-sm font-medium text-gray-500">{emoji} {label}</p>
      <p className="mt-1 text-3xl font-bold">{value}</p>
    </div>
  );
}
