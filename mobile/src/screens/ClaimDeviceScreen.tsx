import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import { ApiError } from "../api/client";
import type { LocationsStackParamList } from "../navigation/LocationsStack";

type Props = NativeStackScreenProps<LocationsStackParamList, "ClaimDevice">;

export default function ClaimDeviceScreen({ route, navigation }: Props) {
  const { locationId } = route.params;
  const queryClient = useQueryClient();
  const [deviceId, setDeviceId] = useState("");
  const [claimCode, setClaimCode] = useState("");
  const [plantName, setPlantName] = useState("");

  const claimMutation = useMutation({
    mutationFn: async () => {
      await devicesApi.claimDevice(deviceId.trim(), claimCode.trim(), locationId);
      if (plantName.trim()) {
        await devicesApi.renameDevice(deviceId.trim(), plantName.trim());
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      navigation.goBack();
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo reclamar el dispositivo";
      Alert.alert("Error", message);
    },
  });

  return (
    <View style={styles.container}>
      <Text style={styles.hint}>
        Introduce el identificador del dispositivo y el código de reclamación de un solo uso que te dio quien
        administra la plataforma (van pegados en el propio macetero, o te los pasan aparte).
      </Text>

      <Text style={styles.label}>Nombre de la planta (opcional)</Text>
      <TextInput
        style={styles.input}
        placeholder="Ej. Amapola, Gardenia..."
        value={plantName}
        onChangeText={setPlantName}
      />

      <Text style={styles.label}>Identificador del dispositivo</Text>
      <TextInput
        style={styles.input}
        placeholder="Ej. macetero01"
        autoCapitalize="none"
        value={deviceId}
        onChangeText={setDeviceId}
      />

      <Text style={styles.label}>Código de reclamación</Text>
      <TextInput
        style={styles.input}
        placeholder="El código de un solo uso"
        autoCapitalize="none"
        value={claimCode}
        onChangeText={setClaimCode}
      />

      <Pressable
        style={[styles.button, (!deviceId || !claimCode) && styles.buttonDisabled]}
        disabled={!deviceId || !claimCode || claimMutation.isPending}
        onPress={() => claimMutation.mutate()}
      >
        {claimMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Reclamar</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, backgroundColor: "#fff" },
  hint: { color: "#666", marginBottom: 20, lineHeight: 20 },
  label: { fontSize: 13, fontWeight: "600", color: "#444", marginBottom: 6 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 16 },
  button: { backgroundColor: "#2e7d32", borderRadius: 8, padding: 14, alignItems: "center", marginTop: 8 },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
