import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import { ApiError } from "../api/client";
import ReadingsChart from "../components/ReadingsChart";
import type { LocationsStackParamList } from "../navigation/LocationsStack";
import type { ReadingPoint } from "../types/api";

type Props = NativeStackScreenProps<LocationsStackParamList, "DeviceDetail">;

type Category = "suelo" | "ambiente";

const FIELDS_BY_CATEGORY: Record<Category, ReadingPoint["field"][]> = {
  suelo: ["humedad_suelo", "temp_suelo"],
  ambiente: ["temp_aire", "presion"],
};

function latestValue(points: ReadingPoint[], field: ReadingPoint["field"]): number | null {
  const fieldPoints = points.filter((p) => p.field === field);
  if (fieldPoints.length === 0) return null;
  return fieldPoints.reduce((latest, p) => (p.time > latest.time ? p : latest)).value;
}

const TIME_RANGES: { label: string; hours: number }[] = [
  { label: "2h", hours: 2 },
  { label: "6h", hours: 6 },
  { label: "24h", hours: 24 },
  { label: "2d", hours: 48 },
  { label: "7d", hours: 168 },
];

export default function DeviceDetailScreen({ route, navigation }: Props) {
  const { deviceId } = route.params;
  const [selectedCategory, setSelectedCategory] = useState<Category>("suelo");
  const [selectedHours, setSelectedHours] = useState(24);

  const deviceQuery = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => devicesApi.getDevice(deviceId),
  });

  const readingsQuery = useQuery({
    queryKey: ["readings", deviceId, selectedHours],
    queryFn: () => devicesApi.getReadings(deviceId, selectedHours),
    refetchInterval: 30_000,
  });

  const latestHumedad = latestValue(readingsQuery.data?.points ?? [], "humedad_suelo");
  const latestTempSuelo = latestValue(readingsQuery.data?.points ?? [], "temp_suelo");

  const waterMutation = useMutation({
    mutationFn: () => devicesApi.waterDevice(deviceId),
    onSuccess: () => Alert.alert("Riego enviado", "El comando de riego se ha enviado al dispositivo."),
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo enviar el comando de riego";
      Alert.alert("Error", message);
    },
  });

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.deviceId}>{deviceQuery.data?.name ?? deviceId}</Text>
      {deviceQuery.data?.name && deviceQuery.data.name !== deviceId ? (
        <Text style={styles.deviceIdSubtitle}>{deviceId}</Text>
      ) : null}
      <Text style={styles.estado}>Estado: {readingsQuery.data?.latest_estado ?? "—"}</Text>

      {latestHumedad != null || latestTempSuelo != null ? (
        <View style={styles.summaryRow}>
          <Text style={styles.summaryItem}>
            💧 {latestHumedad != null ? `${Math.round(latestHumedad)}%` : "—"}
          </Text>
          <Text style={styles.summaryItem}>
            🌡️ {latestTempSuelo != null ? `${latestTempSuelo.toFixed(1)}°C` : "—"}
          </Text>
        </View>
      ) : null}

      <Pressable
        style={styles.configButton}
        onPress={() => navigation.navigate("DeviceConfig", { deviceId })}
      >
        <Text style={styles.configButtonText}>⚙️ Configuración</Text>
      </Pressable>

      <Pressable
        style={[styles.waterButton, waterMutation.isPending && styles.buttonDisabled]}
        disabled={waterMutation.isPending}
        onPress={() => waterMutation.mutate()}
      >
        {waterMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.waterButtonText}>💧 Regar ahora</Text>
        )}
      </Pressable>

      <View style={styles.rangeSelector}>
        {TIME_RANGES.map((range) => (
          <Pressable
            key={range.hours}
            style={[styles.rangeButton, selectedHours === range.hours && styles.rangeButtonActive]}
            onPress={() => setSelectedHours(range.hours)}
          >
            <Text style={[styles.rangeButtonText, selectedHours === range.hours && styles.rangeButtonTextActive]}>
              {range.label}
            </Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.fieldSelector}>
        {(["suelo", "ambiente"] as Category[]).map((category) => (
          <Pressable
            key={category}
            style={[styles.fieldButton, category === selectedCategory && styles.fieldButtonActive]}
            onPress={() => setSelectedCategory(category)}
          >
            <Text style={[styles.fieldButtonText, category === selectedCategory && styles.fieldButtonTextActive]}>
              {category === "suelo" ? "🌱 Suelo" : "🌤️ Ambiente"}
            </Text>
          </Pressable>
        ))}
      </View>

      {readingsQuery.isLoading ? (
        <ActivityIndicator style={styles.loading} />
      ) : (
        FIELDS_BY_CATEGORY[selectedCategory].map((field) => (
          <ReadingsChart key={field} points={readingsQuery.data?.points ?? []} field={field} />
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20 },
  deviceId: { fontSize: 22, fontWeight: "700" },
  deviceIdSubtitle: { fontSize: 13, color: "#888", marginTop: 2 },
  estado: { fontSize: 15, color: "#666", marginTop: 4, marginBottom: 12 },
  summaryRow: { flexDirection: "row", gap: 20, marginBottom: 20 },
  summaryItem: { fontSize: 17, fontWeight: "600", color: "#333" },
  waterButton: {
    backgroundColor: "#1565c0",
    borderRadius: 8,
    padding: 16,
    alignItems: "center",
    marginBottom: 20,
  },
  buttonDisabled: { opacity: 0.5 },
  waterButtonText: { color: "#fff", fontSize: 17, fontWeight: "700" },
  configButton: {
    borderWidth: 1,
    borderColor: "#2e7d32",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
    marginBottom: 12,
  },
  configButtonText: { color: "#2e7d32", fontSize: 15, fontWeight: "600" },
  rangeSelector: { flexDirection: "row", gap: 6, marginBottom: 12 },
  rangeButton: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 16,
    backgroundColor: "#f0f0f0",
  },
  rangeButtonActive: { backgroundColor: "#2e7d32" },
  rangeButtonText: { color: "#555", fontWeight: "600", fontSize: 13 },
  rangeButtonTextActive: { color: "#fff" },
  fieldSelector: { flexDirection: "row", gap: 8, marginBottom: 8 },
  fieldButton: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: "#f0f0f0",
    alignItems: "center",
  },
  fieldButtonActive: { backgroundColor: "#2e7d32" },
  fieldButtonText: { color: "#333", fontWeight: "600" },
  fieldButtonTextActive: { color: "#fff" },
  loading: { marginTop: 40 },
});
