/**
 * Écran "Réglages → Notifications".
 *
 * Permet au patient de gérer ses canaux (push / SMS / email), les horaires
 * de rappel RDV (J-1 / H-1 / H0), et son numéro de téléphone pour les SMS.
 *
 * Sous-écran du tab Réglages — accessible via `router.push("/(tabs)/notifications-settings")`.
 */

import { useEffect, useState, useCallback } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { Stack, router } from "expo-router";
import {
  fetchNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
} from "@/services/api";
import { palette, light, space, radius, font } from "@/theme/tokens";

export default function NotificationsSettingsScreen() {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [phone, setPhone] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await fetchNotificationPreferences();
      setPrefs(p);
      setPhone(p.phone_e164 ?? "");
    } catch {
      Alert.alert("Erreur", "Impossible de charger vos préférences.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const update = async (patch: Partial<NotificationPreferences>) => {
    if (!prefs) return;
    setSaving(true);
    // Mise à jour optimiste pour un feedback immédiat des switches
    setPrefs({ ...prefs, ...patch });
    try {
      const next = await updateNotificationPreferences(patch);
      setPrefs(next);
    } catch {
      // Rollback en cas d'erreur
      await load();
      Alert.alert("Erreur", "Modification non enregistrée. Réessayez.");
    } finally {
      setSaving(false);
    }
  };

  const onSavePhone = async () => {
    const trimmed = phone.trim();
    // Validation E.164 minimal : commence par + et 9-15 chiffres
    if (trimmed && !/^\+\d{9,15}$/.test(trimmed)) {
      Alert.alert(
        "Format invalide",
        "Votre numéro doit être au format international, ex. +33612345678.",
      );
      return;
    }
    await update({ phone_e164: trimmed || null });
  };

  if (loading || !prefs) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator color={palette.primary500} />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.kav}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Stack.Screen
        options={{
          title: "Notifications",
          headerBackTitle: "Retour",
        }}
      />
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Canaux */}
        <Section title="Canaux" subtitle="Choisissez par où vous souhaitez être contacté(e).">
          <ToggleRow
            icon="🔔"
            label="Notifications push"
            description="Recevez les alertes directement sur votre téléphone."
            value={prefs.push_enabled}
            onValueChange={(v) => void update({ push_enabled: v })}
          />
          <ToggleRow
            icon="📱"
            label="SMS"
            description="Pour ne rater aucun rappel de rendez-vous important."
            value={prefs.sms_enabled}
            onValueChange={(v) => void update({ sms_enabled: v })}
            disabled={!phone}
            disabledHint={
              !phone
                ? "Ajoutez d'abord votre numéro de téléphone ci-dessous."
                : undefined
            }
          />
          <ToggleRow
            icon="📧"
            label="Email"
            description="Coachings et résumés hebdomadaires."
            value={prefs.email_enabled}
            onValueChange={(v) => void update({ email_enabled: v })}
          />
        </Section>

        {/* Rappels RDV */}
        <Section
          title="Rappels de rendez-vous"
          subtitle="Quand voulez-vous être prévenu(e) avant un RDV ?"
        >
          <ToggleRow
            icon="📅"
            label="24 heures avant"
            description="Le rappel arrive la veille."
            value={prefs.rdv_reminder_24h}
            onValueChange={(v) => void update({ rdv_reminder_24h: v })}
          />
          <ToggleRow
            icon="⏰"
            label="1 heure avant"
            description="Juste à temps pour vous préparer."
            value={prefs.rdv_reminder_1h}
            onValueChange={(v) => void update({ rdv_reminder_1h: v })}
          />
          <ToggleRow
            icon="🎯"
            label="Au moment du RDV"
            description="Un lien pour rejoindre directement la téléconsultation."
            value={prefs.rdv_reminder_now}
            onValueChange={(v) => void update({ rdv_reminder_now: v })}
          />
        </Section>

        {/* Téléphone */}
        <Section
          title="Numéro de téléphone"
          subtitle="Format international, ex. +33612345678."
        >
          <View style={styles.phoneRow}>
            <TextInput
              style={styles.phoneInput}
              value={phone}
              onChangeText={setPhone}
              placeholder="+33612345678"
              placeholderTextColor={light.textDim}
              keyboardType="phone-pad"
              autoCorrect={false}
              accessibilityLabel="Numéro de téléphone"
            />
            <Pressable
              style={[
                styles.phoneSaveBtn,
                phone === (prefs.phone_e164 ?? "") && styles.phoneSaveBtnDisabled,
              ]}
              onPress={() => void onSavePhone()}
              disabled={phone === (prefs.phone_e164 ?? "") || saving}
              accessibilityRole="button"
              accessibilityLabel="Enregistrer le numéro"
            >
              <Text style={styles.phoneSaveText}>Enregistrer</Text>
            </Pressable>
          </View>
        </Section>

        <Pressable
          style={styles.backBtn}
          onPress={() => router.back()}
          accessibilityRole="button"
        >
          <Text style={styles.backText}>← Retour aux réglages</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Sous-composants
