import { Tabs } from "expo-router";
import { Platform, Text, View } from "react-native";
import { useEffect } from "react";
import { useMessagesStore } from "@/stores/messagesStore";

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
  useEffect(() => {
    void refreshUnread();
    const id = setInterval(() => void refreshUnread(), 60000);
    return () => clearInterval(id);
  }, [refreshUnread]);

  return (
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
    </Tabs>
  );
}
