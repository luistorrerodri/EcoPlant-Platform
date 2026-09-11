import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import { ApiError } from "../api/client";
import type { LocationsStackParamList } from "../navigation/LocationsStack";
import type { HealthVerdict } from "../types/api";

type Props = NativeStackScreenProps<LocationsStackParamList, "DeviceHealth">;

const VERDICT_INFO: Record<HealthVerdict, { icon: string; label: string; color: string }> = {
  sana: { icon: "✅", label: "Sana", color: "#2e7d32" },
  revisar_riego: { icon: "💧", label: "Revisar riego", color: "#e65100" },
  revisar_drenaje: { icon: "⚠️", label: "Revisar drenaje", color: "#c62828" },
  datos_insuficientes: { icon: "⏳", label: "Sin datos suficientes", color: "#888" },
};

function formatPct(value: number | null): string {
  return value != null ? `${(value * 100).toFixed(0)}%` : "—";
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

  if (summaryQuery.isLoading) {
    return <ActivityIndicator style={styles.loading} />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {notFound || !summary ? (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>
            Todavía no hay ningún resumen de salud para este dispositivo. Se genera automáticamente cada
            unos días, o puedes calcularlo ahora mismo.
          </Text>
        </View>
      ) : (
        <>
          <View style={[styles.verdictCard, { borderColor: VERDICT_INFO[summary.verdict].color }]}>
            <Text style={styles.verdictIcon}>{VERDICT_INFO[summary.verdict].icon}</Text>
            <Text style={[styles.verdictLabel, { color: VERDICT_INFO[summary.verdict].color }]}>
              {VERDICT_INFO[summary.verdict].label}
            </Text>
            <Text style={styles.message}>{summary.message}</Text>
          </View>

          {summary.verdict !== "datos_insuficientes" ? (
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
            Calculado el {new Date(summary.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
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
            {notFound || !summary ? "Calcular ahora" : "🔄 Recalcular ahora"}
          </Text>
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
  verdictLabel: { fontSize: 20, fontWeight: "700", marginBottom: 10 },
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
});
