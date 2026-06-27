import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TextInput,
  TouchableOpacity, KeyboardAvoidingView, Platform,
  ActivityIndicator, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/authStore';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ApiMessage {
  id: string;
  sender_id: string;
  recipient_id: string;
  content: string;
  sent_at: string;
  read_at: string | null;
}

interface Teleconsult {
  id: string;
  patient_id: string;
  psychiatre_id: string;
  status: string;
  scheduled_at: string;
  duration_minutes: number;
  jitsi_url: string;
  jitsi_room_name: string;
}

interface HistoryResponse {
  teleconsults: Teleconsult[];
  notes: unknown[];
  messages: ApiMessage[];
}

interface Message {
  id: string;
  from: 'doc' | 'me' | 'system';
  text: string;
  time: string;
  isoTime: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const API_BASE = 'https://api.mood-iot.fr/api/v1';

function fmtTime(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const isToday =
    d.getDate() === today.getDate() &&
    d.getMonth() === today.getMonth() &&
    d.getFullYear() === today.getFullYear();

  if (isToday) {
    return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }) +
    ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

function fmtScheduled(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long',
    hour: '2-digit', minute: '2-digit',
  });
}

const nowTime = () =>
  new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

const SYSTEM_MSG: Message = {
  id: 'system-0',
  from: 'system',
  text: 'Conversation sécurisée et confidentielle',
  time: '',
  isoTime: '',
};

// ─── Teleconsult banner ───────────────────────────────────────────────────────

function TeleconsultBanner({ consult }: { consult: Teleconsult }) {
  const isNow = consult.status === 'in_progress';
  const label = isNow
    ? 'Consultation en cours'
    : `Prochaine consultation — ${fmtScheduled(consult.scheduled_at)}`;

  return (
    <TouchableOpacity
      style={[tc.box, isNow && tc.boxActive]}
      onPress={() => Linking.openURL(consult.jitsi_url).catch(() => {})}
      activeOpacity={0.8}
    >
      <Text style={tc.icon}>{isNow ? '🎥' : '📅'}</Text>
      <View style={{ flex: 1 }}>
        <Text style={[tc.title, isNow && tc.titleActive]}>{label}</Text>
        <Text style={tc.sub}>
          {consult.duration_minutes} min · Appuyez pour rejoindre
        </Text>
      </View>
      <Text style={[tc.arrow, isNow && tc.arrowActive]}>›</Text>
    </TouchableOpacity>
  );
}

const tc = StyleSheet.create({
  box: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    margin: 12, marginBottom: 4,
    backgroundColor: '#E8F3EF', borderRadius: 14,
    padding: 14, borderWidth: 1, borderColor: '#B8DDD4',
  },
  boxActive: { backgroundColor: '#2D7D6E', borderColor: '#2D7D6E' },
  icon:  { fontSize: 22 },
  title: { fontSize: 13, fontWeight: '700', color: '#1B3A3A' },
  titleActive: { color: '#fff' },
  sub:   { fontSize: 11, color: '#5B7672', marginTop: 2 },
  arrow: { fontSize: 22, color: '#2D7D6E', fontWeight: '700' },
  arrowActive: { color: '#fff' },
});

// ─── DateSeparator ────────────────────────────────────────────────────────────

function DateSeparator({ date }: { date: string }) {
  return (
    <View style={ds.wrap}>
      <View style={ds.line} />
      <Text style={ds.text}>{date}</Text>
      <View style={ds.line} />
    </View>
  );
}

const ds = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', marginVertical: 12, gap: 8 },
  line: { flex: 1, height: 1, backgroundColor: '#DCEAE5' },
  text: { fontSize: 11, color: '#5B7672', fontWeight: '600' },
});

// ─── Component ────────────────────────────────────────────────────────────────

