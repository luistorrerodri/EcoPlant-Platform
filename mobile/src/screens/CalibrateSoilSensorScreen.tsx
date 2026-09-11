import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import { ApiError } from "../api/client";
import type { LocationsStackParamList } from "../navigation/LocationsStack";

type Props = NativeStackScreenProps<LocationsStackParamList, "CalibrateSoilSensor">;

export default function CalibrateSoilSensorScreen({ route }: Props) {
  const { deviceId } = route.params;
  const queryClient = useQueryClient();

  const deviceQuery = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => devicesApi.getDevice(deviceId),
  });

  function handleError(err: unknown) {
    const message = err instanceof ApiError ? err.detail : "No se pudo calibrar el sensor";
    Alert.alert("Error", message);
  }

  function handleSuccess(punto: string) {
    queryClient.invalidateQueries({ queryKey: ["device", deviceId] });
    Alert.alert("Calibrado", `Punto "${punto}" guardado y enviado al dispositivo.`);
  }

  const secoMutation = useMutation({
    mutationFn: () => devicesApi.calibrateDevice(deviceId, "seco"),
    onSuccess: () => handleSuccess("seco"),
    onError: handleError,
  });

  const humedoMutation = useMutation({
    mutationFn: () => devicesApi.calibrateDevice(deviceId, "humedo"),
    onSuccess: () => handleSuccess("húmedo"),
    onError: handleError,
  });

  if (deviceQuery.isLoading) {
    return <ActivityIndicator style={styles.loading} />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.intro}>
        Si el sensor de humedad de suelo ya no marca bien (sensor nuevo, sustrato distinto, desgaste),
        puedes recalibrarlo aquí sin reflashear el dispositivo.
      </Text>

      <View style={styles.currentBox}>
        <Text style={styles.currentLabel}>Valores actuales (lectura cruda del sensor)</Text>
        <Text style={styles.currentValue}>Seco: {deviceQuery.data?.soil_dry_raw}</Text>
        <Text style={styles.currentValue}>Húmedo: {deviceQuery.data?.soil_wet_raw}</Text>
      </View>

      <View style={styles.step}>
        <Text style={styles.stepText}>
          1. Saca el sensor de la tierra y déjalo secar al aire unos segundos. Luego pulsa:
        </Text>
        <Pressable
          style={[styles.button, secoMutation.isPending && styles.buttonDisabled]}
          disabled={secoMutation.isPending}
          onPress={() => secoMutation.mutate()}
        >
          {secoMutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>🌵 Medir seco</Text>
          )}
        </Pressable>
      </View>

      <View style={styles.step}>
        <Text style={styles.stepText}>2. Sumerge la punta del sensor en agua (o tierra muy húmeda). Luego pulsa:</Text>
        <Pressable
          style={[styles.button, humedoMutation.isPending && styles.buttonDisabled]}
          disabled={humedoMutation.isPending}
          onPress={() => humedoMutation.mutate()}
        >
          {humedoMutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>💧 Medir húmedo</Text>
          )}
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20 },
  loading: { marginTop: 40 },
  intro: { fontSize: 15, color: "#444", lineHeight: 21, marginBottom: 20 },
  currentBox: { backgroundColor: "#f4f6f4", borderRadius: 10, padding: 14, marginBottom: 24 },
  currentLabel: { fontSize: 12, color: "#777", marginBottom: 6 },
  currentValue: { fontSize: 15, fontWeight: "600", color: "#2e7d32" },
  step: { marginBottom: 24 },
  stepText: { fontSize: 14, color: "#444", marginBottom: 10, lineHeight: 20 },
  button: {
    backgroundColor: "#2e7d32",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
