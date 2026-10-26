import { Pressable, StyleSheet, Text, View } from "react-native";
import type { DeviceOut, DeviceStatusOut } from "../types/api";
import { timeAgo } from "../utils/time";

export function statusLabel(status: DeviceStatusOut | undefined): { dot: string; text: string; color: string } | null {
  // Sin dato de estado todavia (cargando, o la consulta fallo): no se
  // enseña nada en vez de adivinar "desconectado".
  if (!status) return null;
  if (status.online) return { dot: "🟢", text: "Conectado", color: "#2e7d32" };
  if (status.last_seen_at) {
    return { dot: "🔴", text: `Sin conexión · visto ${timeAgo(status.last_seen_at)}`, color: "#c62828" };
  }
  return { dot: "🔴", text: "Sin conexión · sin datos recientes", color: "#c62828" };
}

export default function DeviceCard({
  device,
  status,
  onPress,
}: {
  device: DeviceOut;
  status?: DeviceStatusOut;
  onPress: () => void;
}) {
  const label = statusLabel(status);
  return (
    <Pressable style={styles.card} onPress={onPress}>
      <Text style={styles.title}>{device.name ?? device.device_id}</Text>
      {device.name && device.name !== device.device_id ? (
        <Text style={styles.subtitle}>{device.device_id}</Text>
      ) : null}
      {label ? (
        <View style={styles.statusRow}>
          <Text style={[styles.statusText, { color: label.color }]}>
            {label.dot} {label.text}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: "#f4f6f4", borderRadius: 10, padding: 16, marginBottom: 10 },
  title: { fontSize: 17, fontWeight: "600" },
  subtitle: { fontSize: 13, color: "#888", marginTop: 2 },
  statusRow: { marginTop: 6 },
  statusText: { fontSize: 13, fontWeight: "500" },
});
