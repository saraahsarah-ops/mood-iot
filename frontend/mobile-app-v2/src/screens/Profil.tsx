import React from 'react';
import {
  View, Text, StyleSheet, ScrollView,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/authStore';

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

function formatDate(iso?: string): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'long', year: 'numeric',
  });
}

function roleLabel(role?: string): string {
  if (role === 'patient')    return 'Patient';
  if (role === 'psychiatre') return 'Psychiatre';
  if (role === 'admin')      return 'Administrateur';
  return role ?? '—';
}

function statusLabel(status?: string): { label: string; color: string; bg: string } {
  if (status === 'approved') return { label: 'Compte validé', color: '#1B5E4A', bg: '#EBF8F4' };
  if (status === 'pending')  return { label: 'En attente',    color: '#7A4F10', bg: '#FBF2E3' };
  if (status === 'rejected') return { label: 'Refusé',        color: '#B5362A', bg: '#FBEAE8' };
  return { label: status ?? '—', color: '#5B7672', bg: '#F4FAF8' };
}

function initials(first?: string, last?: string): string {
  return ((first?.[0] ?? '') + (last?.[0] ?? '')).toUpperCase() || '??';
}

// ────────────────────────────────────────────────────────────────────────────
// Sub-components
// ────────────────────────────────────────────────────────────────────────────

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <View style={s.row}>
      <Text style={s.rowLabel}>{label}</Text>
      <Text style={s.rowValue}>{value || '—'}</Text>
    </View>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={s.card}>
      <Text style={s.cardTitle}>{title}</Text>
      {children}
    </View>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Screen
// ────────────────────────────────────────────────────────────────────────────

export default function Profil() {
  const { user, signOut, refreshUser } = useAuthStore();
  const [refreshing, setRefreshing] = React.useState(false);
  const [signingOut, setSigningOut] = React.useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshUser();
    setRefreshing(false);
  };

  const handleSignOut = async () => {
    setSigningOut(true);
    await signOut();
  };

  const status = statusLabel(user?.registration_status);

  return (
    <SafeAreaView style={s.root} edges={['top', 'bottom']}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header avatar */}
        <View style={s.header}>
          <View style={s.avatar}>
            <Text style={s.avatarText}>
              {initials(user?.first_name, user?.last_name)}
            </Text>
          </View>
          <Text style={s.fullName}>
            {user ? `${user.first_name} ${user.last_name}` : '—'}
          </Text>
          <Text style={s.email}>{user?.email ?? '—'}</Text>

          <View style={[s.statusBadge, { backgroundColor: status.bg }]}>
            <View style={[s.statusDot, { backgroundColor: status.color }]} />
            <Text style={[s.statusText, { color: status.color }]}>{status.label}</Text>
          </View>
        </View>

        {/* Infos personnelles */}
        <SectionCard title="Informations personnelles">
          <InfoRow label="Prénom"       value={user?.first_name} />
          <View style={s.divider} />
          <InfoRow label="Nom"          value={user?.last_name} />
          <View style={s.divider} />
          <InfoRow label="E-mail"       value={user?.email} />
          <View style={s.divider} />
          <InfoRow label="Téléphone"    value={user?.phone} />
          <View style={s.divider} />
          <InfoRow label="Date de naissance" value={formatDate(user?.date_of_birth)} />
          <View style={s.divider} />
          <InfoRow label="Genre"        value={user?.gender} />
        </SectionCard>

        {/* Suivi médical */}
        <SectionCard title="Suivi médical">
          <InfoRow label="Rôle"         value={roleLabel(user?.role)} />
          <View style={s.divider} />
          <InfoRow label="Psychiatre référent" value={user?.psychiatre_id ?? 'Non renseigné'} />
        </SectionCard>

        {/* Compte */}
        <SectionCard title="Compte">
          <InfoRow label="Statut"       value={status.label} />
          <View style={s.divider} />
          <InfoRow label="Membre depuis" value={formatDate(user?.created_at)} />
        </SectionCard>

        {/* Bouton actualiser */}
        <TouchableOpacity
          style={s.refreshBtn}
          onPress={handleRefresh}
          disabled={refreshing}
          activeOpacity={0.75}
        >
          {refreshing
            ? <ActivityIndicator color="#2D7D6E" size="small" />
            : <Text style={s.refreshText}>🔄  Actualiser le profil</Text>
          }
        </TouchableOpacity>

        {/* Déconnexion */}
        <TouchableOpacity
          style={[s.signOutBtn, signingOut && s.btnDisabled]}
          onPress={handleSignOut}
          disabled={signingOut}
          activeOpacity={0.75}
        >
          {signingOut
            ? <ActivityIndicator color="#C45850" size="small" />
            : <Text style={s.signOutText}>🚪  Se déconnecter</Text>
          }
        </TouchableOpacity>

        <Text style={s.legal}>
          Vos données sont chiffrées et confidentielles.{'\n'}
          Seul votre médecin y a accès.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Styles
// ────────────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  root:    { flex: 1, backgroundColor: '#F4FAF8' },
  scroll:  { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },

  // Header
  header: { alignItems: 'center', marginBottom: 24, paddingTop: 8 },
  avatar: {
    width: 80, height: 80, borderRadius: 40,
    backgroundColor: '#E1F5EE',
    borderWidth: 2.5, borderColor: '#2D7D6E',
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 12,
  },
  avatarText: { fontSize: 28, fontWeight: '700', color: '#2D7D6E' },
  fullName:   { fontSize: 22, fontWeight: '700', color: '#1B3A3A', marginBottom: 4 },
  email:      { fontSize: 13, color: '#5B7672', marginBottom: 12 },

  statusBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 5, paddingHorizontal: 12,
    borderRadius: 20,
  },
  statusDot:  { width: 7, height: 7, borderRadius: 4 },
  statusText: { fontSize: 12, fontWeight: '700' },

  // Cards
  card: {
    backgroundColor: '#fff',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#DCEAE5',
    padding: 20,
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 11, fontWeight: '700', color: '#5B7672',
    textTransform: 'uppercase', letterSpacing: 0.8,
    marginBottom: 14,
  },

  // Rows
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  rowLabel: { fontSize: 13, color: '#5B7672', fontWeight: '500', flex: 1 },
  rowValue: { fontSize: 13, color: '#1B3A3A', fontWeight: '600', flex: 2, textAlign: 'right' },
  divider:  { height: 1, backgroundColor: '#F0F5F3' },

  // Buttons
  refreshBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 14,
    paddingVertical: 14,
    borderWidth: 1.5,
    borderColor: '#2D7D6E',
    marginBottom: 12,
    backgroundColor: '#fff',
    minHeight: 50,
  },
  refreshText: { fontSize: 14, color: '#2D7D6E', fontWeight: '700' },

  signOutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 14,
    paddingVertical: 14,
    backgroundColor: '#FBEAE8',
    borderWidth: 1.5,
    borderColor: '#F4B8B0',
    marginBottom: 24,
    minHeight: 50,
  },
  signOutText: { fontSize: 14, color: '#C45850', fontWeight: '700' },
  btnDisabled: { opacity: 0.6 },

  legal: {
    textAlign: 'center', fontSize: 11,
    color: '#5B7672', lineHeight: 17,
  },
});