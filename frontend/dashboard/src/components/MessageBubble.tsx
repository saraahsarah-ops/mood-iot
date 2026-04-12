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
      <div
        className={`max-w-[70%] rounded-2xl px-4 py-2 ${
          isDoctor
            ? "rounded-br-none bg-primary text-white"
            : "rounded-bl-none bg-gray-100 text-gray-800"
        }`}
      >
        <p className="text-sm">{texte}</p>
        <p
          className={`mt-1 text-xs ${
            isDoctor ? "text-blue-200" : "text-gray-400"
          }`}
        >
          {heure}
        </p>
      </div>
    </div>
  );
}
