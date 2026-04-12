import { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Alert,
} from "react-native";
import { useHealthStore } from "@/stores/healthStore";

const PHQ9_QUESTIONS = [
  "Peu d'interet ou de plaisir a faire les choses",
  "Se sentir triste, deprime(e) ou sans espoir",
  "Difficultes a s'endormir, sommeil interrompu ou trop dormir",
  "Se sentir fatigue(e) ou manquer d'energie",
  "Peu d'appetit ou manger trop",
  "Mauvaise opinion de soi-meme",
  "Difficultes a se concentrer",
  "Se deplacer ou parler lentement / etre agite(e)",
  "Penser qu'il vaudrait mieux mourir ou se faire du mal",
];

const SCORE_LABELS = [
  { value: 0, label: "Pas du tout", emoji: "😊" },
  { value: 1, label: "Plusieurs jours", emoji: "😐" },
  { value: 2, label: "Plus de la moitie", emoji: "😟" },
  { value: 3, label: "Presque tous les jours", emoji: "😞" },
];

export default function MoodScreen() {
  const [answers, setAnswers] = useState<number[]>(Array(9).fill(-1));
  const [submitted, setSubmitted] = useState(false);
  const submitPhq9 = useHealthStore((s) => s.submitPhq9);

  function setAnswer(qIndex: number, value: number) {
    const next = [...answers];
    next[qIndex] = value;
    setAnswers(next);
  }

  const allAnswered = answers.every((a) => a >= 0);
  const total = answers.reduce((s, v) => s + Math.max(0, v), 0);

  async function handleSubmit() {
    if (!allAnswered) return;
    try {
      await submitPhq9(answers);
      setSubmitted(true);
    } catch {
      Alert.alert("Erreur", "Impossible d'envoyer le questionnaire.");
    }
  }

  if (submitted) {
    const severity =
      total <= 4
        ? { label: "Minimal", emoji: "🟢", color: "#2ecc71" }
        : total <= 9
          ? { label: "Leger", emoji: "🟡", color: "#f39c12" }
          : total <= 14
            ? { label: "Modere", emoji: "🟠", color: "#e67e22" }
            : { label: "Severe", emoji: "🔴", color: "#e74c3c" };

    return (
      <View style={[styles.container, styles.resultContainer]}>
        <Text style={styles.resultEmoji}>{severity.emoji}</Text>
        <Text style={styles.resultTitle}>Questionnaire envoye</Text>
        <Text style={[styles.resultScore, { color: severity.color }]}>
          Score PHQ-9 : {total}/27
        </Text>
        <Text style={styles.resultLabel}>Niveau : {severity.label}</Text>
        <Text style={styles.resultInfo}>
          Votre medecin recevra ces informations pour mieux vous accompagner.
        </Text>
        <TouchableOpacity
          style={styles.retryButton}
          onPress={() => {
            setAnswers(Array(9).fill(-1));
            setSubmitted(false);
          }}
        >
          <Text style={styles.retryText}>Refaire le questionnaire</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Comment vous sentez-vous ?</Text>
      <Text style={styles.subheader}>
        Au cours des 2 dernieres semaines, a quelle frequence avez-vous ete
        gene(e) par les problemes suivants ?
      </Text>

      {PHQ9_QUESTIONS.map((q, qi) => (
        <View key={qi} style={styles.questionBlock}>
          <Text style={styles.questionText}>
            {qi + 1}. {q}
          </Text>
          <View style={styles.optionsRow}>
            {SCORE_LABELS.map((opt) => (
              <TouchableOpacity
                key={opt.value}
                style={[
                  styles.optionButton,
                  answers[qi] === opt.value && styles.optionSelected,
                ]}
                onPress={() => setAnswer(qi, opt.value)}
              >
                <Text style={styles.optionEmoji}>{opt.emoji}</Text>
                <Text
                  style={[
                    styles.optionLabel,
                    answers[qi] === opt.value && styles.optionLabelSelected,
                  ]}
                  numberOfLines={2}
                >
                  {opt.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ))}

      <TouchableOpacity
        style={[styles.submitButton, !allAnswered && styles.submitDisabled]}
        onPress={handleSubmit}
        disabled={!allAnswered}
      >
        <Text style={styles.submitText}>
          Envoyer ({answers.filter((a) => a >= 0).length}/9)
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f7ff" },
  content: { padding: 20, paddingBottom: 40 },
  header: { fontSize: 22, fontWeight: "700", color: "#333" },
  subheader: { fontSize: 13, color: "#777", marginTop: 6, marginBottom: 20 },
  questionBlock: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  questionText: { fontSize: 14, fontWeight: "500", color: "#444", marginBottom: 10 },
  optionsRow: { flexDirection: "row", gap: 6 },
  optionButton: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#e0e0e0",
    backgroundColor: "#fafafa",
  },
  optionSelected: {
    borderColor: "#0288d1",
    backgroundColor: "#e3f2fd",
  },
  optionEmoji: { fontSize: 20, marginBottom: 2 },
  optionLabel: { fontSize: 9, color: "#777", textAlign: "center" },
  optionLabelSelected: { color: "#0288d1", fontWeight: "600" },
  submitButton: {
    backgroundColor: "#0288d1",
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 8,
  },
  submitDisabled: { opacity: 0.4 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  resultContainer: { justifyContent: "center", alignItems: "center", padding: 32 },
  resultEmoji: { fontSize: 60, marginBottom: 12 },
  resultTitle: { fontSize: 22, fontWeight: "700", color: "#333" },
  resultScore: { fontSize: 28, fontWeight: "800", marginTop: 8 },
  resultLabel: { fontSize: 16, color: "#666", marginTop: 4 },
  resultInfo: {
    fontSize: 13,
    color: "#999",
    textAlign: "center",
    marginTop: 16,
    lineHeight: 20,
  },
  retryButton: {
    marginTop: 24,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#0288d1",
  },
  retryText: { color: "#0288d1", fontWeight: "600" },
});
