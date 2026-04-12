"use client";
import { useState } from "react";
import MessageBubble from "@/components/MessageBubble";
import { useMessageStore } from "@/lib/store";
import { getRiskEmoji } from "@/lib/types";

const PATIENTS = [
  { id: "1", name: "Sophie L.", score: 82 },
  { id: "2", name: "Marie D.", score: 55 },
  { id: "3", name: "Lea R.", score: 35 },
  { id: "4", name: "Anna K.", score: 68 },
];

const QUICK_MSGS = [
  { emoji: "📞", label: "Appel prevu", text: "Je vous appelle dans la journee pour faire le point." },
  { emoji: "💊", label: "Rappel medicament", text: "Pensez a prendre votre traitement ce soir." },
  { emoji: "🌟", label: "Encouragement", text: "Vous faites du bon travail, continuez ainsi !" },
];

export default function MessageriePage() {
  const [selected, setSelected] = useState(PATIENTS[0]);
  const [input, setInput] = useState("");
  const { conversations, addMessage } = useMessageStore();

  const messages = conversations[selected.id] || [];

  function send(text: string) {
    if (!text.trim()) return;
    const now = new Date();
    addMessage(selected.id, {
      id: crypto.randomUUID(),
      role: "medecin",
      texte: text,
      heure: `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`,
    });
    setInput("");
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800">💬 Messagerie</h1>

      {/* Selection patient */}
      <div className="mt-4 flex items-center gap-3">
        <select
          value={selected.id}
          onChange={(e) => setSelected(PATIENTS.find((p) => p.id === e.target.value)!)}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm"
        >
          {PATIENTS.map((p) => (
            <option key={p.id} value={p.id}>
              {getRiskEmoji(p.score)} {p.name} — {p.score}/100
            </option>
          ))}
        </select>
      </div>

      {/* Zone de messages */}
      <div className="mt-4 max-h-[400px] min-h-[200px] overflow-y-auto rounded-xl bg-white p-4 shadow-sm">
        {messages.length === 0 ? (
          <p className="text-center text-sm text-gray-400">
            Aucun message. Commencez la conversation.
          </p>
        ) : (
          messages.map((m) => (
            <MessageBubble key={m.id} role={m.role} texte={m.texte} heure={m.heure} />
          ))
        )}
      </div>

      {/* Messages rapides */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        {QUICK_MSGS.map((q) => (
          <button
            key={q.label}
            onClick={() => send(q.text)}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600 hover:bg-gray-50"
          >
            {q.emoji} {q.label}
          </button>
        ))}
      </div>

      {/* Saisie */}
      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder="Votre message..."
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm"
        />
        <button
          onClick={() => send(input)}
          className="rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark"
        >
          📤 Envoyer
        </button>
      </div>
    </div>
  );
}
