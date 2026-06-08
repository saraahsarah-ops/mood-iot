/**
 * Écran de connexion natif (email + mot de passe).
 *
 * Pas de redirection vers le navigateur : l'app POSTe directement les
 * identifiants vers Keycloak (Resource Owner Password Grant). C'est le flow
 * attendu pour une app mobile "moderne".
 *
 * Pour Google / Apple Sign-In / MFA on conservera un bouton secondaire qui
 * déclenche le flow PKCE hosted (signIn classique) — pas encore exposé.
 */

import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Link } from "expo-router";
import { useAuthStore } from "@/stores/authStore";

export default function LoginScreen() {
  const signingIn = useAuthStore((s) => s.signingIn);
  const error = useAuthStore((s) => s.error);
  const signInWithEmailPassword = useAuthStore(
    (s) => s.signInWithEmailPassword,
  );

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const canSubmit = email.trim().length > 3 && password.length >= 1 && !signingIn;

  const onSubmit = async () => {
    setLocalError(null);
    if (!canSubmit) {
      setLocalError("Veuillez saisir votre email et votre mot de passe.");
      return;
    }
    try {
      await signInWithEmailPassword(email, password);
    } catch {
      // L'erreur est déjà dans le store (set par signInWithEmailPassword)
    }
  };

  const displayError = localError || error;

  return (
    <KeyboardAvoidingView
      style={styles.kav}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo} accessibilityLabel="Logo Mood-IoT">
            💙
          </Text>
          <Text style={styles.title}>Mood-IoT</Text>
          <Text style={styles.subtitle}>Suivi de votre bien-être</Text>
        </View>

        {/* Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Connexion</Text>

          {/* Email */}
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="vous@example.com"
            placeholderTextColor="#bbb"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
            returnKeyType="next"
            accessibilityLabel="Adresse email"
          />

          {/* Password */}
          <Text style={styles.label}>Mot de passe</Text>
          <View style={styles.passwordRow}>
            <TextInput
              style={[styles.input, { flex: 1, marginBottom: 0 }]}
              value={password}
              onChangeText={setPassword}
              placeholder="••••••••"
              placeholderTextColor="#bbb"
              secureTextEntry={!showPassword}
              autoCapitalize="none"
              autoCorrect={false}
              textContentType="password"
              returnKeyType="go"
              onSubmitEditing={onSubmit}
              accessibilityLabel="Mot de passe"
            />
            <Pressable
              onPress={() => setShowPassword((v) => !v)}
              style={styles.eyeBtn}
              accessibilityRole="button"
              accessibilityLabel={
                showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"
              }
            >
              <Text style={styles.eyeText}>{showPassword ? "🙈" : "👁️"}</Text>
            </Pressable>
          </View>

          {/* Error banner */}
          {displayError ? (
            <View style={styles.errorBox} accessibilityRole="alert">
              <Text style={styles.errorText}>{displayError}</Text>
            </View>
          ) : null}

          {/* Submit */}
          <Pressable
            style={({ pressed }) => [
              styles.button,
              (!canSubmit || signingIn) && styles.buttonDisabled,
              pressed && canSubmit && styles.buttonPressed,
            ]}
            onPress={onSubmit}
            disabled={!canSubmit}
            accessibilityRole="button"
            accessibilityLabel="Se connecter"
          >
            {signingIn ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Se connecter</Text>
            )}
          </Pressable>

          {/* Forgot password */}
          <Link href="/(auth)/login" asChild>
            <Pressable style={styles.linkRow} accessibilityRole="link">
              <Text style={styles.linkText}>Mot de passe oublié ?</Text>
            </Pressable>
          </Link>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footnote}>
            Pas encore de compte ?{" "}
            <Text
              style={styles.footnoteLink}
              accessibilityRole="link"
              onPress={() => {
                /* TODO : ouvrir l'écran inscription en Phase 2.7 */
              }}
            >
              S'inscrire
            </Text>
          </Text>
          <Text style={styles.disclaimer}>
            Vos données sont chiffrées (AES-256) et hébergées en France.
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  kav: { flex: 1, backgroundColor: "#f0f7ff" },
  scroll: {
    flexGrow: 1,
    justifyContent: "center",
    padding: 24,
  },
  header: {
    alignItems: "center",
    marginBottom: 24,
  },
  logo: { fontSize: 56, marginBottom: 8 },
  title: { fontSize: 32, fontWeight: "700", color: "#0288d1" },
  subtitle: { fontSize: 14, color: "#666", marginTop: 4 },

  card: {
    backgroundColor: "#fff",
    borderRadius: 20,
    padding: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#222",
    marginBottom: 20,
    textAlign: "center",
  },

  label: {
    fontSize: 13,
    fontWeight: "600",
    color: "#444",
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: "#dbe2ec",
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: Platform.OS === "ios" ? 14 : 11,
    fontSize: 16,
    color: "#222",
    backgroundColor: "#f8fafd",
    marginBottom: 4,
  },
  passwordRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  eyeBtn: {
    height: 48,
    width: 48,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: 12,
    backgroundColor: "#f8fafd",
    borderWidth: 1,
    borderColor: "#dbe2ec",
  },
  eyeText: { fontSize: 20 },

  errorBox: {
    backgroundColor: "#fdecea",
    borderColor: "#f5b7b1",
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginTop: 16,
  },
  errorText: { color: "#c0392b", fontSize: 13, lineHeight: 18 },

  button: {
    height: 52,
    backgroundColor: "#0288d1",
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 20,
    shadowColor: "#0288d1",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 3,
  },
  buttonDisabled: { opacity: 0.5, shadowOpacity: 0 },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  linkRow: {
    marginTop: 14,
    alignItems: "center",
  },
  linkText: { color: "#0288d1", fontSize: 13, fontWeight: "500" },

  footer: {
    alignItems: "center",
    marginTop: 24,
  },
  footnote: {
    fontSize: 14,
    color: "#666",
    marginBottom: 8,
  },
  footnoteLink: { color: "#0288d1", fontWeight: "600" },
  disclaimer: {
    fontSize: 11,
    color: "#999",
    marginTop: 12,
    textAlign: "center",
    paddingHorizontal: 16,
  },
});
