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

  const claimMutation = useMutation({
    mutationFn: () => devicesApi.claimDevice(deviceId.trim(), claimCode.trim(), locationId),
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
        Introduce el `device_id` y el código de reclamación que te dio quien administra la plataforma.
      </Text>

      <TextInput
        style={styles.input}
        placeholder="device_id (ej. macetero01)"
        autoCapitalize="none"
        value={deviceId}
        onChangeText={setDeviceId}
      />
      <TextInput
        style={styles.input}
        placeholder="Código de reclamación"
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
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 16 },
  button: { backgroundColor: "#2e7d32", borderRadius: 8, padding: 14, alignItems: "center", marginTop: 8 },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
