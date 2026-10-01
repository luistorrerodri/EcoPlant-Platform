import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";

import * as devicesApi from "../api/devices";
import { ApiError } from "../api/client";
import type { LocationsStackParamList } from "../navigation/LocationsStack";
import type { HealthVerdict, PhotoVerdict } from "../types/api";

type Props = NativeStackScreenProps<LocationsStackParamList, "DeviceHealth">;

const VERDICT_INFO: Record<HealthVerdict, { icon: string; label: string; color: string }> = {
  sana: { icon: "✅", label: "Sana", color: "#2e7d32" },
  revisar_riego: { icon: "💧", label: "Revisar riego", color: "#e65100" },
  revisar_drenaje: { icon: "⚠️", label: "Revisar drenaje", color: "#c62828" },
  datos_insuficientes: { icon: "⏳", label: "Sin datos suficientes", color: "#888" },
};

const PHOTO_VERDICT_INFO: Record<PhotoVerdict, { icon: string; label: string; color: string }> = {
  bien: { icon: "🌿", label: "Bien", color: "#2e7d32" },
  revisar: { icon: "🔍", label: "Revisar", color: "#e65100" },
  preocupante: { icon: "🚨", label: "Preocupante", color: "#c62828" },
};

function formatPct(value: number | null): string {
  return value != null ? `${(value * 100).toFixed(0)}%` : "—";
}

type MergedDiagnosis = {
  icon: string;
  label: string;
  color: string;
  message: string;
  source: "foto" | "sensores";
  createdAt: string;
};

// La foto siempre gana cuando existe: el propio prompt de la IA (ver
// plant_vision.py) ya le pide que mezcle foto + sensores en un unico
// mensaje y marque contradicciones - no hace falta "mezclar" nada aqui,
// solo elegir que tarjeta mostrar. Si no hay ninguna foto analizada
// todavia (o la unica que hubo nunca llego a analizarse con exito), cae
// al diagnostico por sensores. Un intento de foto fallido no borra una
// foto anterior valida - photoQuery simplemente no cambia si el POST falla.
function mergeDiagnosis(
  photoDiagnosis: { verdict: PhotoVerdict; message: string; created_at: string } | undefined,
  summary: { verdict: HealthVerdict; message: string; created_at: string } | undefined
): MergedDiagnosis | null {
  if (photoDiagnosis) {
    const info = PHOTO_VERDICT_INFO[photoDiagnosis.verdict];
    return { ...info, message: photoDiagnosis.message, source: "foto", createdAt: photoDiagnosis.created_at };
  }
  if (summary) {
    const info = VERDICT_INFO[summary.verdict];
    return { ...info, message: summary.message, source: "sensores", createdAt: summary.created_at };
  }
  return null;
}

