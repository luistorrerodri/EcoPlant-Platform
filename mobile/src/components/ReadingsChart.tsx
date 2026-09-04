import { Dimensions, StyleSheet, Text, View } from "react-native";
import { LineChart } from "react-native-chart-kit";
import type { ReadingPoint } from "../types/api";

const FIELD_LABELS: Record<ReadingPoint["field"], string> = {
  humedad_suelo: "Humedad de suelo (%)",
  temp_aire: "Temperatura (°C)",
  presion: "Presión (hPa)",
};

export default function ReadingsChart({
  points,
  field,
}: {
  points: ReadingPoint[];
  field: ReadingPoint["field"];
}) {
  const fieldPoints = points.filter((p) => p.field === field);

  if (fieldPoints.length < 2) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>Todavía no hay suficientes datos para graficar.</Text>
      </View>
    );
  }

  // Como maximo ~12 etiquetas en el eje X para que no se amontonen.
  const step = Math.max(1, Math.floor(fieldPoints.length / 6));
  const labels = fieldPoints.map((p, i) =>
    i % step === 0 ? new Date(p.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""
  );

  return (
    <View>
      <Text style={styles.title}>{FIELD_LABELS[field]}</Text>
      <LineChart
        data={{ labels, datasets: [{ data: fieldPoints.map((p) => p.value) }] }}
        width={Dimensions.get("window").width - 40}
        height={200}
        yAxisSuffix=""
        chartConfig={{
          backgroundColor: "#fff",
          backgroundGradientFrom: "#fff",
          backgroundGradientTo: "#fff",
          decimalPlaces: 1,
          color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`,
          labelColor: (opacity = 1) => `rgba(60, 60, 60, ${opacity})`,
          propsForDots: { r: "2" },
        }}
        bezier
        style={styles.chart}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 15, fontWeight: "600", marginTop: 16, marginBottom: 4 },
  chart: { borderRadius: 8 },
  empty: { padding: 20, alignItems: "center" },
  emptyText: { color: "#888" },
});
