import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAuthStore } from '../store/authStore';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ApiNotification {
  id: string;
  patient_id: string;
  type: string;
  level: 1 | 2 | 3;
  channel: string;
  title: string;
  body: string;
  recipient_user_id: string;
  status: string;
  sent_at: string | null;
  read_at: string | null;
  created_at: string;
}

interface ApiResponse {
  notifications: ApiNotification[];
  total: number;
  unread: number;
}

// ─── Config ───────────────────────────────────────────────────────────────────

const API_BASE = 'https://api.mood-iot.fr/api/v1';

const BADGE_CONFIG: Record<1 | 2 | 3, { label: string; bg: string; color: string; dot: string; border: string }> = {
  1: { label: 'Conseil',        bg: '#E8F3EF', color: '#2D7D6E', dot: '#2D7D6E', border: '#B8DDD4' },
  2: { label: 'Suivi renforcé', bg: '#FBF2E3', color: '#C9852B', dot: '#C9852B', border: '#F0D9B5' },
  3: { label: 'Action requise', bg: '#FBEAE8', color: '#C45850', dot: '#C45850', border: '#F4B8B0' },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  if (d.toDateString() === today.toDateString())     return "Aujourd'hui";
  if (d.toDateString() === yesterday.toDateString()) return 'Hier';
  return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

// Déduplique : garde une seule notif par (type + created_at tronqué à la seconde)
function deduplicate(notifs: ApiNotification[]): ApiNotification[] {
  const seen = new Set<string>();
  return notifs.filter(n => {
    const key = `${n.type}__${n.created_at.slice(0, 19)}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ─── NotifCard ────────────────────────────────────────────────────────────────

function NotifCard({
  notif,
  onChat,
}: {
  notif: ApiNotification;
  onChat: () => void;
}) {
  const badge  = BADGE_CONFIG[notif.level] ?? BADGE_CONFIG[1];
  const isRead = !!notif.read_at;
  const showCta = notif.level === 1 || notif.level === 2;

  return (
    <View style={[s.card, { borderColor: badge.border }, !isRead && s.cardUnread]}>
      <View style={s.cardTop}>
        <View style={[s.badge, { backgroundColor: badge.bg }]}>
          <View style={[s.dot, { backgroundColor: badge.dot }]} />
          <Text style={[s.badgeText, { color: badge.color }]}>{badge.label}</Text>
        </View>
        <View style={s.cardTopRight}>
          {!isRead && <View style={s.unreadDot} />}
          <Text style={s.time}>{fmtTime(notif.created_at)}</Text>
        </View>
      </View>

      <Text style={s.msgTitle}>{notif.title}</Text>
      <Text style={s.msg}>{notif.body}</Text>

      {showCta && (
        <TouchableOpacity style={[s.btnChat, { borderColor: badge.color }]} onPress={onChat}>
          <Text style={[s.btnChatText, { color: badge.color }]}>🩺 Contacter mon médecin</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

// ─── Screen ───────────────────────────────────────────────────────────────────

export default function Recommandations() {
  const navigation = useNavigation<any>();
  const { user, getValidAccessToken } = useAuthStore();

  const [notifications, setNotifications] = useState<ApiNotification[]>([]);
  const [loading, setLoading]             = useState(true);
  const [refreshing, setRefreshing]       = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [unread, setUnread]               = useState(0);

  const fetchNotifications = useCallback(async (isRefresh = false) => {
    if (!user?.patient_id) return;
    isRefresh ? setRefreshing(true) : setLoading(true);
    setError(null);

    try {
      const token = await getValidAccessToken();
      if (!token) throw new Error('Session expirée');

      const res = await fetch(`${API_BASE}/notifications/${user.patient_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Erreur serveur (${res.status})`);

      const data: ApiResponse = await res.json();
      const deduped = deduplicate(
        [...data.notifications].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )
      );
      setNotifications(deduped);
      setUnread(data.unread);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Impossible de charger les notifications');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.patient_id]);

  useEffect(() => { fetchNotifications(); }, [fetchNotifications]);

  // Grouper par date
  const grouped = notifications.reduce<Record<string, ApiNotification[]>>((acc, n) => {
    const key = fmtDate(n.created_at);
    if (!acc[key]) acc[key] = [];
    acc[key].push(n);
    return acc;
  }, {});

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.greeting}>Bonjour {user?.first_name} 👋</Text>
        <View style={s.headerRow}>
          <Text style={s.title}>Mes recommandations</Text>
          {unread > 0 && (
            <View style={s.unreadBadge}>
              <Text style={s.unreadBadgeText}>{unread}</Text>
            </View>
          )}
        </View>
      </View>

      {/* Loader */}
      {loading && (
        <View style={s.loaderCenter}>
          <ActivityIndicator color="#2D7D6E" size="large" />
          <Text style={s.loaderText}>Chargement…</Text>
        </View>
      )}

      {/* Erreur */}
      {!loading && error && (
        <View style={s.errorWrap}>
          <Text style={s.errorText}>⚠️ {error}</Text>
          <TouchableOpacity style={s.retryBtn} onPress={() => fetchNotifications()}>
            <Text style={s.retryText}>Réessayer</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Feed */}
      {!loading && !error && (
        <ScrollView
          style={s.feed}
          contentContainerStyle={s.feedContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchNotifications(true)}
              tintColor="#2D7D6E"
              colors={['#2D7D6E']}
            />
          }
        >
          {notifications.length === 0 ? (
            <View style={s.emptyWrap}>
              <Text style={s.emptyIcon}>🌿</Text>
              <Text style={s.emptyTitle}>Tout va bien !</Text>
              <Text style={s.emptyText}>Aucune recommandation pour le moment.</Text>
            </View>
          ) : (
            Object.entries(grouped).map(([date, items]) => (
              <View key={date}>
                <Text style={s.dateSep}>{date}</Text>
                {items.map(notif => (
                  <NotifCard
                    key={notif.id}
                    notif={notif}
                    onChat={() => navigation.navigate('Tchat')}
                  />
                ))}
              </View>
            ))
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4FAF8' },

  header: {
    backgroundColor: '#fff',
    paddingHorizontal: 20, paddingTop: 16, paddingBottom: 14,
    borderBottomWidth: 1, borderBottomColor: '#DCEAE5',
  },
  headerRow:  { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 },
  greeting:   { fontSize: 12, color: '#5B7672', fontWeight: '500' },
  title:      { fontSize: 21, fontWeight: '700', color: '#1B3A3A' },
  unreadBadge: {
    backgroundColor: '#C45850', borderRadius: 10,
    paddingHorizontal: 7, paddingVertical: 2,
  },
  unreadBadgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },

  loaderCenter: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loaderText:   { fontSize: 13, color: '#2D7D6E', fontWeight: '600' },

  errorWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 12 },
  errorText: { fontSize: 13, color: '#C45850', textAlign: 'center', fontWeight: '600' },
  retryBtn:  { backgroundColor: '#2D7D6E', borderRadius: 12, paddingHorizontal: 20, paddingVertical: 10 },
  retryText: { color: '#fff', fontWeight: '700', fontSize: 13 },

  feed:        { flex: 1 },
  feedContent: { paddingHorizontal: 16, paddingBottom: 32 },

  dateSep: {
    textAlign: 'center', fontSize: 11, color: '#5B7672',
    fontWeight: '600', marginVertical: 14,
    textTransform: 'uppercase', letterSpacing: 0.5,
  },

  card: {
    backgroundColor: '#fff', borderRadius: 18,
    padding: 14, marginBottom: 12,
    borderWidth: 1,
  },
  cardUnread: { backgroundColor: '#FAFFFE' },
  cardTop: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: 8,
  },
  cardTopRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },

  badge: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20,
  },
  dot:       { width: 7, height: 7, borderRadius: 4 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  unreadDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#C45850' },
  time:      { fontSize: 11, color: '#5B7672' },

  msgTitle: { fontSize: 13, fontWeight: '700', color: '#1B3A3A', marginBottom: 4 },
  msg:      { fontSize: 13, lineHeight: 19, color: '#3A5A58' },

  btnChat: {
    marginTop: 12, borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 9,
    borderWidth: 1.5, alignSelf: 'flex-start',
  },
  btnChatText: { fontSize: 12, fontWeight: '700' },

  emptyWrap:  { alignItems: 'center', justifyContent: 'center', paddingTop: 80, gap: 8 },
  emptyIcon:  { fontSize: 48 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: '#1B3A3A' },
  emptyText:  { fontSize: 13, color: '#5B7672', textAlign: 'center' },
});