export default function DeviceHealthScreen({ route }: Props) {
  const { deviceId } = route.params;
  const queryClient = useQueryClient();

  const summaryQuery = useQuery({
    queryKey: ["health-summary", deviceId],
    queryFn: () => devicesApi.getHealthSummary(deviceId),
    retry: false,
  });

  const refreshMutation = useMutation({
    mutationFn: () => devicesApi.refreshHealthSummary(deviceId),
    onSuccess: (data) => {
      queryClient.setQueryData(["health-summary", deviceId], data);
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.detail : "No se pudo calcular el resumen";
      Alert.alert("Error", message);
    },
  });

  const notFound = summaryQuery.isError && summaryQuery.error instanceof ApiError && summaryQuery.error.status === 404;
  const summary = summaryQuery.data;

  const photoQuery = useQuery({
    queryKey: ["photo-diagnosis", deviceId],
    queryFn: () => devicesApi.getPhotoDiagnosis(deviceId),
    retry: false,
  });
  const photoNotFound =
    photoQuery.isError && photoQuery.error instanceof ApiError && photoQuery.error.status === 404;
  const photoDiagnosis = photoQuery.data;

  const [imageSource, setImageSource] = useState<{ uri: string } | null>(null);
  useEffect(() => {
    if (photoDiagnosis) {
      devicesApi.getPhotoDiagnosisImageSource(deviceId, photoDiagnosis.created_at).then(setImageSource);
    } else {
      setImageSource(null);
    }
  }, [deviceId, photoDiagnosis]);

  const photoMutation = useMutation({
    mutationFn: (photoUri: string) => devicesApi.submitPhotoDiagnosis(deviceId, photoUri),
    onSuccess: (data) => {
      queryClient.setQueryData(["photo-diagnosis", deviceId], data);
    },
    onError: (err) => {
      // eslint-disable-next-line no-console
      console.error("submitPhotoDiagnosis failed:", err);
      const message = err instanceof ApiError ? err.detail : `No se pudo analizar la foto: ${String((err as Error)?.message ?? err)}`;
      Alert.alert("Error", message);
    },
  });

  async function handlePickPhoto(source: "camera" | "library") {
    const permission =
      source === "camera"
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(
        "Permiso necesario",
        source === "camera" ? "Necesitamos acceso a la cámara." : "Necesitamos acceso a tus fotos."
      );
      return;
    }
    const result =
      source === "camera"
        ? await ImagePicker.launchCameraAsync({ quality: 0.7 })
        : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7 });
    if (result.canceled) return;
    photoMutation.mutate(result.assets[0].uri);
  }

  function handleUpdatePhoto() {
    Alert.alert("Actualizar foto", "¿Cómo quieres añadir la foto?", [
      { text: "Hacer foto", onPress: () => handlePickPhoto("camera") },
      { text: "Elegir de la galería", onPress: () => handlePickPhoto("library") },
      { text: "Cancelar", style: "cancel" },
    ]);
  }

  if (summaryQuery.isLoading || photoQuery.isLoading) {
    return <ActivityIndicator style={styles.loading} />;
  }

  const diagnosis = mergeDiagnosis(
    photoNotFound ? undefined : photoDiagnosis,
    notFound ? undefined : summary
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {!diagnosis ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>
            Todavía no hay ningún diagnóstico para este dispositivo. Se genera automáticamente a partir
            de los sensores cada unos días, puedes calcularlo ahora mismo, o subir una foto para un
            diagnóstico más completo.
          </Text>
        </View>
      ) : (
        <>
          <View style={[styles.verdictCard, { borderColor: diagnosis.color }]}>
            <Text style={styles.verdictIcon}>{diagnosis.icon}</Text>
            <Text style={[styles.verdictLabel, { color: diagnosis.color }]}>{diagnosis.label}</Text>
            <Text style={styles.sourceTag}>
              {diagnosis.source === "foto"
                ? "📷 Basado en tu última foto + los sensores"
                : "🌿 Basado en los sensores — sube una foto para un diagnóstico más completo"}
            </Text>
            <Text style={styles.message}>{diagnosis.message}</Text>
          </View>

          {summary && summary.verdict !== "datos_insuficientes" ? (
            <View style={styles.statsGrid}>
              <View style={styles.statBox}>
                <Text style={styles.statValue}>{summary.num_riegos ?? "—"}</Text>
                <Text style={styles.statLabel}>Riegos en {summary.window_days} días</Text>
              </View>
              <View style={styles.statBox}>
                <Text style={styles.statValue}>{formatPct(summary.pct_tiempo_bajo_minimo)}</Text>
                <Text style={styles.statLabel}>Tiempo bajo el mínimo</Text>
              </View>
              <View style={styles.statBox}>
                <Text style={styles.statValue}>{formatPct(summary.pct_tiempo_saturado)}</Text>
                <Text style={styles.statLabel}>Tiempo saturado</Text>
              </View>
              <View style={styles.statBox}>
                <Text style={styles.statValue}>
                  {summary.tiempo_recuperacion_medio_h != null
                    ? `${summary.tiempo_recuperacion_medio_h.toFixed(0)}h`
                    : "—"}
                </Text>
                <Text style={styles.statLabel}>Recuperación media tras regar</Text>
              </View>
              <View style={styles.statBox}>
                <Text style={styles.statValue}>
                  {summary.tasa_secado_pct_h != null ? `${summary.tasa_secado_pct_h.toFixed(2)}%/h` : "—"}
                </Text>
                <Text style={styles.statLabel}>Ritmo de secado</Text>
              </View>
              {summary.temp_suelo_min != null && summary.temp_suelo_max != null ? (
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>
                    {summary.temp_suelo_min.toFixed(1)}–{summary.temp_suelo_max.toFixed(1)}°C
                  </Text>
                  <Text style={styles.statLabel}>Rango temp. suelo</Text>
                </View>
              ) : null}
              {summary.temp_aire_min != null && summary.temp_aire_max != null ? (
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>
                    {summary.temp_aire_min.toFixed(1)}–{summary.temp_aire_max.toFixed(1)}°C
                  </Text>
                  <Text style={styles.statLabel}>Rango temp. aire</Text>
                </View>
              ) : null}
            </View>
          ) : null}

          <Text style={styles.updatedAt}>
            {diagnosis.source === "foto" ? "Foto del " : "Calculado el "}
            {new Date(diagnosis.createdAt).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
          </Text>
        </>
      )}

      <Pressable
        style={[styles.refreshButton, refreshMutation.isPending && styles.buttonDisabled]}
        disabled={refreshMutation.isPending}
        onPress={() => refreshMutation.mutate()}
      >
        {refreshMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.refreshButtonText}>
            {notFound || !summary ? "Calcular por sensores ahora" : "🔄 Recalcular por sensores"}
          </Text>
        )}
      </Pressable>

      <View style={styles.divider} />
      <Text style={styles.sectionTitle}>📷 Foto de la planta</Text>
      <Text style={styles.sectionIntro}>
        Sube una foto para que el diagnóstico de arriba también tenga en cuenta cosas que ningún sensor
        puede ver — hojas amarillas, plaga, marchitez. Compara con la foto anterior si ya habías subido una.
      </Text>

      {photoQuery.isLoading ? (
        <ActivityIndicator style={styles.loading} />
      ) : photoNotFound || !photoDiagnosis ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>Todavía no has subido ninguna foto de esta planta.</Text>
        </View>
      ) : (
        <>
          {imageSource ? <Image source={imageSource} style={styles.photoThumbnail} /> : null}
          <Text style={styles.updatedAt}>
            Última foto del{" "}
            {new Date(photoDiagnosis.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
            {" — su diagnóstico es el que ves arriba"}
          </Text>
        </>
      )}

      <Pressable
        style={[styles.refreshButton, photoMutation.isPending && styles.buttonDisabled]}
        disabled={photoMutation.isPending}
        onPress={handleUpdatePhoto}
      >
        {photoMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.refreshButtonText}>📷 Actualizar foto</Text>
        )}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20 },
  loading: { marginTop: 40 },
  empty: { padding: 12, marginBottom: 20 },
  emptyText: { color: "#666", fontSize: 15, lineHeight: 22 },
  verdictCard: {
    borderWidth: 2,
    borderRadius: 12,
    padding: 20,
    alignItems: "center",
    marginBottom: 20,
  },
  verdictIcon: { fontSize: 40, marginBottom: 8 },
  verdictLabel: { fontSize: 20, fontWeight: "700", marginBottom: 4 },
  sourceTag: { fontSize: 11.5, color: "#999", marginBottom: 10, textAlign: "center" },
  message: { fontSize: 15, color: "#444", textAlign: "center", lineHeight: 21 },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginBottom: 16 },
  statBox: {
    flexBasis: "47%",
    backgroundColor: "#f4f6f4",
    borderRadius: 10,
    padding: 14,
  },
  statValue: { fontSize: 18, fontWeight: "700", color: "#2e7d32" },
  statLabel: { fontSize: 12, color: "#777", marginTop: 4 },
  updatedAt: { fontSize: 12, color: "#aaa", textAlign: "center", marginBottom: 20 },
  refreshButton: {
    backgroundColor: "#2e7d32",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  buttonDisabled: { opacity: 0.5 },
  refreshButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  divider: { height: 1, backgroundColor: "#eee", marginVertical: 24 },
  sectionTitle: { fontSize: 18, fontWeight: "700", color: "#333", marginBottom: 6 },
  sectionIntro: { fontSize: 13.5, color: "#777", lineHeight: 19, marginBottom: 16 },
  photoThumbnail: {
    width: "100%",
    aspectRatio: 4 / 3,
    borderRadius: 10,
    marginBottom: 16,
    backgroundColor: "#f0f0f0",
  },
});
