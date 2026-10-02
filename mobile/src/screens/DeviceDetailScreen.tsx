import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import { ApiError } from "../api/client";
import ReadingsChart from "../components/ReadingsChart";
import type { LocationsStackParamList } from "../navigation/LocationsStack";
import type { ReadingPoint } from "../types/api";

type Props = NativeStackScreenProps<LocationsStackParamList, "DeviceDetail">;

type Category = "suelo" | "ambiente";

// Campos "candidatos" por categoria - no todos los dispositivos
// publican todos (depende de su sensor de ambiente: BMP280 da presion,
// DHT22 da humedad_ambiente, ninguno da los dos). Tanto el resumen como
// las graficas se filtran a lo que el dispositivo tenga de verdad, ver
// mas abajo - nunca se rellena un hueco con un 0 falso.
const FIELDS_BY_CATEGORY: Record<Category, ReadingPoint["field"][]> = {
  suelo: ["humedad_suelo", "temp_suelo"],
  ambiente: ["temp_aire", "presion", "humedad_ambiente"],
};

function formatHumedad(value: number | null): string {
  return value != null ? `${value.toFixed(0)}%` : "—";
}

const SUMMARY_BY_CATEGORY: Record<
  Category,
  { field: ReadingPoint["field"]; icon: string; decimals: number; unit: string }[]
> = {
  suelo: [
    { field: "humedad_suelo", icon: "💧", decimals: 0, unit: "%" },
    { field: "temp_suelo", icon: "🌡️", decimals: 1, unit: "°C" },
  ],
  ambiente: [
    { field: "temp_aire", icon: "🌡️", decimals: 1, unit: "°C" },
    { field: "presion", icon: "🌬️", decimals: 0, unit: " hPa" },
    { field: "humedad_ambiente", icon: "💦", decimals: 0, unit: "%" },
  ],
};

const ESTADO_LABELS: Record<string, string> = {
  SECO: "Seco",
  NECESITA_RIEGO: "Necesita riego",
  OK: "OK",
  HUMEDO: "Húmedo",
  EXCESO_AGUA: "Exceso de agua",
};

const TIME_RANGES: { label: string; hours: number }[] = [
  { label: "2h", hours: 2 },
  { label: "6h", hours: 6 },
  { label: "24h", hours: 24 },
  { label: "2d", hours: 48 },
  { label: "7d", hours: 168 },
];

