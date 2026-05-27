"use client";
import { useState, useEffect } from "react";
import { getPatientHistory, sendDirectMessage } from "@/lib/api";

interface MessagerieProps {
  patientId: string;
}

export default function Messagerie({ patientId }: MessagerieProps) {
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<any[]>([]);
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);

  async function loadMessages() {
    try {
      const data = await getPatientHistory(patientId);
      // Ensure we set an array, and reverse to show oldest first if we want a chat view
      // But let's keep newest at bottom for chat
      setMessages((data.messages || []).sort((a: any, b: any) => new Date(a.sent_at).getTime() - new Date(b.sent_at).getTime()));
    } catch (err) {
      console.error("Erreur chargement messages:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (patientId) {
      setLoading(true);
      loadMessages();
    }
  }, [patientId]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!newMessage.trim()) return;
    setSending(true);
    try {
      await sendDirectMessage(patientId, newMessage);
      setNewMessage("");
      await loadMessages();
    } catch (err) {
      console.error("Erreur envoi message:", err);
    } finally {
      setSending(false);
    }
  }

  if (loading) return <div className="py-10 text-center text-[13px] text-gray-400">Chargement des messages...</div>;

  return (
    <div className="flex flex-col h-[500px] rounded-2xl border border-gray-100 bg-white shadow-card">
      <div className="p-4 border-b border-gray-100">
        <h3 className="text-[15px] font-bold text-gray-800">Messages Directs</h3>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length > 0 ? (
          messages.map((msg, idx) => {
            const isMe = msg.sender_id !== patientId; // Assuming current user is doctor if it's not the patient's ID
            return (
              <div key={idx} className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[70%] rounded-2xl px-4 py-2 ${isMe ? 'bg-primary-500 text-white rounded-br-none' : 'bg-gray-100 text-gray-800 rounded-bl-none'}`}>
                  <p className="text-[13px]">{msg.content}</p>
                  <p className={`text-[10px] mt-1 text-right ${isMe ? 'text-primary-100' : 'text-gray-400'}`}>
                    {new Date(msg.sent_at).toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            );
          })
        ) : (
          <p className="text-center text-[13px] text-gray-400 mt-10">Aucun message pour le moment.</p>
        )}
      </div>

      <div className="p-4 border-t border-gray-100 bg-gray-50/50 rounded-b-2xl">
        <form onSubmit={handleSend} className="flex gap-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Écrivez un message..."
            className="flex-1 rounded-xl border border-gray-200 bg-white px-4 py-2 text-[13px] text-gray-700 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          />
          <button
            type="submit"
            disabled={sending || !newMessage.trim()}
            className="rounded-xl bg-primary-500 px-5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-primary-600 disabled:opacity-50"
          >
            {sending ? "..." : "Envoyer"}
          </button>
        </form>
      </div>
    </div>
  );
}