export default function Tchat() {
  const { user, getValidAccessToken } = useAuthStore();

  const [messages, setMessages]         = useState<Message[]>([SYSTEM_MSG]);
  const [teleconsult, setTeleconsult]   = useState<Teleconsult | null>(null);
  const [input, setInput]               = useState('');
  const [loading, setLoading]           = useState(true);
  const [sending, setSending]           = useState(false);
  const [error, setError]               = useState<string | null>(null);
  const listRef = useRef<FlatList>(null);

  // ── Fetch history ────────────────────────────────────────────────────────

  const fetchHistory = useCallback(async () => {
    if (!user?.id || !user?.patient_id) return;
    setError(null);

    const token = await getValidAccessToken();
    if (!token) {
      setError('Session expirée. Reconnectez-vous.');
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/teleconsult/history/${user.patient_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Erreur serveur (${res.status})`);

      const data: HistoryResponse = await res.json();

      // Messages : triés par date croissante (plus ancien → plus récent)
      const sorted = [...data.messages].sort(
        (a, b) => new Date(a.sent_at).getTime() - new Date(b.sent_at).getTime()
      );

      const mapped: Message[] = sorted.map((m) => ({
        id: m.id,
        from: m.sender_id === user.id ? 'me' : 'doc',
        text: m.content,
        time: fmtTime(m.sent_at),
        isoTime: m.sent_at,
      }));

      setMessages([SYSTEM_MSG, ...mapped]);

      // Téléconsultation planifiée ou en cours
      const upcoming = data.teleconsults.find(
        t => t.status === 'scheduled' || t.status === 'in_progress'
      );
      setTeleconsult(upcoming ?? null);

    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Impossible de charger la conversation.');
    } finally {
      setLoading(false);
    }
  }, [user?.id, getValidAccessToken]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // ── Send message ─────────────────────────────────────────────────────────

  const send = async () => {
    const text = input.trim();
    if (!text || sending || !user?.id || !user?.patient_id) return;

    const optimistic: Message = {
      id: `local-${Date.now()}`,
      from: 'me',
      text,
      time: nowTime(),
      isoTime: new Date().toISOString(),
    };

    setMessages(prev => [...prev, optimistic]);
    setInput('');
    setSending(true);
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 80);

    const token = await getValidAccessToken();
    if (!token) {
      markFailed(optimistic.id);
      setSending(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/teleconsult/messages/${user.patient_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ApiMessage = await res.json();

      setMessages(prev =>
        prev.map(m =>
          m.id === optimistic.id
            ? { id: data.id, from: 'me', text: data.content, time: fmtTime(data.sent_at), isoTime: data.sent_at }
            : m
        )
      );
    } catch {
      markFailed(optimistic.id);
    } finally {
      setSending(false);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 80);
    }
  };

  const markFailed = (id: string) => {
    setMessages(prev =>
      prev.map(m => m.id === id ? { ...m, text: `${m.text} ⚠️` } : m)
    );
  };

  // ── FlatList item + date separators ──────────────────────────────────────

  /** Insère des séparateurs de date entre messages de jours différents */
  const itemsWithSeparators = React.useMemo(() => {
    type ListItem =
      | { type: 'msg'; data: Message }
      | { type: 'sep'; key: string; label: string };

    const result: ListItem[] = [];
    let lastDay = '';

    for (const msg of messages) {
      if (msg.from === 'system') {
        result.push({ type: 'msg', data: msg });
        continue;
      }
      const day = msg.isoTime
        ? new Date(msg.isoTime).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
        : '';
      if (day && day !== lastDay) {
        lastDay = day;
        result.push({ type: 'sep', key: `sep-${day}`, label: day });
      }
      result.push({ type: 'msg', data: msg });
    }
    return result;
  }, [messages]);

  const renderItem = ({ item }: { item: typeof itemsWithSeparators[number] }) => {
    if (item.type === 'sep') {
      return <DateSeparator date={item.label} />;
    }
    const msg = item.data;
    if (msg.from === 'system') {
      return (
        <View style={s.systemWrap}>
          <Text style={s.systemText}>{msg.text}</Text>
        </View>
      );
    }
    const isMe = msg.from === 'me';
    return (
      <View style={[s.bubbleWrap, isMe ? s.bubbleWrapMe : s.bubbleWrapDoc]}>
        <View style={[s.bubble, isMe ? s.bubbleMe : s.bubbleDoc]}>
          <Text style={[s.bubbleText, isMe ? s.bubbleTextMe : s.bubbleTextDoc]}>
            {msg.text}
          </Text>
        </View>
        {msg.time ? (
          <Text style={[s.bubbleTime, isMe ? s.bubbleTimeMe : null]}>{msg.time}</Text>
        ) : null}
      </View>
    );
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <View style={s.avatar}>
          <Text style={{ fontSize: 20 }}>🩺</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.docName}>Mon médecin</Text>
          <Text style={s.docStatus}>● Suivi psychiatrique</Text>
        </View>
        <TouchableOpacity style={s.refreshBtn} onPress={fetchHistory}>
          <Text style={s.refreshIcon}>↻</Text>
        </TouchableOpacity>
      </View>

      {/* Bannière téléconsultation */}
      {teleconsult && <TeleconsultBanner consult={teleconsult} />}

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        {loading ? (
          <View style={s.loadingWrap}>
            <ActivityIndicator size="large" color="#2D7D6E" />
            <Text style={s.loadingText}>Chargement de la conversation…</Text>
          </View>
        ) : error ? (
          <View style={s.errorWrap}>
            <Text style={s.errorText}>⚠️ {error}</Text>
            <TouchableOpacity style={s.retryBtn} onPress={fetchHistory}>
              <Text style={s.retryText}>Réessayer</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={itemsWithSeparators}
            keyExtractor={item => item.type === 'sep' ? item.key : item.data.id}
            renderItem={renderItem}
            contentContainerStyle={s.list}
            onContentSizeChange={() =>
              listRef.current?.scrollToEnd({ animated: false })
            }
          />
        )}

        {/* Barre de saisie */}
        <View style={s.inputRow}>
          <TextInput
            style={s.input}
            placeholder="Écrire un message…"
            placeholderTextColor="#5B7672"
            value={input}
            onChangeText={setInput}
            multiline
            maxLength={500}
            editable={!sending && !loading}
            onSubmitEditing={send}
            blurOnSubmit={false}
          />
          <TouchableOpacity
            style={[s.sendBtn, (!input.trim() || sending) && s.sendBtnDisabled]}
            onPress={send}
            disabled={!input.trim() || sending}
          >
            {sending ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={s.sendIcon}>➤</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4FAF8' },

  header: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#fff', padding: 16,
    borderBottomWidth: 1, borderBottomColor: '#DCEAE5',
  },
  avatar: {
    width: 42, height: 42, borderRadius: 21,
    backgroundColor: '#E8F3EF', alignItems: 'center', justifyContent: 'center',
  },
  docName:   { fontSize: 16, fontWeight: '700', color: '#1B3A3A' },
  docStatus: { fontSize: 12, color: '#2D7D6E', fontWeight: '500', marginTop: 2 },
  refreshBtn: { padding: 8 },
  refreshIcon: { fontSize: 20, color: '#2D7D6E', fontWeight: '700' },

  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadingText: { fontSize: 13, color: '#5B7672' },

  errorWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 12 },
  errorText: { fontSize: 13, color: '#C45850', textAlign: 'center', fontWeight: '600' },
  retryBtn:  { backgroundColor: '#2D7D6E', borderRadius: 12, paddingHorizontal: 20, paddingVertical: 10 },
  retryText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  list: { padding: 16, paddingBottom: 8 },

  systemWrap: { alignItems: 'center', marginVertical: 8 },
  systemText: {
    fontSize: 11, color: '#5B7672', backgroundColor: '#E8F3EF',
    paddingHorizontal: 12, paddingVertical: 5, borderRadius: 12,
  },

  bubbleWrap:    { maxWidth: '80%', marginBottom: 6 },
  bubbleWrapMe:  { alignSelf: 'flex-end' },
  bubbleWrapDoc: { alignSelf: 'flex-start' },

  bubble:    { borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10 },
  bubbleMe:  { backgroundColor: '#2D7D6E', borderBottomRightRadius: 4 },
  bubbleDoc: {
    backgroundColor: '#fff', borderBottomLeftRadius: 4,
    borderWidth: 1, borderColor: '#DCEAE5',
  },

  bubbleText:    { fontSize: 14, lineHeight: 20 },
  bubbleTextMe:  { color: '#fff' },
  bubbleTextDoc: { color: '#1B3A3A' },

  bubbleTime:   { fontSize: 10, color: '#5B7672', marginTop: 3, marginHorizontal: 4 },
  bubbleTimeMe: { textAlign: 'right' },

  inputRow: {
    flexDirection: 'row', alignItems: 'flex-end', gap: 8,
    backgroundColor: '#fff',
    borderTopWidth: 1, borderTopColor: '#DCEAE5',
    padding: 12,
  },
  input: {
    flex: 1, backgroundColor: '#F4FAF8', borderRadius: 20,
    paddingHorizontal: 16, paddingVertical: 10,
    fontSize: 14, color: '#1B3A3A',
    maxHeight: 100, borderWidth: 1, borderColor: '#DCEAE5',
  },
  sendBtn: {
    width: 42, height: 42, borderRadius: 21,
    backgroundColor: '#2D7D6E', alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.45 },
  sendIcon: { color: '#fff', fontSize: 16 },
});