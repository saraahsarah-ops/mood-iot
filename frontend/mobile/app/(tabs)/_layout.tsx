import { Tabs } from "expo-router";
import { Platform, Text, View, Alert } from "react-native";
import { useEffect, useState } from "react";
import { useMessagesStore } from "@/stores/messagesStore";
import { useAuthStore } from "@/stores/authStore";
import {
  ConsentModal,
  type ConsentValues,
} from "@/components/ConsentModal";
import { fetchMyConsents, updateMyConsents } from "@/services/api";

const TAB_COLOR = "#0288d1";
const TAB_INACTIVE = "#999";

function TabIcon({ emoji }: { emoji: string }) {
  return <Text style={{ fontSize: 22 }}>{emoji}</Text>;
}

function MessagesIcon() {
  const unread = useMessagesStore((s) => s.unreadCount);
  return (
    <View>
      <Text style={{ fontSize: 22 }}>💬</Text>
      {unread > 0 ? (
        <View
          style={{
            position: "absolute",
            top: -3,
            right: -8,
            minWidth: 16,
            height: 16,
            borderRadius: 8,
            paddingHorizontal: 4,
            backgroundColor: "#e74c3c",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <Text style={{ color: "#fff", fontSize: 10, fontWeight: "700" }}>
            {unread > 99 ? "99+" : unread}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

export default function TabsLayout() {
  // Charge le compteur de messages non lus au demarrage et toutes les 60s
  const refreshUnread = useMessagesStore((s) => s.refreshUnreadCount);
  const signOut = useAuthStore((s) => s.signOut);

  // Vérification du consentement RGPD/CGU à la 1re ouverture des tabs.
  // Si l'utilisateur n'a jamais accepté → modal bloquante.
  const [consentVisible, setConsentVisible] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const c = await fetchMyConsents();
        if (!cancelled && !(c.cgu && c.rgpd)) {
          setConsentVisible(true);
        }
      } catch {
        // En cas d'erreur réseau, on laisse passer — la prochaine ouverture
        // re-vérifiera. Pas bloquant pour éviter de coincer un user offline.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onConsentAccept = async (values: ConsentValues) => {
    try {
      await updateMyConsents({
        cgu: values.cgu,
        rgpd: values.rgpd,
        health_sensors: values.healthSensors,
        ai_recommendations: values.aiRecommendations,
      });
      setConsentVisible(false);
    } catch {
      Alert.alert(
        "Erreur",
        "Impossible d'enregistrer les consentements. Réessayez plus tard.",
      );
    }
  };

  const onConsentDecline = () => {
    Alert.alert(
      "Mood-IoT ne peut pas fonctionner sans consentement",
      "Les conditions générales et la politique RGPD sont obligatoires pour utiliser l'application.",
      [
        { text: "Revenir", style: "cancel" },
        {
          text: "Se déconnecter",
          style: "destructive",
          onPress: () => void signOut(),
        },
      ],
    );
  };

  useEffect(() => {
    void refreshUnread();
    const id = setInterval(() => void refreshUnread(), 60000);
    return () => clearInterval(id);
  }, [refreshUnread]);

  return (
    <>
      <ConsentModal
        visible={consentVisible}
        onAccept={onConsentAccept}
        onDecline={onConsentDecline}
      />
      <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: "#fff" },
        headerTitleStyle: { fontWeight: "600", color: "#333" },
        tabBarActiveTintColor: TAB_COLOR,
        tabBarInactiveTintColor: TAB_INACTIVE,
        tabBarStyle: {
          backgroundColor: "#fff",
          borderTopWidth: 0.5,
          borderTopColor: "#e0e0e0",
          paddingBottom: Platform.OS === "ios" ? 20 : 8,
          height: Platform.OS === "ios" ? 85 : 65,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "500" },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Accueil",
          tabBarIcon: () => <TabIcon emoji="🏠" />,
          headerTitle: "Mood-IoT",
        }}
      />
      <Tabs.Screen
        name="mood"
        options={{
          title: "Humeur",
          tabBarIcon: () => <TabIcon emoji="😊" />,
          headerTitle: "Mon humeur",
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: "Historique",
          tabBarIcon: () => <TabIcon emoji="📊" />,
          headerTitle: "Mon historique",
        }}
      />
      <Tabs.Screen
        name="messages"
        options={{
          title: "Messages",
          tabBarIcon: () => <MessagesIcon />,
          headerTitle: "Messages",
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Reglages",
          tabBarIcon: () => <TabIcon emoji="⚙️" />,
          headerTitle: "Reglages",
        }}
      />
      {/* Sous-écran réglages → masqué de la tab bar */}
      <Tabs.Screen
        name="notifications-settings"
        options={{
          href: null,
          headerTitle: "Notifications",
        }}
      />
      </Tabs>
    </>
  );
}
