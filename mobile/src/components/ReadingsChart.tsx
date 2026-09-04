import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { LineChart } from "react-native-gifted-charts";
import type { ReadingPoint } from "../types/api";

const FIELD_LABELS: Record<ReadingPoint["field"], string> = {
  humedad_suelo: "Humedad de suelo (%)",
  temp_aire: "Temperatura (°C)",
  presion: "Presión (hPa)",
};

const LINE_COLOR = "#2e7d32";
// Maximo de puntos que se dibujan de verdad - mas puntos de los que hacen
// falta para que la curva se vea bien no aportan nada y solo apretujan
// el grafico.
const MAX_POINTS = 30;
// Numero de marcas de hora bajo el grafico - se dibujan aparte del propio
// grafico (ver mas abajo) porque las etiquetas del eje X de la libreria
// reservan un ancho por punto y truncan el texto con puntos suspensivos
// en cuanto hay mas de un puñado de puntos.
const TIME_MARKS = 4;

function downsample(points: ReadingPoint[], max: number): ReadingPoint[] {
  if (points.length <= max) return points;
  const step = points.length / max;
  const result: ReadingPoint[] = [];
  for (let i = 0; i < max; i++) {
    result.push(points[Math.floor(i * step)]);
  }
  result.push(points[points.length - 1]);
  return result;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function ReadingsChart({
  points,
  field,
}: {
  points: ReadingPoint[];
  field: ReadingPoint["field"];
}) {
  // El ancho real disponible se mide con onLayout en vez de calcularse a
  // partir de Dimensions.get("window") - ese calculo dependia de adivinar
  // el padding exacto del contenedor padre y se desincronizaba en cuanto
  // cambiaba el layout, cortando el grafico por la derecha.
  const [containerWidth, setContainerWidth] = useState(0);

  const fieldPoints = downsample(
    points.filter((p) => p.field === field),
    MAX_POINTS
  );

  if (fieldPoints.length < 2) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>Todavía no hay suficientes datos para graficar.</Text>
      </View>
    );
  }

  const data = fieldPoints.map((p) => ({ value: p.value }));

  const markStep = Math.max(1, Math.floor((fieldPoints.length - 1) / (TIME_MARKS - 1)));
  const timeMarks = fieldPoints.filter((_, i) => i % markStep === 0 || i === fieldPoints.length - 1).slice(0, TIME_MARKS);

  // El eje Y empieza en 0 por defecto, lo cual aplasta campos como
  // presion (valores siempre cerca de 1013) contra el borde superior.
  // Se calcula un rango ajustado a los datos reales, con un margen para
  // que la curva no toque los bordes.
  const values = fieldPoints.map((p) => p.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const padding = Math.max((maxValue - minValue) * 0.15, 0.5);
  const yAxisOffset = Math.floor(minValue - padding);
  const yAxisMax = Math.ceil(maxValue + padding) - yAxisOffset;

  return (
    <View style={styles.container} onLayout={(e) => setContainerWidth(e.nativeEvent.layout.width)}>
      <Text style={styles.title}>{FIELD_LABELS[field]}</Text>
      {containerWidth > 0 ? (
        <>
          <LineChart
            data={data}
            width={containerWidth - 36}
            height={180}
            curved
            areaChart
            color={LINE_COLOR}
            thickness={3}
            startFillColor={LINE_COLOR}
            endFillColor={LINE_COLOR}
            startOpacity={0.25}
            endOpacity={0.02}
            hideDataPoints
            hideRules
            xAxisColor="#e0e0e0"
            yAxisColor="transparent"
            yAxisTextStyle={{ color: "#999", fontSize: 11 }}
            initialSpacing={10}
            endSpacing={10}
            noOfSections={4}
            adjustToWidth
            xAxisLabelTexts={fieldPoints.map(() => "")}
            yAxisOffset={yAxisOffset}
            maxValue={yAxisMax}
          />
          <View style={styles.timeRow}>
            {timeMarks.map((p, i) => (
              <Text key={i} style={styles.timeText}>
                {formatTime(p.time)}
              </Text>
            ))}
          </View>
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: 16 },
  title: { fontSize: 15, fontWeight: "600", marginBottom: 8 },
  timeRow: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 6, marginTop: 2 },
  timeText: { fontSize: 11, color: "#999" },
  empty: { padding: 20, alignItems: "center" },
  emptyText: { color: "#888" },
});
