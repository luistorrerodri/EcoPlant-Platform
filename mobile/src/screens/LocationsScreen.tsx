import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as locationsApi from "../api/locations";
import { ApiError } from "../api/client";
import type { LocationsStackParamList } from "../navigation/LocationsStack";

type Props = NativeStackScreenProps<LocationsStackParamList, "Locations">;

export default function LocationsScreen({ navigation }: Props) {
  const queryClient = useQueryClient();
  const [isModalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");

  const locationsQuery = useQuery({
    queryKey: ["locations"],
    queryFn: locationsApi.listLocations,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      locationsApi.createLocation(
        name.trim(),
        description.trim() || undefined,
        latitude.trim() ? Number(latitude) : undefined,
        longitude.trim() ? Number(longitude) : undefined
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["locations"] });
      setModalOpen(false);
      setName("");
      setDescription("");
      setLatitude("");
      setLongitude("");
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo crear la ubicación";
      Alert.alert("Error", message);
    },
  });

  return (
    <View style={styles.container}>
      <FlatList
        data={locationsQuery.data ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={locationsQuery.isRefetching} onRefresh={locationsQuery.refetch} />
        }
        ListEmptyComponent={
          !locationsQuery.isLoading ? (
            <Text style={styles.empty}>Todavía no tienes ninguna ubicación — crea la primera.</Text>
          ) : null
        }
        renderItem={({ item }) => (
          <Pressable
            style={styles.card}
            onPress={() => navigation.navigate("LocationDetail", { locationId: item.id, locationName: item.name })}
          >
            <Text style={styles.cardTitle}>{item.name}</Text>
            {item.description ? <Text style={styles.cardSubtitle}>{item.description}</Text> : null}
          </Pressable>
        )}
      />

      {locationsQuery.isLoading ? <ActivityIndicator style={styles.loading} /> : null}

      <Pressable style={styles.fab} onPress={() => setModalOpen(true)}>
        <Text style={styles.fabText}>+</Text>
      </Pressable>

      <Modal visible={isModalOpen} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Nueva ubicación</Text>
            <TextInput style={styles.input} placeholder="Nombre" value={name} onChangeText={setName} />
            <TextInput
              style={styles.input}
              placeholder="Descripción (opcional)"
              value={description}
              onChangeText={setDescription}
            />
            <TextInput
              style={styles.input}
              placeholder="Latitud (opcional, para exteriores)"
              value={latitude}
              onChangeText={setLatitude}
              keyboardType="numeric"
            />
            <TextInput
              style={styles.input}
              placeholder="Longitud (opcional, para exteriores)"
              value={longitude}
              onChangeText={setLongitude}
              keyboardType="numeric"
            />
            <View style={styles.modalActions}>
              <Pressable onPress={() => setModalOpen(false)}>
                <Text style={styles.cancel}>Cancelar</Text>
              </Pressable>
              <Pressable
                style={[styles.createButton, !name && styles.buttonDisabled]}
                disabled={!name || createMutation.isPending}
                onPress={() => createMutation.mutate()}
              >
                {createMutation.isPending ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.createButtonText}>Crear</Text>
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
  card: {
    backgroundColor: "#f4f6f4",
    borderRadius: 10,
    padding: 16,
    marginBottom: 10,
  },
  cardTitle: { fontSize: 17, fontWeight: "600" },
  cardSubtitle: { fontSize: 14, color: "#666", marginTop: 4 },
  fab: {
    position: "absolute",
    right: 20,
    bottom: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#2e7d32",
    alignItems: "center",
    justifyContent: "center",
    elevation: 4,
  },
  fabText: { color: "#fff", fontSize: 28, lineHeight: 30 },
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  modalCard: { backgroundColor: "#fff", borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 20 },
  modalTitle: { fontSize: 18, fontWeight: "700", marginBottom: 16 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 16 },
  modalActions: { flexDirection: "row", justifyContent: "flex-end", alignItems: "center", gap: 16 },
  cancel: { color: "#666", fontSize: 16, marginRight: 8 },
  createButton: { backgroundColor: "#2e7d32", borderRadius: 8, paddingVertical: 10, paddingHorizontal: 20 },
  buttonDisabled: { opacity: 0.5 },
  createButtonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