export default function DeviceDetailScreen({ route, navigation }: Props) {
  const { deviceId } = route.params;
  const queryClient = useQueryClient();
  const [selectedCategory, setSelectedCategory] = useState<Category>("suelo");
  const [selectedHours, setSelectedHours] = useState(24);

  const deviceQuery = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => devicesApi.getDevice(deviceId),
    // Corto para que el aviso de "sensor pausado" desaparezca solo en
    // cuanto expira (autoexpira por timestamp en el backend, ver
    // pause-sensor/resume-sensor), sin que haga falta reabrir la pantalla.
    refetchInterval: 15_000,
  });

  const pausadoHasta = deviceQuery.data?.sensor_pausado_hasta
    ? new Date(deviceQuery.data.sensor_pausado_hasta)
    : null;
  const sensorPausado = pausadoHasta != null && pausadoHasta.getTime() > Date.now();

  const pauseMutation = useMutation({
    mutationFn: () => devicesApi.pauseSensor(deviceId),
    onSuccess: (data) => queryClient.setQueryData(["device", deviceId], data),
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo pausar el sensor";
      Alert.alert("Error", message);
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => devicesApi.resumeSensor(deviceId),
    onSuccess: (data) => queryClient.setQueryData(["device", deviceId], data),
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo reanudar el sensor";
      Alert.alert("Error", message);
    },
  });

  const readingsQuery = useQuery({
    queryKey: ["readings", deviceId, selectedHours],
    queryFn: () => devicesApi.getReadings(deviceId, selectedHours),
    refetchInterval: 30_000,
  });

  // /readings agrega a 1m/10m/1h segun el rango (ver influx_client.py) -
  // de sobra para las graficas, pero "el ultimo punto" de ahi puede
  // tardar hasta 10 minutos en reflejar un cambio real, lo cual se nota
  // mucho mientras se mueve el sensor a mano. La fila-resumen y el
  // banner de pausa usan en su lugar /latest-readings (sin agregar),
  // refrescado mucho mas rapido mientras el sensor esta pausado.
  const latestQuery = useQuery({
    queryKey: ["latest-readings", deviceId],
    queryFn: () => devicesApi.getLatestReadings(deviceId),
    refetchInterval: sensorPausado ? 3_000 : 15_000,
  });

  const points = readingsQuery.data?.points ?? [];
  // Solo se muestra lo que el dispositivo publica de verdad (ver el
  // porque en FIELDS_BY_CATEGORY, arriba) - un campo sin dato se oculta
  // del todo en vez de enseñar un "—" permanente, que acabaria leyendose
  // como "sensor roto" en un dispositivo que simplemente no lo tiene.
  const summaryItems = SUMMARY_BY_CATEGORY[selectedCategory]
    .map((item) => ({ ...item, value: latestQuery.data?.[item.field] ?? null }))
    .filter((item) => item.value != null);
  const chartFields = FIELDS_BY_CATEGORY[selectedCategory].filter((field) =>
    points.some((p) => p.field === field)
  );

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
      <Text style={styles.estado}>
        Estado: {ESTADO_LABELS[readingsQuery.data?.latest_estado ?? ""] ?? "—"}
      </Text>

      {sensorPausado ? (
        <View style={styles.pauseBanner}>
          <Text style={styles.pauseBannerTitle}>
            ⏸️ Sensor pausado — humedad ahora: {formatHumedad(latestQuery.data?.humedad_suelo ?? null)}
          </Text>
          <Text style={styles.pauseBannerSubtitle}>
            El riego automático no se activará hasta las{" "}
            {pausadoHasta?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}. Mueve el
            sensor o la planta con calma.
          </Text>
          <Pressable
            style={[styles.resumeButton, resumeMutation.isPending && styles.buttonDisabled]}
            disabled={resumeMutation.isPending}
            onPress={() => resumeMutation.mutate()}
          >
            {resumeMutation.isPending ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.resumeButtonText}>✅ Ya está, reanudar</Text>
            )}
          </Pressable>
        </View>
      ) : (
        <Pressable
          style={[styles.pauseButton, pauseMutation.isPending && styles.buttonDisabled]}
          disabled={pauseMutation.isPending}
          onPress={() => pauseMutation.mutate()}
        >
          {pauseMutation.isPending ? (
            <ActivityIndicator color="#1565c0" />
          ) : (
            <Text style={styles.pauseButtonText}>⏸️ Pausar sensor (10 min) para moverlo</Text>
          )}
        </Pressable>
      )}

      <View style={styles.summaryRow}>
        {summaryItems.map((item) => (
          <Text key={item.field} style={styles.summaryItem}>
            {item.icon} {item.value!.toFixed(item.decimals)}{item.unit}
          </Text>
        ))}
      </View>

      <Pressable
        style={styles.configButton}
        onPress={() => navigation.navigate("DeviceConfig", { deviceId })}
      >
        <Text style={styles.configButtonText}>⚙️ Configuración</Text>
      </Pressable>

      <Pressable
        style={styles.configButton}
        onPress={() => navigation.navigate("DeviceHealth", { deviceId })}
      >
        <Text style={styles.configButtonText}>🩺 Salud de la planta</Text>
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
        chartFields.map((field) => (
          <ReadingsChart key={field} points={points} field={field} hours={selectedHours} />
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
  pauseButton: {
    borderWidth: 1,
    borderColor: "#1565c0",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
    marginBottom: 20,
  },
  pauseButtonText: { color: "#1565c0", fontSize: 15, fontWeight: "600" },
  pauseBanner: {
    backgroundColor: "#fff8e1",
    borderWidth: 1,
    borderColor: "#f9a825",
    borderRadius: 10,
    padding: 14,
    marginBottom: 20,
  },
  pauseBannerTitle: { fontSize: 16, fontWeight: "700", color: "#7a5c00", marginBottom: 4 },
  pauseBannerSubtitle: { fontSize: 13, color: "#8a6d00", lineHeight: 18, marginBottom: 10 },
  resumeButton: {
    backgroundColor: "#f9a825",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  resumeButtonText: { color: "#fff", fontSize: 15, fontWeight: "700" },
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
