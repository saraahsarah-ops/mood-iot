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
  return (
    <div
      className={`rounded-xl border-l-4 p-4 shadow-sm ${
        read ? "border-gray-300 bg-white" : "border-danger bg-yellow-50"
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="font-semibold text-gray-800">
            {read ? "✓" : "🔔"} {patientName} — Score {score}/100
          </p>
          <p className="mt-1 text-sm text-gray-600">{message}</p>
          <p className="mt-1 text-xs text-gray-400">{time}</p>
        </div>
        {!read && onMarkRead && (
          <button
            onClick={onMarkRead}
            className="ml-4 shrink-0 rounded-lg bg-primary px-3 py-1 text-xs text-white hover:bg-primary-dark"
          >
            Marquer comme lu
          </button>
        )}
      </div>
    </div>
  );
}
