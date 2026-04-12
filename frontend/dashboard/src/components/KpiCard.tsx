"use client";

interface KpiCardProps {
  label: string;
  value: number | string;
  emoji: string;
  color: "danger" | "warning" | "success" | "primary";
  trend?: { value: number; label: string };
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

export default function KpiCard({ label, value, emoji, color, trend }: KpiCardProps) {
  const c = colorConfig[color];

  return (
    <div className="group rounded-2xl border border-gray-100 bg-white p-5 shadow-card transition-all duration-200 hover:shadow-card-hover">
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
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${c.iconBg}`}>
          <span className="text-xl">{emoji}</span>
        </div>
      </div>
    </div>
  );
}
