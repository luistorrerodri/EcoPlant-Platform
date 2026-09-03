import { createNativeStackNavigator } from "@react-navigation/native-stack";

import LocationsScreen from "../screens/LocationsScreen";
import LocationDetailScreen from "../screens/LocationDetailScreen";
import ClaimDeviceScreen from "../screens/ClaimDeviceScreen";
import DeviceDetailScreen from "../screens/DeviceDetailScreen";

export type LocationsStackParamList = {
  Locations: undefined;
  LocationDetail: { locationId: string; locationName: string };
  ClaimDevice: { locationId: string };
  DeviceDetail: { deviceId: string };
};

const Stack = createNativeStackNavigator<LocationsStackParamList>();

export default function LocationsStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Locations" component={LocationsScreen} options={{ title: "Ubicaciones" }} />
      <Stack.Screen
        name="LocationDetail"
        component={LocationDetailScreen}
        options={({ route }) => ({ title: route.params.locationName })}
      />
      <Stack.Screen name="ClaimDevice" component={ClaimDeviceScreen} options={{ title: "Reclamar dispositivo" }} />
      <Stack.Screen name="DeviceDetail" component={DeviceDetailScreen} options={{ title: "Dispositivo" }} />
    </Stack.Navigator>
  );
}
