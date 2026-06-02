import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";

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

  useEffect(() => {
    if (loading) return;
    const inAuth = segments[0] === "(auth)";
    const atWelcome =
      segments[0] === "(auth)" && segments[1] === "welcome";

    if (!tokens) {
      // Non connecté → écran de login
      if (!inAuth || atWelcome) {
        router.replace("/(auth)/login");
      }
    } else if (!user) {
      // Connecté Keycloak mais pas de profil interne → écran welcome
      if (!atWelcome) {
        router.replace("/(auth)/welcome");
      }
    } else if (inAuth) {
      // Connecté + profil → app principale
      router.replace("/(tabs)");
    }
  }, [tokens, user, loading, segments, router]);

  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(tabs)" />
      </Stack>
    </>
  );
}
