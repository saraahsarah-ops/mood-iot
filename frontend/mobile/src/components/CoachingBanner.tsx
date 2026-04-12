import { View, Text, StyleSheet } from "react-native";

interface Props {
  message: string;
}

export default function CoachingBanner({ message }: Props) {
  return (
    <View style={styles.banner}>
      <Text style={styles.icon}>🤖</Text>
      <View style={styles.textContainer}>
        <Text style={styles.title}>Conseil du jour</Text>
        <Text style={styles.message}>{message}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: "row",
    backgroundColor: "#e3f2fd",
    borderRadius: 14,
    padding: 16,
    gap: 12,
    alignItems: "flex-start",
    marginTop: 16,
  },
  icon: { fontSize: 28 },
  textContainer: { flex: 1 },
  title: { fontSize: 13, fontWeight: "600", color: "#0288d1", marginBottom: 4 },
  message: { fontSize: 14, color: "#444", lineHeight: 20 },
});
