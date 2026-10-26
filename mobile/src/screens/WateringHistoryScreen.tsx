import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import type { LocationsStackParamList } from "../navigation/LocationsStack";
import type { WateringEventOut } from "../types/api";
import { timeAgo } from "../utils/time";

type Props = NativeStackScreenProps<LocationsStackParamList, "WateringHistory">;

const ORIGEN_LABELS: Record<string, { text: string; color: string; background: string }> = {
  manual: { text: "Manual", color: "#1565c0", background: "#e3f0fc" },
  automatico: { text: "Automático", color: "#2e7d32", background: "#e6f2e6" },
};

function formatDuration(ms: number): string {
  const seconds = ms / 1000;
  return `${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)} s`;
}

function EventRow({ event }: { event: WateringEventOut }) {
  const origen = event.origen ? ORIGEN_LABELS[event.origen] : null;
  return (
    <View style={styles.row}>
      <View style={styles.rowMain}>
        <Text style={styles.date}>
          {new Date(event.timestamp).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
        </Text>
        <Text style={styles.ago}>{timeAgo(event.timestamp)}</Text>
      </View>
      <View style={styles.rowSide}>
        <Text style={styles.duration}>💧 {formatDuration(event.duration_ms)}</Text>
        {origen ? (
          <Text style={[styles.badge, { color: origen.color, backgroundColor: origen.background }]}>
            {origen.text}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

export default function WateringHistoryScreen({ route }: Props) {
  const { deviceId } = route.params;

  const eventsQuery = useQuery({
    queryKey: ["watering-events", deviceId],
    queryFn: () => devicesApi.getWateringEvents(deviceId),
  });

  if (eventsQuery.isLoading) {
    return <ActivityIndicator style={styles.loading} />;
  }

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={eventsQuery.data ?? []}
      keyExtractor={(item) => item.timestamp}
      refreshControl={
        <RefreshControl refreshing={eventsQuery.isRefetching} onRefresh={() => eventsQuery.refetch()} />
      }
      ListHeaderComponent={
        eventsQuery.data && eventsQuery.data.length > 0 ? (
          <Text style={styles.intro}>Últimos {eventsQuery.data.length} riegos, del más reciente al más antiguo.</Text>
        ) : null
      }
      ListEmptyComponent={
        <Text style={styles.empty}>
          {eventsQuery.isError
            ? "No se pudo cargar el historial. Desliza hacia abajo para reintentar."
            : "Todavía no hay ningún riego registrado."}
        </Text>
      }
      renderItem={({ item }) => <EventRow event={item} />}
      ListFooterComponent={
        eventsQuery.data && eventsQuery.data.some((e) => e.origen === null) ? (
          <Text style={styles.footnote}>
            Los riegos sin etiqueta son anteriores a que la app registrara si fueron manuales o automáticos.
          </Text>
        ) : null
      }
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20 },
  loading: { marginTop: 40 },
  intro: { fontSize: 13.5, color: "#777", marginBottom: 14 },
  empty: { color: "#888", fontSize: 15, lineHeight: 22, textAlign: "center", marginTop: 30 },
  footnote: { fontSize: 12, color: "#aaa", marginTop: 12, textAlign: "center", lineHeight: 17 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#f4f6f4",
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
  },
  rowMain: { flexShrink: 1, paddingRight: 10 },
  rowSide: { alignItems: "flex-end", gap: 6 },
  date: { fontSize: 15, fontWeight: "600", color: "#333" },
  ago: { fontSize: 12.5, color: "#888", marginTop: 2 },
  duration: { fontSize: 15, fontWeight: "600", color: "#1565c0" },
  badge: { fontSize: 11.5, fontWeight: "700", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, overflow: "hidden" },
});
