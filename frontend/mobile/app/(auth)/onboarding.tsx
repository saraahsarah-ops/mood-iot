/**
 * Onboarding — 3 slides présentant Mood-IoT au premier lancement.
 *
 * Affiché AVANT le login si l'utilisateur n'a pas encore vu l'onboarding
 * (flag persisté dans expo-secure-store). Skippable, mais utile pour
 * comprendre ce que fait l'app et qui a accès aux données.
 */

import { useRef, useState } from "react";
import {
  Dimensions,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  NativeSyntheticEvent,
  NativeScrollEvent,
} from "react-native";
import { router } from "expo-router";
import * as SecureStore from "expo-secure-store";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { palette, light, space, radius, font } from "@/theme/tokens";

interface Slide {
  emoji: string;
  title: string;
  body: string;
  bullets?: string[];
}

const SLIDES: Slide[] = [
  {
    emoji: "💙",
    title: "Bienvenue sur Mood-IoT",
    body: "Mood-IoT vous accompagne au quotidien dans le suivi de votre bien-être, en lien avec votre médecin.",
    bullets: [
      "Indiquez votre humeur en un clic",
      "Connectez vos capteurs santé",
      "Restez en contact avec votre praticien",
    ],
  },
  {
    emoji: "🔒",
    title: "Vos données sont protégées",
    body: "Toutes vos données sont chiffrées et hébergées en France (HDS).",
    bullets: [
      "Chiffrement AES-256 au repos",
      "Communication TLS bout-en-bout",
      "Souveraineté française — RGPD strict",
      "Vous pouvez tout exporter ou supprimer",
    ],
  },
  {
    emoji: "🩺",
    title: "Un outil, pas un diagnostic",
    body: "Mood-IoT ne remplace pas votre médecin. Les recommandations sont indicatives.",
    bullets: [
      "Les suggestions de l'IA sont informatives",
      "Votre psychiatre garde la décision médicale",
      "En cas d'urgence, contactez le 112",
    ],
  },
];

const { width } = Dimensions.get("window");
const ONBOARDING_DONE_KEY = "onboarding_seen_v1";

export default function OnboardingScreen() {
  const [index, setIndex] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const insets = useSafeAreaInsets();

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const i = Math.round(e.nativeEvent.contentOffset.x / width);
    if (i !== index) setIndex(i);
  };

  const goNext = () => {
    if (index < SLIDES.length - 1) {
      scrollRef.current?.scrollTo({ x: width * (index + 1), animated: true });
      setIndex(index + 1);
    } else {
      void finish();
    }
  };

  const finish = async () => {
    await SecureStore.setItemAsync(ONBOARDING_DONE_KEY, "true");
    router.replace("/(auth)/login");
  };

  return (
    <View
      style={[
        styles.container,
        { paddingTop: insets.top },
      ]}
    >
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
      >
        {SLIDES.map((slide, idx) => (
          <View key={idx} style={[styles.slide, { width }]}>
            <Text style={styles.emoji}>{slide.emoji}</Text>
            <Text style={styles.title}>{slide.title}</Text>
            <Text style={styles.body}>{slide.body}</Text>
            {slide.bullets ? (
              <View style={styles.bullets}>
                {slide.bullets.map((b, i) => (
                  <View key={i} style={styles.bulletRow}>
                    <Text style={styles.bulletDot}>•</Text>
                    <Text style={styles.bulletText}>{b}</Text>
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        ))}
      </ScrollView>

      {/* Indicateurs de page */}
      <View style={styles.dots}>
        {SLIDES.map((_, i) => (
          <View
            key={i}
            style={[styles.dot, i === index && styles.dotActive]}
          />
        ))}
      </View>

      {/* Actions */}
      <View
        style={[
          styles.actions,
          { paddingBottom: Math.max(insets.bottom + space.md, space["3xl"]) },
        ]}
      >
        <Pressable
          onPress={() => void finish()}
          style={styles.skipBtn}
          accessibilityRole="button"
          accessibilityLabel="Passer l'onboarding"
        >
          <Text style={styles.skipText}>Passer</Text>
        </Pressable>
        <Pressable
          onPress={goNext}
          style={styles.nextBtn}
          accessibilityRole="button"
          accessibilityLabel={
            index === SLIDES.length - 1 ? "Commencer" : "Suivant"
          }
        >
          <Text style={styles.nextText}>
            {index === SLIDES.length - 1 ? "Commencer" : "Suivant"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

export async function hasSeenOnboarding(): Promise<boolean> {
  try {
    return (await SecureStore.getItemAsync(ONBOARDING_DONE_KEY)) === "true";
  } catch {
    return false;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: light.bg },
  slide: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: space["2xl"],
  },
  emoji: { fontSize: 80, marginBottom: space["2xl"] },
  title: {
    fontSize: font.size["3xl"],
    fontWeight: font.weight.bold,
    color: light.text,
    textAlign: "center",
    marginBottom: space.md,
  },
  body: {
    fontSize: font.size.base,
    color: light.textMuted,
    textAlign: "center",
    lineHeight: font.size.base * font.lineHeight.relaxed,
    marginBottom: space.xl,
    maxWidth: 320,
  },
  bullets: { gap: space.sm, alignSelf: "stretch", paddingHorizontal: space.lg },
  bulletRow: { flexDirection: "row", gap: space.sm, alignItems: "flex-start" },
  bulletDot: { color: palette.primary500, fontSize: 18, lineHeight: 22 },
  bulletText: { flex: 1, fontSize: font.size.sm, color: light.text, lineHeight: 20 },

  dots: {
    flexDirection: "row",
    justifyContent: "center",
    gap: space.sm,
    marginBottom: space.lg,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: light.border,
  },
  dotActive: { backgroundColor: palette.primary500, width: 24 },

  actions: {
    flexDirection: "row",
    paddingHorizontal: space["2xl"],
    paddingTop: space.md,
    gap: space.md,
  },
  skipBtn: {
    flex: 1,
    height: 52,
    borderRadius: radius.lg,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "transparent",
  },
  skipText: { color: light.textMuted, fontSize: font.size.base, fontWeight: font.weight.medium },
  nextBtn: {
    flex: 2,
    height: 52,
    borderRadius: radius.lg,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: palette.primary500,
    shadowColor: palette.primary500,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  nextText: { color: "#fff", fontSize: font.size.base, fontWeight: font.weight.bold },
});
