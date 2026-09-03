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

const FIELDS: ReadingPoint["field"][] = ["humedad_suelo", "temp_aire", "presion"];

export default function DeviceDetailScreen({ route }: Props) {
  const { deviceId } = route.params;
  const [selectedField, setSelectedField] = useState<ReadingPoint["field"]>("humedad_suelo");

  const readingsQuery = useQuery({
    queryKey: ["readings", deviceId],
    queryFn: () => devicesApi.getReadings(deviceId, 24),
    refetchInterval: 30_000,
  });

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
      <Text style={styles.deviceId}>{deviceId}</Text>
      <Text style={styles.estado}>Estado: {readingsQuery.data?.latest_estado ?? "—"}</Text>

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

      <View style={styles.fieldSelector}>
        {FIELDS.map((field) => (
          <Pressable
            key={field}
            style={[styles.fieldButton, field === selectedField && styles.fieldButtonActive]}
            onPress={() => setSelectedField(field)}
          >
            <Text style={[styles.fieldButtonText, field === selectedField && styles.fieldButtonTextActive]}>
              {field === "humedad_suelo" ? "Suelo" : field === "temp_aire" ? "Temp" : "Presión"}
            </Text>
          </Pressable>
        ))}
      </View>

      {readingsQuery.isLoading ? (
        <ActivityIndicator style={styles.loading} />
      ) : (
        <ReadingsChart points={readingsQuery.data?.points ?? []} field={selectedField} />
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20 },
  deviceId: { fontSize: 22, fontWeight: "700" },
  estado: { fontSize: 15, color: "#666", marginTop: 4, marginBottom: 20 },
  waterButton: {
    backgroundColor: "#1565c0",
    borderRadius: 8,
    padding: 16,
    alignItems: "center",
    marginBottom: 20,
  },
  buttonDisabled: { opacity: 0.5 },
  waterButtonText: { color: "#fff", fontSize: 17, fontWeight: "700" },
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
