import { View, Text, StyleSheet } from "react-native";

interface Props {
  score: number; // 0-100 score clinico (NO se muestra al paciente)
}

/**
 * Muestra el bienestar en 3 niveles (el paciente NO ve el score numerico).
 * - Niveau 1 (score < 40) : Vert — "Tout va bien"
 * - Niveau 2 (score 40-69) : Jaune — "Restez vigilant(e)"
 * - Niveau 3 (score >= 70) : Rouge — "Contactez votre medecin"
 */
export default function WellbeingGauge({ score }: Props) {
  const level =
    score >= 70
      ? {
          niveau: 3,
          emoji: "🔴",
          color: "#e74c3c",
          bg: "#fdecea",
          label: "Contactez votre medecin",
          description: "Votre bien-etre necessite une attention particuliere.",
        }
      : score >= 40
        ? {
            niveau: 2,
            emoji: "🟡",
            color: "#f39c12",
            bg: "#fef9e7",
            label: "Restez vigilant(e)",
            description: "Prenez soin de vous. Pensez a une activite legere.",
          }
        : {
            niveau: 1,
            emoji: "🟢",
            color: "#2ecc71",
            bg: "#eafaf1",
            label: "Tout va bien",
            description: "Continuez comme ca, votre routine est equilibree !",
          };

  return (
    <View style={[styles.card, { backgroundColor: level.bg }]}>
      <Text style={styles.emoji}>{level.emoji}</Text>
      <Text style={[styles.niveau, { color: level.color }]}>
        Niveau {level.niveau}
      </Text>
      <Text style={[styles.label, { color: level.color }]}>{level.label}</Text>
      <Text style={styles.description}>{level.description}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    padding: 24,
    alignItems: "center",
    marginTop: 8,
  },
  emoji: { fontSize: 48, marginBottom: 8 },
  niveau: { fontSize: 20, fontWeight: "800" },
  label: { fontSize: 16, fontWeight: "600", marginTop: 4 },
  description: {
    fontSize: 13,
    color: "#666",
    textAlign: "center",
    marginTop: 8,
    lineHeight: 20,
  },
});
