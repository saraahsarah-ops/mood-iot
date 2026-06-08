import { View, Text, TouchableOpacity, StyleSheet, Alert, Switch } from "react-native";
import { useEffect, useState, useCallback } from "react";
import { router } from "expo-router";
import { useAuthStore } from "@/stores/authStore";
import { useHealthStore } from "@/stores/healthStore";
import {
  getLastSyncAt,
  getPermissionsState,
  requestPermissions,
} from "@/services/healthSync";

function formatRelative(d: Date): string {
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${hours} h`;
  const days = Math.floor(hours / 24);
  return `il y a ${days} j`;
}

export default function SettingsScreen() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.signOut);
  const syncNow = useHealthStore((s) => s.syncHealthData);
  const [autoSync, setAutoSync] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [permGranted, setPermGranted] = useState<boolean>(false);

  const refreshState = useCallback(async () => {
    const d = await getLastSyncAt();
    setLastSync(d ? formatRelative(d) : null);
    const p = await getPermissionsState();
    setPermGranted(p.granted);
  }, []);

  useEffect(() => {
    void refreshState();
  }, [refreshState]);

  async function handleSync() {
    if (!permGranted) {
      Alert.alert(
        "Autorisations requises",
        "Vous devez d'abord autoriser l'accès à Health Connect.",
        [
          { text: "Annuler", style: "cancel" },
          {
            text: "Autoriser",
            onPress: async () => {
              const ok = await requestPermissions();
              setPermGranted(ok);
              if (ok) await handleSync();
            },
          },
        ],
      );
      return;
    }
    setSyncing(true);
    try {
      await syncNow();
      await refreshState();
      Alert.alert("Synchronisation", "Données synchronisées avec succès !");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Échec de la synchronisation.";
      Alert.alert("Erreur", msg);
    } finally {
      setSyncing(false);
    }
  }

  function handleLogout() {
    Alert.alert("Deconnexion", "Voulez-vous vous deconnecter ?", [
      { text: "Annuler", style: "cancel" },
      { text: "Se deconnecter", style: "destructive", onPress: logout },
    ]);
  }

  return (
    <View style={styles.container}>
      {/* Profile */}
      <View style={styles.profileCard}>
        <Text style={styles.avatar}>👤</Text>
        <View>
          <Text style={styles.userName}>
            {user?.first_name} {user?.last_name}
          </Text>
          <Text style={styles.userEmail}>{user?.email || "patient@mood-iot.fr"}</Text>
        </View>
      </View>

      {/* Health Sync */}
      <Text style={styles.sectionTitle}>Données de santé</Text>
      <View style={styles.card}>
        <SettingRow
          emoji={permGranted ? "✅" : "⚠️"}
          label="Health Connect"
          right={
            <Text style={styles.infoText}>
              {permGranted ? "Autorisé" : "Non autorisé"}
            </Text>
          }
        />
        <SettingRow
          emoji="🕒"
          label="Dernière synchronisation"
          right={
            <Text style={styles.infoText}>{lastSync ?? "Jamais"}</Text>
          }
        />
        <SettingRow
          emoji="🔄"
          label="Sync automatique"
          right={
            <Switch
              value={autoSync}
              onValueChange={setAutoSync}
              trackColor={{ true: "#0288d1" }}
            />
          }
        />
        <TouchableOpacity
          style={styles.syncButton}
          onPress={handleSync}
          disabled={syncing}
          accessibilityRole="button"
          accessibilityLabel="Synchroniser les données maintenant"
        >
          <Text style={styles.syncButtonText}>
            {syncing ? "Synchronisation..." : "📤 Synchroniser maintenant"}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Notifications */}
      <Text style={styles.sectionTitle}>Notifications</Text>
      <View style={styles.card}>
        <TouchableOpacity
          style={styles.settingRow}
          onPress={() => router.push("/(tabs)/notifications-settings")}
          accessibilityRole="button"
          accessibilityLabel="Gérer mes notifications"
        >
          <View style={styles.settingLeft}>
            <Text style={{ fontSize: 18 }}>🔔</Text>
            <View>
              <Text style={styles.settingLabel}>Gérer mes notifications</Text>
              <Text style={styles.settingSubLabel}>
                Push, SMS, email & rappels RDV
              </Text>
            </View>
          </View>
          <Text style={styles.chevron}>›</Text>
        </TouchableOpacity>
      </View>

      {/* Info */}
      <Text style={styles.sectionTitle}>Application</Text>
      <View style={styles.card}>
        <SettingRow emoji="📋" label="Version" right={<Text style={styles.infoText}>1.0.0</Text>} />
        <SettingRow
          emoji="🔒"
          label="Donnees chiffrees"
          right={<Text style={styles.infoText}>AES-256</Text>}
        />
      </View>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>🚪 Se deconnecter</Text>
      </TouchableOpacity>
    </View>
  );
}

function SettingRow({
  emoji,
  label,
  right,
}: {
  emoji: string;
  label: string;
  right: React.ReactNode;
}) {
  return (
    <View style={styles.settingRow}>
      <View style={styles.settingLeft}>
        <Text style={{ fontSize: 18 }}>{emoji}</Text>
        <Text style={styles.settingLabel}>{label}</Text>
      </View>
      {right}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f7ff", padding: 20 },
  profileCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  avatar: { fontSize: 40 },
  userName: { fontSize: 18, fontWeight: "700", color: "#333" },
  userEmail: { fontSize: 13, color: "#888", marginTop: 2 },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#777",
    marginBottom: 8,
    marginTop: 4,
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 4,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  settingRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  settingLeft: { flexDirection: "row", alignItems: "center", gap: 10 },
  settingLabel: { fontSize: 15, color: "#444" },
  settingSubLabel: { fontSize: 12, color: "#888", marginTop: 2 },
  chevron: { fontSize: 24, color: "#bbb", fontWeight: "300" },
  infoText: { fontSize: 13, color: "#999" },
  syncButton: {
    backgroundColor: "#e3f2fd",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginHorizontal: 12,
    marginBottom: 12,
  },
  syncButtonText: { color: "#0288d1", fontWeight: "600", fontSize: 14 },
  logoutButton: {
    backgroundColor: "#fff",
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e74c3c",
    marginTop: 8,
  },
  logoutText: { color: "#e74c3c", fontWeight: "600", fontSize: 15 },
});
