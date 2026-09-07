import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import * as devicesApi from "../api/devices";
import * as locationsApi from "../api/locations";
import { ApiError } from "../api/client";
import DeviceCard from "../components/DeviceCard";
import type { LocationsStackParamList } from "../navigation/LocationsStack";

type Props = NativeStackScreenProps<LocationsStackParamList, "LocationDetail">;

export default function LocationDetailScreen({ route, navigation }: Props) {
  const { locationId } = route.params;
  const queryClient = useQueryClient();
  const insets = useSafeAreaInsets();

  const [isGpsModalOpen, setGpsModalOpen] = useState(false);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");

  const [isInfoModalOpen, setInfoModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const devicesQuery = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.listDevices,
  });

  const locationQuery = useQuery({
    queryKey: ["location", locationId],
    queryFn: () => locationsApi.getLocation(locationId),
  });

  function openInfoModal() {
    setName(locationQuery.data?.name ?? "");
    setDescription(locationQuery.data?.description ?? "");
    setInfoModalOpen(true);
  }

  const saveInfoMutation = useMutation({
    mutationFn: () =>
      locationsApi.updateLocation(locationId, {
        name: name.trim(),
        description: description.trim(),
      }),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["location", locationId] });
      queryClient.invalidateQueries({ queryKey: ["locations"] });
      navigation.setOptions({ title: updated.name });
      setInfoModalOpen(false);
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo guardar la ubicación";
      Alert.alert("Error", message);
    },
  });

  function handleSaveInfo() {
    if (!name.trim()) {
      Alert.alert("Nombre obligatorio", "La ubicación necesita un nombre.");
      return;
    }
    saveInfoMutation.mutate();
  }

  function openGpsModal() {
    setLatitude(locationQuery.data?.latitude != null ? String(locationQuery.data.latitude) : "");
    setLongitude(locationQuery.data?.longitude != null ? String(locationQuery.data.longitude) : "");
    setGpsModalOpen(true);
  }

  const saveGpsMutation = useMutation({
    mutationFn: () =>
      locationsApi.updateLocation(locationId, {
        latitude: Number(latitude),
        longitude: Number(longitude),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["location", locationId] });
      setGpsModalOpen(false);
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

  const hasGps = locationQuery.data?.latitude != null && locationQuery.data?.longitude != null;
  const devicesHere = (devicesQuery.data ?? []).filter((d) => d.location_id === locationId);

  return (
    <View style={styles.container}>
      <FlatList
        data={devicesHere}
        keyExtractor={(item) => item.device_id}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          <>
          <Pressable style={styles.gpsRow} onPress={openInfoModal}>
            <Text style={styles.gpsRowIcon}>✏️</Text>
            <View style={styles.gpsRowTextWrap}>
              <Text style={styles.gpsRowTitle}>Nombre y descripción</Text>
              <Text style={styles.gpsRowSubtitle}>
                {locationQuery.data?.name ?? "—"}
                {locationQuery.data?.description ? ` · ${locationQuery.data.description}` : ""}
              </Text>
            </View>
            <Text style={styles.gpsRowChevron}>›</Text>
          </Pressable>
          <Pressable style={styles.gpsRow} onPress={openGpsModal}>
            <Text style={styles.gpsRowIcon}>📍</Text>
            <View style={styles.gpsRowTextWrap}>
              <Text style={styles.gpsRowTitle}>Ubicación GPS</Text>
              <Text style={styles.gpsRowSubtitle}>
                {hasGps
                  ? `${locationQuery.data!.latitude!.toFixed(2)}, ${locationQuery.data!.longitude!.toFixed(2)}`
                  : "Sin configurar — toca para añadirla"}
              </Text>
            </View>
            <Text style={styles.gpsRowChevron}>›</Text>
          </Pressable>
          </>
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
        <Text style={styles.claimButtonText}>+ Añadir dispositivo</Text>
      </Pressable>

      <Modal visible={isGpsModalOpen} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: 20 + insets.bottom }]}>
            <Text style={styles.modalTitle}>📍 Ubicación GPS</Text>
            <Text style={styles.modalHint}>
              Solo se usa para los dispositivos marcados como exteriores, para consultar la previsión de lluvia.
              Puedes buscar "mis coordenadas" en Google Maps y copiarlas aquí.
            </Text>
            <Text style={styles.label}>Latitud</Text>
            <TextInput
              style={styles.input}
              placeholder="Ej. 40.4168"
              value={latitude}
              onChangeText={setLatitude}
              keyboardType="numeric"
            />
            <Text style={styles.label}>Longitud</Text>
            <TextInput
              style={styles.input}
              placeholder="Ej. -3.7038"
              value={longitude}
              onChangeText={setLongitude}
              keyboardType="numeric"
            />
            <View style={styles.modalActions}>
              <Pressable onPress={() => setGpsModalOpen(false)}>
                <Text style={styles.cancel}>Cancelar</Text>
              </Pressable>
              <Pressable
                style={[styles.saveButton, saveGpsMutation.isPending && styles.buttonDisabled]}
                disabled={saveGpsMutation.isPending}
                onPress={handleSaveGps}
              >
                {saveGpsMutation.isPending ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.saveButtonText}>Guardar</Text>
                )}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={isInfoModalOpen} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: 20 + insets.bottom }]}>
            <Text style={styles.modalTitle}>✏️ Nombre y descripción</Text>
            <Text style={styles.label}>Nombre</Text>
            <TextInput
              style={styles.input}
              placeholder="Ej. Mi Casa"
              value={name}
              onChangeText={setName}
            />
            <Text style={styles.label}>Descripción (opcional)</Text>
            <TextInput
              style={styles.input}
              placeholder="Ej. Novelda"
              value={description}
              onChangeText={setDescription}
            />
            <View style={styles.modalActions}>
              <Pressable onPress={() => setInfoModalOpen(false)}>
                <Text style={styles.cancel}>Cancelar</Text>
              </Pressable>
              <Pressable
                style={[styles.saveButton, saveInfoMutation.isPending && styles.buttonDisabled]}
                disabled={saveInfoMutation.isPending}
                onPress={handleSaveInfo}
              >
                {saveInfoMutation.isPending ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.saveButtonText}>Guardar</Text>
                )}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  list: { padding: 16 },
  empty: { textAlign: "center", color: "#888", marginTop: 40 },
  loading: { marginTop: 20 },
  gpsRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#f4f6f4",
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
  },
  gpsRowIcon: { fontSize: 20, marginRight: 10 },
  gpsRowTextWrap: { flex: 1 },
  gpsRowTitle: { fontSize: 14, fontWeight: "700" },
  gpsRowSubtitle: { fontSize: 12, color: "#777", marginTop: 2 },
  gpsRowChevron: { fontSize: 22, color: "#bbb", marginLeft: 8 },
  claimButton: {
    backgroundColor: "#2e7d32",
    margin: 16,
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  claimButtonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: "#fff", borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 },
  modalTitle: { fontSize: 18, fontWeight: "700", marginBottom: 6 },
  modalHint: { fontSize: 12, color: "#777", marginBottom: 14 },
  label: { fontSize: 13, fontWeight: "600", color: "#444", marginBottom: 6 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 16 },
  modalActions: { flexDirection: "row", justifyContent: "flex-end", alignItems: "center", gap: 16 },
  cancel: { color: "#666", fontSize: 16, marginRight: 8 },
  saveButton: { backgroundColor: "#2e7d32", borderRadius: 8, paddingVertical: 10, paddingHorizontal: 20 },
  buttonDisabled: { opacity: 0.5 },
  saveButtonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
