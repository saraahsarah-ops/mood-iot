"use client";

interface MessageBubbleProps {
  role: "medecin" | "patiente";
  texte: string;
  heure: string;
}

export default function MessageBubble({ role, texte, heure }: MessageBubbleProps) {
  const isDoctor = role === "medecin";

  return (
    <div className={`flex ${isDoctor ? "justify-end" : "justify-start"} mb-3`}>
      {/* Patient avatar */}
      {!isDoctor && (
        <div className="mr-2 mt-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[11px] font-bold text-gray-500">
          P
        </div>
      )}
      <div
        className={`max-w-[70%] px-4 py-2.5 ${
          isDoctor
            ? "rounded-2xl rounded-br-md bg-primary-500 text-white"
            : "rounded-2xl rounded-bl-md bg-gray-100 text-gray-800"
        }`}
      >
        <p className="text-[13px] leading-relaxed">{texte}</p>
        <p
          className={`mt-1 text-[10px] ${
            isDoctor ? "text-primary-200" : "text-gray-400"
          }`}
        >
          {heure}
        </p>
      </div>
      {/* Doctor avatar */}
      {isDoctor && (
        <div className="ml-2 mt-auto flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-500/10 text-[11px] font-bold text-primary-500">
          Dr
        </div>
      )}
    </div>
  );
}
