import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { useAuthStore } from "@/stores/authStore";
import { hasSeenOnboarding } from "./(auth)/onboarding";
import { getPermissionsState } from "@/services/healthSync";

export default function RootLayout() {
  const tokens = useAuthStore((s) => s.tokens);
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const restore = useAuthStore((s) => s.restore);
  const router = useRouter();
  const segments = useSegments();

  // Bootstrap : restaure session au démarrage de l'app
  useEffect(() => {
    void restore();
  }, [restore]);

  // Re-lit SecureStore à CHAQUE changement de segment pour éviter le bug
  // "onboarding seen mais state pas à jour" → boucle infinie sur l'écran 1.
  useEffect(() => {
    if (loading) return;
    void (async () => {
      const segs: string[] = segments as unknown as string[];
      const inAuth = segs[0] === "(auth)";
      const atWelcome = segs[0] === "(auth)" && segs[1] === "welcome";
      const atOnboarding = segs[0] === "(auth)" && segs[1] === "onboarding";
      const atHealthPerms =
        segs[0] === "(auth)" && segs[1] === "health-permissions";

      const seen = await hasSeenOnboarding();

      // 1. Onboarding : premier lancement, jamais connecté
      if (!tokens && !seen && !atOnboarding) {
        router.replace("/(auth)/onboarding");
        return;
      }

      if (!tokens) {
        // Non connecté → écran de login (sauf si onboarding en cours)
        if (atOnboarding) return;
        if (!inAuth || atWelcome) {
          router.replace("/(auth)/login");
        }
        return;
      }

      if (!user) {
        // Connecté Keycloak mais pas de profil interne → welcome
        if (!atWelcome) {
          router.replace("/(auth)/welcome");
        }
        return;
      }

      // Connecté + profil
      if (inAuth) {
        if (atHealthPerms) return;
        const p = await getPermissionsState();
        if (!p.hasAsked) {
          router.replace("/(auth)/health-permissions");
        } else {
          router.replace("/(tabs)");
        }
      }
    })();
  }, [tokens, user, loading, segments, router]);

  return (
    <>
      <StatusBar style="dark" />
      <SafeAreaProvider>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="(auth)" />
          <Stack.Screen name="(tabs)" />
        </Stack>
      </SafeAreaProvider>
    </>
  );
}
