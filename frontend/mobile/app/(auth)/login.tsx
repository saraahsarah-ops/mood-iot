/**
 * Écran de connexion — délègue entièrement à Keycloak.
 *
 * Un seul bouton ouvre la hosted UI de Keycloak (FR), qui propose :
 *  - Email / mot de passe
 *  - Google Sign-In
 *  - Apple Sign-In (sur iOS)
 *  - TOTP MFA si activé sur le compte
 *  - Lien "Mot de passe oublié" → reset email envoyé par Keycloak
 *
 * Une fois le flow OIDC terminé, authStore stocke les tokens. Le _layout
 * racine décide de rediriger vers /(tabs)/ ou /(auth)/welcome.tsx si le
 * profil interne n'existe pas encore.
 */

import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useAuthStore } from "@/stores/authStore";

export default function LoginScreen() {
  const signingIn = useAuthStore((s) => s.signingIn);
  const error = useAuthStore((s) => s.error);
  const signIn = useAuthStore((s) => s.signIn);

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.logo} accessibilityLabel="Logo Mood-IoT">
          💙
        </Text>
        <Text style={styles.title}>Mood-IoT</Text>
        <Text style={styles.subtitle}>Suivi de votre bien-être</Text>

        {error ? (
          <Text style={styles.error} accessibilityRole="alert">
            {error}
          </Text>
        ) : null}

        <TouchableOpacity
          style={[styles.button, signingIn && styles.buttonDisabled]}
          onPress={() => {
            void signIn();
          }}
          disabled={signingIn}
          accessibilityRole="button"
          accessibilityLabel="Se connecter à Mood-IoT"
          accessibilityHint="Ouvre la page de connexion Mood-IoT dans votre navigateur"
        >
          {signingIn ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Se connecter</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.footnote}>
          Connexion sécurisée par OpenID Connect.{"\n"}
          Email, Google ou Apple — au choix.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f0f7ff",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  card: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: "#fff",
    borderRadius: 20,
    padding: 32,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
  logo: { fontSize: 48, marginBottom: 8 },
  title: { fontSize: 28, fontWeight: "700", color: "#0288d1" },
  subtitle: { fontSize: 14, color: "#666", marginBottom: 24 },
  error: {
    color: "#e74c3c",
    fontSize: 13,
    marginBottom: 12,
    textAlign: "center",
  },
  button: {
    width: "100%",
    height: 48,
    backgroundColor: "#0288d1",
    borderRadius: 12,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 8,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  footnote: {
    marginTop: 20,
    fontSize: 12,
    color: "#888",
    textAlign: "center",
    lineHeight: 18,
  },
});
