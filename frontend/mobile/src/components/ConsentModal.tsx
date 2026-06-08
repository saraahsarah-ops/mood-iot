/**
 * Modal de consentement RGPD + Conditions générales d'utilisation.
 *
 * Affiché APRÈS le premier login si l'utilisateur n'a pas encore donné
 * son consentement (vérifié via l'endpoint backend `/patients/me/consents`).
 *
 * Trois cases distinctes — chacune correspond à un type de consentement
 * stocké horodaté côté backend (RGPD oblige).
 */

import { useState } from "react";
import {
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { palette, light, space, radius, font } from "@/theme/tokens";

export interface ConsentValues {
  cgu: boolean;
  rgpd: boolean;
  healthSensors: boolean;
  aiRecommendations: boolean;
}

export interface ConsentModalProps {
  visible: boolean;
  onAccept: (values: ConsentValues) => void;
  onDecline: () => void;
}

export function ConsentModal({ visible, onAccept, onDecline }: ConsentModalProps) {
  const [cgu, setCgu] = useState(false);
  const [rgpd, setRgpd] = useState(false);
  const [healthSensors, setHealthSensors] = useState(false);
  const [aiRecommendations, setAiRecommendations] = useState(false);

  // Minimum requis : CGU + RGPD. Capteurs et IA sont optionnels.
  const canAccept = cgu && rgpd;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onDecline}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <ScrollView contentContainerStyle={styles.content}>
            <Text style={styles.title}>Avant de continuer</Text>
            <Text style={styles.subtitle}>
              Mood-IoT respecte vos données. Voici ce que nous vous demandons :
            </Text>

            {/* Required */}
            <ConsentItem
              required
              checked={cgu}
              onToggle={() => setCgu(!cgu)}
              title="J'accepte les conditions générales d'utilisation"
              description={
                <Text style={styles.itemDesc}>
                  Mood-IoT n'est pas un dispositif médical. Les suggestions sont
                  informatives.{" "}
                  <Text
                    style={styles.link}
                    onPress={() => void Linking.openURL("https://mood-iot.fr/cgu")}
                  >
                    Lire les CGU
                  </Text>
                </Text>
              }
            />

            <ConsentItem
              required
              checked={rgpd}
              onToggle={() => setRgpd(!rgpd)}
              title="J'autorise le traitement de mes données (RGPD)"
              description={
                <Text style={styles.itemDesc}>
                  Vos données sont chiffrées et hébergées en France (HDS). Vous
                  pouvez les exporter ou les supprimer à tout moment depuis
                  Réglages.{" "}
                  <Text
                    style={styles.link}
                    onPress={() => void Linking.openURL("https://mood-iot.fr/rgpd")}
                  >
                    Politique de confidentialité
                  </Text>
                </Text>
              }
            />

            {/* Optional */}
            <Text style={styles.optionalHeader}>Optionnel — vous pourrez changer plus tard</Text>

            <ConsentItem
              checked={healthSensors}
              onToggle={() => setHealthSensors(!healthSensors)}
              title="Accès à mes capteurs santé"
              description={
                <Text style={styles.itemDesc}>
                  Permet de récupérer rythme cardiaque, pas, sommeil depuis
                  Apple Santé (iOS) ou Health Connect (Android). Vous serez
                  ensuite redirigé vers la fenêtre de permission du système.
                </Text>
              }
            />

            <ConsentItem
              checked={aiRecommendations}
              onToggle={() => setAiRecommendations(!aiRecommendations)}
              title="Recommandations personnalisées par IA"
              description={
                <Text style={styles.itemDesc}>
                  Nous générons des suggestions de bien-être en analysant vos
                  données (sommeil, activité). Le contenu reste indicatif et ne
                  remplace jamais l'avis de votre médecin.
                </Text>
              }
            />
          </ScrollView>

          <View style={styles.actions}>
            <Pressable
              onPress={onDecline}
              style={styles.declineBtn}
              accessibilityRole="button"
              accessibilityLabel="Refuser et se déconnecter"
            >
              <Text style={styles.declineText}>Refuser</Text>
            </Pressable>
            <Pressable
              onPress={() =>
                onAccept({ cgu, rgpd, healthSensors, aiRecommendations })
              }
              disabled={!canAccept}
              style={[
                styles.acceptBtn,
                !canAccept && styles.acceptBtnDisabled,
              ]}
              accessibilityRole="button"
              accessibilityLabel="Accepter et continuer"
            >
              <Text style={styles.acceptText}>Accepter et continuer</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

interface ConsentItemProps {
  required?: boolean;
  checked: boolean;
  onToggle: () => void;
  title: string;
  description: React.ReactNode;
}

function ConsentItem({ required, checked, onToggle, title, description }: ConsentItemProps) {
  return (
    <Pressable
      onPress={onToggle}
      style={[styles.item, checked && styles.itemChecked]}
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      accessibilityLabel={title}
    >
      <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
        {checked ? <Text style={styles.checkmark}>✓</Text> : null}
      </View>
      <View style={styles.itemContent}>
        <Text style={styles.itemTitle}>
          {title}
          {required ? <Text style={styles.required}> *</Text> : null}
        </Text>
        {description}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: light.overlay,
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: light.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    maxHeight: "92%",
  },
  content: { padding: space["2xl"], gap: space.md },

  title: {
    fontSize: font.size["2xl"],
    fontWeight: font.weight.bold,
    color: light.text,
  },
  subtitle: {
    fontSize: font.size.sm,
    color: light.textMuted,
    marginBottom: space.lg,
  },

  optionalHeader: {
    fontSize: font.size.xs,
    fontWeight: font.weight.semibold,
    color: light.textDim,
    textTransform: "uppercase" as const,
    letterSpacing: 0.5,
    marginTop: space.lg,
    marginBottom: space.sm,
  },

  item: {
    flexDirection: "row",
    gap: space.md,
    padding: space.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: light.borderSoft,
    backgroundColor: light.surfaceAlt,
  },
  itemChecked: {
    borderColor: palette.primary300,
    backgroundColor: palette.primary50,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: radius.sm,
    borderWidth: 2,
    borderColor: light.border,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 2,
  },
  checkboxChecked: {
    backgroundColor: palette.primary500,
    borderColor: palette.primary500,
  },
  checkmark: { color: "#fff", fontSize: 14, fontWeight: font.weight.bold },

  itemContent: { flex: 1, gap: 4 },
  itemTitle: {
    fontSize: font.size.base,
    fontWeight: font.weight.semibold,
    color: light.text,
  },
  itemDesc: { fontSize: font.size.sm, color: light.textMuted, lineHeight: 20 },
  link: { color: palette.primary500, textDecorationLine: "underline" },
  required: { color: palette.danger500 },

  actions: {
    flexDirection: "row",
    padding: space["2xl"],
    paddingTop: space.lg,
    gap: space.md,
    borderTopWidth: 1,
    borderTopColor: light.borderSoft,
  },
  declineBtn: {
    flex: 1,
    height: 50,
    borderRadius: radius.lg,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: light.border,
  },
  declineText: { color: light.textMuted, fontSize: font.size.base, fontWeight: font.weight.medium },
  acceptBtn: {
    flex: 2,
    height: 50,
    borderRadius: radius.lg,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: palette.primary500,
  },
  acceptBtnDisabled: { backgroundColor: light.border },
  acceptText: { color: "#fff", fontSize: font.size.base, fontWeight: font.weight.bold },
});
