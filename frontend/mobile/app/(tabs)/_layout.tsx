import { Tabs } from "expo-router";
import { Platform, Text } from "react-native";

const TAB_COLOR = "#0288d1";
const TAB_INACTIVE = "#999";

function TabIcon({ emoji }: { emoji: string }) {
  return <Text style={{ fontSize: 22 }}>{emoji}</Text>;
}

export default function TabsLayout() {
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