// ──────────────────────────────────────────────────────────────────────────

interface SectionProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}
function Section({ title, subtitle, children }: SectionProps) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.sectionSubtitle}>{subtitle}</Text> : null}
      <View style={styles.sectionCard}>{children}</View>
    </View>
  );
}

interface ToggleRowProps {
  icon: string;
  label: string;
  description: string;
  value: boolean;
  onValueChange: (v: boolean) => void;
  disabled?: boolean;
  disabledHint?: string;
}
function ToggleRow({
  icon, label, description, value, onValueChange, disabled, disabledHint,
}: ToggleRowProps) {
  return (
    <View
      style={[styles.row, disabled && { opacity: 0.5 }]}
      accessibilityRole="switch"
      accessibilityState={{ checked: value, disabled }}
      accessibilityLabel={label}
    >
      <Text style={styles.rowIcon}>{icon}</Text>
      <View style={styles.rowContent}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowDesc}>{disabled && disabledHint ? disabledHint : description}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{ false: light.border, true: palette.primary300 }}
        thumbColor={value ? palette.primary500 : "#fff"}
        disabled={disabled}
      />
    </View>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Styles
// ──────────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  kav: { flex: 1, backgroundColor: light.bg },
  loadingContainer: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: light.bg },
  scroll: { padding: space.xl, paddingBottom: space["4xl"] },

  section: { marginBottom: space["2xl"] },
  sectionTitle: {
    fontSize: font.size.base,
    fontWeight: font.weight.bold,
    color: light.text,
    marginBottom: space.xs,
    marginLeft: space.xs,
  },
  sectionSubtitle: {
    fontSize: font.size.sm,
    color: light.textMuted,
    marginBottom: space.md,
    marginLeft: space.xs,
  },
  sectionCard: {
    backgroundColor: light.surface,
    borderRadius: radius.lg,
    overflow: "hidden",
  },

  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
    gap: space.md,
    borderBottomWidth: 0.5,
    borderBottomColor: light.borderSoft,
  },
  rowIcon: { fontSize: 22, width: 30, textAlign: "center" },
  rowContent: { flex: 1, minWidth: 0 },
  rowLabel: { fontSize: font.size.base, fontWeight: font.weight.semibold, color: light.text },
  rowDesc: { fontSize: font.size.sm, color: light.textMuted, marginTop: 2, lineHeight: 18 },

  phoneRow: { flexDirection: "row", padding: space.md, gap: space.sm },
  phoneInput: {
    flex: 1,
    backgroundColor: light.surfaceAlt,
    borderColor: light.borderSoft,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: Platform.OS === "ios" ? 12 : 9,
    fontSize: font.size.base,
    color: light.text,
  },
  phoneSaveBtn: {
    paddingHorizontal: space.lg,
    backgroundColor: palette.primary500,
    borderRadius: radius.md,
    justifyContent: "center",
    alignItems: "center",
  },
  phoneSaveBtnDisabled: { backgroundColor: light.border },
  phoneSaveText: { color: "#fff", fontSize: font.size.sm, fontWeight: font.weight.semibold },

  backBtn: {
    marginTop: space.lg,
    padding: space.md,
    alignItems: "center",
  },
  backText: { color: palette.primary500, fontSize: font.size.sm, fontWeight: font.weight.medium },
});
