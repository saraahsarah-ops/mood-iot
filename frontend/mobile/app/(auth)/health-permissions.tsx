/**
 * Écran "Autorisation des capteurs santé".
 *
 * Affiché une fois après le 1er login (si pas déjà passé). Demande l'accès
 * à Health Connect (Android) avec justifications FR explicites.
 *
 * Sur iOS, l'écran s'affiche aussi mais indique que HealthKit sera activé
 * dans une prochaine version.
 */

import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  requestPermissions,
  markPermissionsAsked,
  getSupportedPlatform,
} from "@/services/healthSync";
import { palette, light, space, radius, font } from "@/theme/tokens";

const PERMISSIONS_LIST = [
  {
    icon: "❤️",
    label: "Fréquence cardiaque",
    desc: "Suivre votre rythme cardiaque au repos et son évolution.",
  },
  {
    icon: "💤",
    label: "Sommeil",
    desc: "Mesurer la durée et la régularité de vos nuits.",
  },
  {
    icon: "🚶",
    label: "Activité physique (pas)",
    desc: "Évaluer votre niveau de mobilité quotidien.",
  },
  {
    icon: "📊",
    label: "Variabilité cardiaque (HRV)",
    desc: "Indicateur de stress et de récupération.",
  },
  {
    icon: "🩺",
    label: "Tension artérielle & SpO₂",
    desc: "Si votre montre/tensiomètre les mesure (optionnel).",
  },
];

export default function HealthPermissionsScreen() {
  const [loading, setLoading] = useState(false);
  const platform = getSupportedPlatform();
  const insets = useSafeAreaInsets();

  const onAccept = async () => {
    setLoading(true);
    try {
      const granted = await requestPermissions();
      if (!granted && platform === "android") {
        Alert.alert(
          "Autorisations non accordées",
          "Vous pouvez les activer plus tard depuis l'application Health Connect.",
        );
      }
    } finally {
      setLoading(false);
      router.replace("/(tabs)");
    }
  };

  const onSkip = async () => {
    await markPermissionsAsked();
    router.replace("/(tabs)");
  };

  return (
    <ScrollView
      contentContainerStyle={[
        styles.container,
        {
          paddingTop: insets.top + space.xl,
          paddingBottom: Math.max(insets.bottom + space.md, space["4xl"]),
        },
      ]}
    >
      <View style={styles.iconCircle}>
        <Text style={styles.iconEmoji}>📲</Text>
      </View>

      <Text style={styles.title}>Autorisez l'accès à vos capteurs</Text>
      <Text style={styles.subtitle}>
        Mood-IoT lit vos données de santé localement sur votre téléphone
        pour mieux comprendre votre bien-être. Vous gardez la main : vous pouvez
        révoquer l'accès à tout moment.
      </Text>

      <View style={styles.list}>
        {PERMISSIONS_LIST.map((p) => (
          <View key={p.label} style={styles.row}>
            <Text style={styles.rowIcon}>{p.icon}</Text>
            <View style={styles.rowContent}>
              <Text style={styles.rowLabel}>{p.label}</Text>
              <Text style={styles.rowDesc}>{p.desc}</Text>
            </View>
          </View>
        ))}
      </View>

      <View style={styles.notice}>
        <Text style={styles.noticeText}>
          🔒 Vos données restent chiffrées et hébergées en France (OVH HDS).
          Elles ne sont partagées qu'avec votre médecin référent.
        </Text>
      </View>

      {platform === "ios" && (
        <View style={styles.iosNote}>
          <Text style={styles.iosNoteText}>
            ℹ️ Sur iPhone, l'intégration HealthKit sera disponible dans une
            prochaine version. Vous pouvez continuer sans pour le moment.
          </Text>
        </View>
      )}

      <Pressable
        style={[styles.btnPrimary, loading && { opacity: 0.6 }]}
        disabled={loading}
        onPress={() => void onAccept()}
        accessibilityRole="button"
        accessibilityLabel="Autoriser l'accès aux capteurs santé"
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.btnPrimaryText}>
            {Platform.OS === "android"
              ? "Autoriser Health Connect"
              : "Continuer"}
          </Text>
        )}
      </Pressable>

      <Pressable
        style={styles.btnSecondary}
        onPress={() => void onSkip()}
        accessibilityRole="button"
        accessibilityLabel="Passer cette étape"
      >
        <Text style={styles.btnSecondaryText}>Plus tard</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    backgroundColor: light.bg,
    paddingHorizontal: space.xl,
  },
  iconCircle: {
    alignSelf: "center",
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: palette.primary100,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: space.lg,
  },
  iconEmoji: { fontSize: 40 },
  title: {
    fontSize: font.size["2xl"],
    fontWeight: font.weight.bold,
    color: light.text,
    textAlign: "center",
    marginBottom: space.sm,
  },
  subtitle: {
    fontSize: font.size.base,
    color: light.textMuted,
    textAlign: "center",
    lineHeight: 22,
    marginBottom: space["2xl"],
  },
  list: {
    backgroundColor: light.surface,
    borderRadius: radius.lg,
    padding: space.sm,
    marginBottom: space.lg,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingHorizontal: space.md,
    paddingVertical: space.md,
    gap: space.md,
  },
  rowIcon: { fontSize: 26, width: 36, textAlign: "center" },
  rowContent: { flex: 1, minWidth: 0 },
  rowLabel: {
    fontSize: font.size.base,
    fontWeight: font.weight.semibold,
    color: light.text,
  },
  rowDesc: {
    fontSize: font.size.sm,
    color: light.textMuted,
    marginTop: 2,
    lineHeight: 18,
  },
  notice: {
    backgroundColor: palette.primary50,
    borderRadius: radius.md,
    padding: space.md,
    marginBottom: space.md,
  },
  noticeText: { fontSize: font.size.sm, color: palette.primary900, lineHeight: 20 },
  iosNote: {
    backgroundColor: "#fff3e0",
    borderRadius: radius.md,
    padding: space.md,
    marginBottom: space.md,
  },
  iosNoteText: { fontSize: font.size.sm, color: "#8a6d3b", lineHeight: 20 },
  btnPrimary: {
    backgroundColor: palette.primary500,
    paddingVertical: space.lg,
    borderRadius: radius.md,
    alignItems: "center",
    marginTop: space.md,
  },
  btnPrimaryText: { color: "#fff", fontSize: font.size.lg, fontWeight: font.weight.semibold },
  btnSecondary: {
    paddingVertical: space.md,
    alignItems: "center",
    marginTop: space.sm,
  },
  btnSecondaryText: { color: palette.primary500, fontSize: font.size.base, fontWeight: font.weight.medium },
});
