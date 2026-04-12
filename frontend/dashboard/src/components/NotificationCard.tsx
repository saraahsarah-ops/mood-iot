"use client";

interface NotificationCardProps {
  patientName: string;
  score: number;
  message: string;
  time: string;
  read: boolean;
  onMarkRead?: () => void;
}

export default function NotificationCard({
  patientName,
  score,
  message,
  time,
  read,
  onMarkRead,
}: NotificationCardProps) {
  const levelColor =
    score >= 70 ? "bg-danger-500" : score >= 40 ? "bg-warning-500" : "bg-success-500";
  const levelBg =
    score >= 70 ? "bg-danger-50" : score >= 40 ? "bg-warning-50" : "bg-success-50";

  return (
    <div
      className={`group rounded-2xl border bg-white p-4 shadow-card transition-all duration-200 hover:shadow-card-hover ${
        read ? "border-gray-100 opacity-70" : "border-gray-100"
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Dot indicator */}
        <div className="mt-1.5 flex shrink-0 flex-col items-center">
          <span className={`h-2.5 w-2.5 rounded-full ${read ? "bg-gray-300" : levelColor} ${!read ? "animate-pulse-soft" : ""}`} />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="text-[13px] font-semibold text-gray-800">{patientName}</p>
            <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${levelBg} ${score >= 70 ? "text-danger-500" : score >= 40 ? "text-warning-500" : "text-success-500"}`}>
              Score {score}
            </span>
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-gray-500">{message}</p>
          <p className="mt-2 text-[11px] text-gray-400">{time}</p>
        </div>

        {/* Action */}
        {!read && onMarkRead && (
          <button
            onClick={onMarkRead}
            className="shrink-0 rounded-lg border border-gray-200 px-3 py-1.5 text-[11px] font-medium text-gray-500 transition-all hover:border-primary-500 hover:bg-primary-50 hover:text-primary-500"
          >
            Marquer lu
          </button>
        )}
        {read && (
          <svg className="h-4 w-4 shrink-0 text-success-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        )}
      </div>
    </div>
  );
}
