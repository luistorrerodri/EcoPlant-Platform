import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import * as devicesApi from "../api/devices";
import * as plantTypesApi from "../api/plantTypes";
import { ApiError } from "../api/client";
import type { LocationsStackParamList } from "../navigation/LocationsStack";
import type { DeviceEnvironment, PlantTypeOut } from "../types/api";

type Props = NativeStackScreenProps<LocationsStackParamList, "DeviceConfig">;

export default function DeviceConfigScreen({ route, navigation }: Props) {
  const { deviceId } = route.params;
  const queryClient = useQueryClient();
  const insets = useSafeAreaInsets();

  const [isInitialized, setIsInitialized] = useState(false);
  const [isPickerOpen, setPickerOpen] = useState(false);
  const [name, setName] = useState("");
  const [plantTypeId, setPlantTypeId] = useState<string | null>(null);
  const [humedadMin, setHumedadMin] = useState("");
  const [horaInicio, setHoraInicio] = useState("");
  const [horaFin, setHoraFin] = useState("");
  const [environment, setEnvironment] = useState<DeviceEnvironment | null>(null);

  const deviceQuery = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => devicesApi.getDevice(deviceId),
  });

  const plantTypesQuery = useQuery({
    queryKey: ["plant-types"],
    queryFn: plantTypesApi.listPlantTypes,
  });

  useEffect(() => {
    if (isInitialized || !deviceQuery.data) return;
    setName(deviceQuery.data.name ?? "");
    setPlantTypeId(deviceQuery.data.plant_type_id);
    setHumedadMin(String(deviceQuery.data.humedad_min));
    setHoraInicio(String(deviceQuery.data.hora_inicio));
    setHoraFin(String(deviceQuery.data.hora_fin));
    setEnvironment(deviceQuery.data.environment);
    setIsInitialized(true);
  }, [isInitialized, deviceQuery.data]);

  const selectedPlantType = plantTypesQuery.data?.find((p) => p.id === plantTypeId);

  function selectPlantType(plantType: PlantTypeOut) {
    setPlantTypeId(plantType.id);
    setHumedadMin(String(plantType.default_humedad_min));
    setHoraInicio(String(plantType.default_hora_inicio));
    setHoraFin(String(plantType.default_hora_fin));
    setPickerOpen(false);
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      devicesApi.updateDeviceConfig(deviceId, {
        name: name.trim() || deviceId,
        plant_type_id: plantTypeId,
        humedad_min: Number(humedadMin),
        hora_inicio: Number(horaInicio),
        hora_fin: Number(horaFin),
        ...(environment ? { environment } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["device", deviceId] });
      Alert.alert("Guardado", "Configuración actualizada. Node-RED la recogerá en menos de un minuto.");
      navigation.goBack();
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo guardar la configuración";
      Alert.alert("Error", message);
    },
  });

  function handleSave() {
    const humedad = Number(humedadMin);
    const inicio = Number(horaInicio);
    const fin = Number(horaFin);
    if (!Number.isInteger(humedad) || humedad < 0 || humedad > 100) {
      Alert.alert("Valor inválido", "La humedad mínima debe ser un número entre 0 y 100.");
      return;
    }
    if (!Number.isInteger(inicio) || inicio < 0 || inicio > 23 || !Number.isInteger(fin) || fin < 0 || fin > 23) {
      Alert.alert("Valor inválido", "Las horas deben ser números entre 0 y 23.");
      return;
    }
    saveMutation.mutate();
  }

  if (deviceQuery.isLoading) {
    return <ActivityIndicator style={styles.loading} />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={[styles.label, { marginTop: 0 }]}>Nombre de la planta</Text>
      <TextInput style={styles.input} placeholder="Ej. Amapola, Gardenia..." value={name} onChangeText={setName} />

      <Text style={styles.label}>Ubicación de la planta</Text>
      <View style={styles.envSelector}>
        {(["interior", "exterior"] as DeviceEnvironment[]).map((option) => (
          <Pressable
            key={option}
            style={[styles.envButton, environment === option && styles.envButtonActive]}
            onPress={() => setEnvironment(option)}
          >
            <Text style={[styles.envButtonText, environment === option && styles.envButtonTextActive]}>
              {option === "interior" ? "🏠 Interior" : "🌤️ Exterior"}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={styles.label}>Tipo de planta</Text>
      <Pressable style={styles.selector} onPress={() => setPickerOpen(true)}>
        <Text style={styles.selectorText}>{selectedPlantType?.name ?? "Sin tipo / personalizado"}</Text>
      </Pressable>

      <Text style={styles.label}>Humedad mínima de suelo (%)</Text>
      <TextInput
        style={styles.input}
        value={humedadMin}
        onChangeText={setHumedadMin}
        keyboardType="numeric"
        maxLength={3}
      />

      <Text style={styles.label}>Hora de inicio del riego permitido</Text>
      <TextInput
        style={styles.input}
        value={horaInicio}
        onChangeText={setHoraInicio}
        keyboardType="numeric"
        maxLength={2}
      />

      <Text style={styles.label}>Hora de fin del riego permitido</Text>
      <TextInput style={styles.input} value={horaFin} onChangeText={setHoraFin} keyboardType="numeric" maxLength={2} />

      <Pressable
        style={[styles.saveButton, saveMutation.isPending && styles.buttonDisabled]}
        disabled={saveMutation.isPending}
        onPress={handleSave}
      >
        {saveMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.saveButtonText}>Guardar</Text>
        )}
      </Pressable>

      <Modal visible={isPickerOpen} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, { paddingBottom: 20 + insets.bottom }]}>
            <Text style={styles.modalTitle}>Elegir tipo de planta</Text>
            <FlatList
              data={plantTypesQuery.data ?? []}
              keyExtractor={(item) => item.id}
              style={styles.modalList}
              renderItem={({ item }) => (
                <Pressable style={styles.plantTypeRow} onPress={() => selectPlantType(item)}>
                  <Text style={styles.plantTypeRowText}>{item.name}</Text>
                </Pressable>
              )}
            />
            <Pressable onPress={() => setPickerOpen(false)}>
              <Text style={styles.cancel}>Cancelar</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20 },
  loading: { marginTop: 40 },
  label: { fontSize: 14, fontWeight: "600", color: "#444", marginBottom: 6, marginTop: 16 },
  selector: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12 },
  selectorText: { fontSize: 16 },
  envSelector: { flexDirection: "row", gap: 8 },
  envButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: "#f0f0f0",
    alignItems: "center",
  },
  envButtonActive: { backgroundColor: "#2e7d32" },
  envButtonText: { color: "#333", fontWeight: "600" },
  envButtonTextActive: { color: "#fff" },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12, fontSize: 16 },
  saveButton: {
    backgroundColor: "#2e7d32",
    borderRadius: 8,
    padding: 16,
    alignItems: "center",
    marginTop: 28,
  },
  buttonDisabled: { opacity: 0.5 },
  saveButtonText: { color: "#fff", fontSize: 17, fontWeight: "700" },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: "#fff", borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20, maxHeight: "70%" },
  modalTitle: { fontSize: 18, fontWeight: "700", marginBottom: 12 },
  modalList: { marginBottom: 12 },
  plantTypeRow: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: "#eee" },
  plantTypeRowText: { fontSize: 16 },
  cancel: { color: "#666", fontSize: 16, textAlign: "center", paddingVertical: 8 },
});
