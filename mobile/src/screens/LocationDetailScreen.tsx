import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";

import * as devicesApi from "../api/devices";
import DeviceCard from "../components/DeviceCard";
import type { LocationsStackParamList } from "../navigation/LocationsStack";

type Props = NativeStackScreenProps<LocationsStackParamList, "LocationDetail">;

export default function LocationDetailScreen({ route, navigation }: Props) {
  const { locationId } = route.params;

  const devicesQuery = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.listDevices,
  });

  const devicesHere = (devicesQuery.data ?? []).filter((d) => d.location_id === locationId);

  return (
    <View style={styles.container}>
      <FlatList
        data={devicesHere}
        keyExtractor={(item) => item.device_id}
        contentContainerStyle={styles.list}
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
        <Text style={styles.claimButtonText}>+ Reclamar dispositivo</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  list: { padding: 16 },
  empty: { textAlign: "center", color: "#888", marginTop: 40 },
  loading: { marginTop: 20 },
  claimButton: {
    backgroundColor: "#2e7d32",
    margin: 16,
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
  },
  claimButtonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
});
