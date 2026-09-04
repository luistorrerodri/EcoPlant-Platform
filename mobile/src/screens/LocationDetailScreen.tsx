import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import * as locationsApi from "../api/locations";
import { ApiError } from "../api/client";
import DeviceCard from "../components/DeviceCard";
import type { LocationsStackParamList } from "../navigation/LocationsStack";

type Props = NativeStackScreenProps<LocationsStackParamList, "LocationDetail">;

export default function LocationDetailScreen({ route, navigation }: Props) {
  const { locationId } = route.params;
  const queryClient = useQueryClient();

  const [isGpsInitialized, setGpsInitialized] = useState(false);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");

  const devicesQuery = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.listDevices,
  });

  const locationQuery = useQuery({
    queryKey: ["location", locationId],
    queryFn: () => locationsApi.getLocation(locationId),
  });

  useEffect(() => {
    if (isGpsInitialized || !locationQuery.data) return;
    setLatitude(locationQuery.data.latitude != null ? String(locationQuery.data.latitude) : "");
    setLongitude(locationQuery.data.longitude != null ? String(locationQuery.data.longitude) : "");
    setGpsInitialized(true);
  }, [isGpsInitialized, locationQuery.data]);

  const saveGpsMutation = useMutation({
    mutationFn: () =>
      locationsApi.updateLocation(locationId, {
        latitude: Number(latitude),
        longitude: Number(longitude),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["location", locationId] });
      Alert.alert("Guardado", "Ubicación GPS actualizada.");
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo guardar la ubicación";
      Alert.alert("Error", message);
    },
  });

  function handleSaveGps() {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      Alert.alert("Valor inválido", "La latitud debe ser un número entre -90 y 90.");
      return;
    }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      Alert.alert("Valor inválido", "La longitud debe ser un número entre -180 y 180.");
      return;
    }
    saveGpsMutation.mutate();
  }

  const devicesHere = (devicesQuery.data ?? []).filter((d) => d.location_id === locationId);

  return (
    <View style={styles.container}>
      <FlatList
        data={devicesHere}
        keyExtractor={(item) => item.device_id}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          <View style={styles.gpsCard}>
            <Text style={styles.gpsTitle}>📍 Ubicación GPS</Text>
            <Text style={styles.gpsHint}>
              Solo se usa para los dispositivos marcados como exteriores (previsión de lluvia).
            </Text>
            <TextInput
              style={styles.input}
              placeholder="Latitud"
              value={latitude}
              onChangeText={setLatitude}
              keyboardType="numeric"
            />
            <TextInput
              style={styles.input}
              placeholder="Longitud"
              value={longitude}
              onChangeText={setLongitude}
              keyboardType="numeric"
            />
            <Pressable
              style={[styles.gpsSaveButton, saveGpsMutation.isPending && styles.buttonDisabled]}
              disabled={saveGpsMutation.isPending}
              onPress={handleSaveGps}
            >
              {saveGpsMutation.isPending ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.gpsSaveButtonText}>Guardar</Text>
              )}
            </Pressable>
          </View>
        }
        ListEmptyComponent={
          !devicesQuery.isLoading ? (
            <Text style={styles.empty}>Sin dispositivos aquí todavía — reclama uno.</Text>
          ) : null
        }
        renderItem={({ item }) => (
          <DeviceCard
            device={item}
            onPress={() => navigation.navigate("DeviceDetail", { deviceId: item.device_id })}
          />
        )}
      />

      {devicesQuery.isLoading ? <ActivityIndicator style={styles.loading} /> : null}

      <Pressable style={styles.claimButton} onPress={() => navigation.navigate("ClaimDevice", { locationId })}>
        <Text style={styles.claimButtonText}>+ Reclamar dispositivo</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  list: { padding: 16 },
  empty: { textAlign: "center", color: "#888", marginTop: 40 },
  loading: { marginTop: 20 },
  gpsCard: {
    backgroundColor: "#f4f6f4",
    borderRadius: 10,
    padding: 16,
    marginBottom: 16,
  },
  gpsTitle: { fontSize: 15, fontWeight: "700", marginBottom: 4 },
  gpsHint: { fontSize: 12, color: "#777", marginBottom: 12 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10, marginBottom: 8, fontSize: 15 },
  gpsSaveButton: { backgroundColor: "#2e7d32", borderRadius: 8, paddingVertical: 10, alignItems: "center" },
  buttonDisabled: { opacity: 0.5 },
  gpsSaveButtonText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  claimButton: {
    backgroundColor: "#2e7d32",
    margin: 16,
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  claimButtonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
