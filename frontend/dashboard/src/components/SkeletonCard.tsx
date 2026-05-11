"use client";

export function SkeletonPulse({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-gray-200 ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl bg-white p-5 shadow-card">
      <div className="flex items-center gap-3">
        <SkeletonPulse className="h-10 w-10 rounded-xl" />
        <div className="flex-1 space-y-2">
          <SkeletonPulse className="h-4 w-24" />
          <SkeletonPulse className="h-3 w-16" />
        </div>
      </div>
      <SkeletonPulse className="mt-4 h-8 w-20" />
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="rounded-xl bg-white p-5 shadow-card">
      <SkeletonPulse className="mb-4 h-4 w-32" />
      <SkeletonPulse className="h-48 w-full rounded-xl" />
    </div>
  );
}
