import { Pressable, StyleSheet, Text, View } from "react-native";
import type { DeviceOut } from "../types/api";

export default function DeviceCard({ device, onPress }: { device: DeviceOut; onPress: () => void }) {
  return (
    <Pressable style={styles.card} onPress={onPress}>
      <Text style={styles.title}>{device.name ?? device.device_id}</Text>
      <Text style={styles.subtitle}>{device.device_id}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: "#f4f6f4", borderRadius: 10, padding: 16, marginBottom: 10 },
  title: { fontSize: 17, fontWeight: "600" },
  subtitle: { fontSize: 13, color: "#888", marginTop: 2 },
});
