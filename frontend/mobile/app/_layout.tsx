import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/authStore";
import { hasSeenOnboarding } from "./(auth)/onboarding";

export default function RootLayout() {
  const tokens = useAuthStore((s) => s.tokens);
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const restore = useAuthStore((s) => s.restore);
  const router = useRouter();
  const segments = useSegments();
  const [onboardingChecked, setOnboardingChecked] = useState(false);
  const [onboardingSeen, setOnboardingSeen] = useState(false);

  // Bootstrap : restaure session au démarrage de l'app
  useEffect(() => {
    void restore();
    void hasSeenOnboarding().then((seen) => {
      setOnboardingSeen(seen);
      setOnboardingChecked(true);
    });
  }, [restore]);

  useEffect(() => {
    if (loading || !onboardingChecked) return;
    const segs: string[] = segments as unknown as string[];
    const inAuth = segs[0] === "(auth)";
    const atWelcome = segs[0] === "(auth)" && segs[1] === "welcome";
    const atOnboarding = segs[0] === "(auth)" && segs[1] === "onboarding";

    // Onboarding : premier lancement, jamais connecté
    if (!tokens && !onboardingSeen && !atOnboarding) {
      router.replace("/(auth)/onboarding");
      return;
    }

    if (!tokens) {
      // Non connecté → écran de login (sauf si déjà sur onboarding)
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
  }, [tokens, user, loading, segments, router, onboardingChecked, onboardingSeen]);

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
