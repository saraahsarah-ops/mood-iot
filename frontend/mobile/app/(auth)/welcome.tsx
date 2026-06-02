/**
 * Écran de bienvenue — premier login Keycloak.
 *
 * Quand `/auth/me` retourne 404, c'est que l'utilisateur a un compte Keycloak
 * mais pas encore de profil interne (`users` + `patient_profile`). Cet écran
 * lui demande prénom, nom, date de naissance, genre, puis appelle
 * `POST /auth/register-profile` pour finaliser.
 *
 * Cible : patients uniquement (les médecins s'inscrivent côté dashboard).
 */

import { useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { router } from "expo-router";
import { registerProfile } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

type Gender = "M" | "F" | "autre";

export default function WelcomeScreen() {
  const tokens = useAuthStore((s) => s.tokens);
  const refreshUser = useAuthStore((s) => s.refreshUser);
  const signOut = useAuthStore((s) => s.signOut);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [birth, setBirth] = useState(""); // YYYY-MM-DD
  const [gender, setGender] = useState<Gender | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!firstName.trim() || !lastName.trim()) {
      setError("Veuillez indiquer votre prénom et votre nom.");
      return;
    }
    if (!tokens) {
      setError("Session expirée — veuillez vous reconnecter.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await registerProfile(
        {
          role: "patient",
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          date_of_birth: birth || undefined,
          gender: gender || undefined,
        },
        tokens.accessToken,
      );
      await refreshUser();
      router.replace("/(tabs)");
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "Création du profil impossible.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Bienvenue sur Mood-IoT</Text>
      <Text style={styles.subtitle}>
        Quelques informations pour finaliser votre compte patient.
      </Text>

      {error ? (
        <Text style={styles.error} accessibilityRole="alert">
          {error}
        </Text>
      ) : null}

      <Text style={styles.label}>Prénom</Text>
      <TextInput
        style={styles.input}
        value={firstName}
        onChangeText={setFirstName}
        autoCapitalize="words"
        placeholder="Votre prénom"
        placeholderTextColor="#999"
        accessibilityLabel="Prénom"
      />

      <Text style={styles.label}>Nom</Text>
      <TextInput
        style={styles.input}
        value={lastName}
        onChangeText={setLastName}
        autoCapitalize="words"
        placeholder="Votre nom"
        placeholderTextColor="#999"
        accessibilityLabel="Nom de famille"
      />

      <Text style={styles.label}>Date de naissance (facultatif)</Text>
      <TextInput
        style={styles.input}
        value={birth}
        onChangeText={setBirth}
        placeholder="AAAA-MM-JJ"
        placeholderTextColor="#999"
        keyboardType="numbers-and-punctuation"
        accessibilityLabel="Date de naissance au format année mois jour"
      />

      <Text style={styles.label}>Genre (facultatif)</Text>
      <View style={styles.genderRow}>
        {(["F", "M", "autre"] as Gender[]).map((g) => (
          <TouchableOpacity
            key={g}
            style={[
              styles.genderChip,
              gender === g && styles.genderChipSelected,
            ]}
            onPress={() => setGender(g)}
            accessibilityRole="radio"
            accessibilityState={{ selected: gender === g }}
            accessibilityLabel={labelFor(g)}
          >
            <Text
              style={[
                styles.genderText,
                gender === g && styles.genderTextSelected,
              ]}
            >
              {labelFor(g)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity
        style={[styles.button, loading && styles.buttonDisabled]}
        onPress={handleSubmit}
        disabled={loading}
        accessibilityRole="button"
        accessibilityLabel="Créer mon profil"
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Créer mon profil</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.linkButton}
        onPress={() => {
          void signOut();
        }}
        accessibilityRole="button"
        accessibilityLabel="Annuler et me déconnecter"
      >
        <Text style={styles.linkText}>Annuler et me déconnecter</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function labelFor(g: Gender): string {
  if (g === "F") return "Femme";
  if (g === "M") return "Homme";
  return "Autre";
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    paddingTop: 60,
    backgroundColor: "#f0f7ff",
    flexGrow: 1,
  },
  title: { fontSize: 26, fontWeight: "700", color: "#0288d1" },
  subtitle: { fontSize: 14, color: "#555", marginTop: 6, marginBottom: 24 },
  error: {
    color: "#e74c3c",
    fontSize: 13,
    marginBottom: 12,
    textAlign: "center",
  },
  label: {
    fontSize: 13,
    color: "#444",
    marginTop: 12,
    marginBottom: 6,
    fontWeight: "600",
  },
  input: {
    height: 48,
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 15,
    backgroundColor: "#fff",
  },
  genderRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 4,
  },
  genderChip: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#ddd",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  genderChipSelected: {
    backgroundColor: "#0288d1",
    borderColor: "#0288d1",
  },
  genderText: { fontSize: 14, color: "#555" },
  genderTextSelected: { color: "#fff", fontWeight: "600" },
  button: {
    height: 48,
    backgroundColor: "#0288d1",
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 24,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  linkButton: { marginTop: 16, alignItems: "center" },
  linkText: { color: "#0288d1", fontSize: 14 },
});
