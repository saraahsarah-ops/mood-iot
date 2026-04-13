"use client";

interface NotificationCardProps {
  patientName: string;
  score: number;
  level: number;         // 1=modéré, 2=élevé, 3=critique
  message: string;
  time: string;
  read: boolean;
  onMarkRead?: () => void;
  onDelete?: () => void;
}

export default function NotificationCard({
  patientName,
  score,
  level,
  message,
  time,
  read,
  onMarkRead,
  onDelete,
}: NotificationCardProps) {
  // Couleur basée sur le niveau d'alerte, pas le score
  const levelColor =
    level >= 3 ? "bg-danger-500" : level >= 2 ? "bg-warning-500" : "bg-success-500";
  const levelBg =
    level >= 3 ? "bg-danger-50" : level >= 2 ? "bg-warning-50" : "bg-success-50";
  const levelText =
    level >= 3 ? "text-danger-500" : level >= 2 ? "text-warning-500" : "text-success-500";

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
            <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${levelBg} ${levelText}`}>
              Score {score}
            </span>
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-gray-500">{message}</p>
          <p className="mt-2 text-[11px] text-gray-400">{time}</p>
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-2">
          {!read && onMarkRead && (
            <button
              onClick={onMarkRead}
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-[11px] font-medium text-gray-500 transition-all hover:border-primary-500 hover:bg-primary-50 hover:text-primary-500"
            >
              Marquer lu
            </button>
          )}
          {read && (
            <svg className="h-4 w-4 text-success-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          )}
          {onDelete && (
            <button
              onClick={onDelete}
              className="rounded-lg border border-gray-200 p-1.5 text-gray-400 transition-all hover:border-red-300 hover:bg-red-50 hover:text-red-500"
              title="Supprimer"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
