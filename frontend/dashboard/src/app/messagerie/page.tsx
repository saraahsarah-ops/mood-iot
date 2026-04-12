"use client";
import { useState, useRef, useEffect } from "react";
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
  { icon: "📞", label: "Appel prevu", text: "Je vous appelle dans la journee pour faire le point." },
  { icon: "💊", label: "Rappel medicament", text: "Pensez a prendre votre traitement ce soir." },
  { icon: "🌟", label: "Encouragement", text: "Vous faites du bon travail, continuez ainsi !" },
];

export default function MessageriePage() {
  const [selected, setSelected] = useState(PATIENTS[0]);
  const [input, setInput] = useState("");
  const { conversations, addMessage } = useMessageStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const messages = conversations[selected.id] || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

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

  const scoreColor =
    selected.score >= 70 ? "text-danger-500" : selected.score >= 40 ? "text-warning-500" : "text-success-500";

  return (
    <div className="page-enter flex h-[calc(100vh-3rem)] flex-col">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
          Messagerie
        </h1>
        <p className="mt-1 text-[13px] text-gray-400">
          Communication securisee avec les patientes
        </p>
      </div>

      {/* Patient bar */}
      <div className="mt-4 flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white pl-3 pr-1 shadow-card">
          <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
          <select
            value={selected.id}
            onChange={(e) => setSelected(PATIENTS.find((p) => p.id === e.target.value)!)}
            className="border-none bg-transparent py-2.5 pr-8 text-[13px] font-medium text-gray-700 focus:outline-none"
          >
            {PATIENTS.map((p) => (
              <option key={p.id} value={p.id}>
                {getRiskEmoji(p.score)} {p.name} — {p.score}/100
              </option>
            ))}
          </select>
        </div>
        <span className={`text-[13px] font-bold ${scoreColor}`}>
          {getRiskEmoji(selected.score)} Score: {selected.score}/100
        </span>
      </div>

      {/* Chat area */}
      <div className="mt-4 flex min-h-0 flex-1 flex-col rounded-2xl border border-gray-100 bg-white shadow-card">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-50">
                <svg className="h-7 w-7 text-gray-300" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                </svg>
              </div>
              <p className="mt-3 text-[13px] text-gray-400">
                Aucun message. Commencez la conversation.
              </p>
            </div>
          ) : (
            <>
              {messages.map((m) => (
                <MessageBubble key={m.id} role={m.role} texte={m.texte} heure={m.heure} />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Quick replies */}
        <div className="border-t border-gray-100 px-4 pt-3">
          <div className="flex gap-2">
            {QUICK_MSGS.map((q) => (
              <button
                key={q.label}
                onClick={() => send(q.text)}
                className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-[11px] font-medium text-gray-500 transition-all hover:border-primary-300 hover:bg-primary-50 hover:text-primary-500"
              >
                {q.icon} {q.label}
              </button>
            ))}
          </div>
        </div>

        {/* Input */}
        <div className="flex items-center gap-2 border-t border-gray-100 p-4">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder="Ecrivez votre message..."
            className="flex-1 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 transition focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-500 text-white shadow-sm transition hover:bg-primary-600 active:scale-95 disabled:opacity-40"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
