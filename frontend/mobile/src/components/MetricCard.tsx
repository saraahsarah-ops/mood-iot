import { View, Text, StyleSheet } from "react-native";

interface Props {
  emoji: string;
  label: string;
  value: number;
  unit: string;
}

export default function MetricCard({ emoji, label, value, unit }: Props) {
  return (
    <View style={styles.card}>
      <Text style={styles.emoji}>{emoji}</Text>
      <Text style={styles.value}>
        {value}
        <Text style={styles.unit}> {unit}</Text>
      </Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    width: "47%",
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 16,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  emoji: { fontSize: 28, marginBottom: 6 },
  value: { fontSize: 22, fontWeight: "700", color: "#333" },
  unit: { fontSize: 13, fontWeight: "400", color: "#999" },
  label: { fontSize: 12, color: "#888", marginTop: 4 },
});
