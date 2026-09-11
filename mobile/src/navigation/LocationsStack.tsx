import { createNativeStackNavigator } from "@react-navigation/native-stack";

import LocationsScreen from "../screens/LocationsScreen";
import LocationDetailScreen from "../screens/LocationDetailScreen";
import ClaimDeviceScreen from "../screens/ClaimDeviceScreen";
import DeviceDetailScreen from "../screens/DeviceDetailScreen";
import DeviceConfigScreen from "../screens/DeviceConfigScreen";
import DeviceHealthScreen from "../screens/DeviceHealthScreen";
import CalibrateSoilSensorScreen from "../screens/CalibrateSoilSensorScreen";

export type LocationsStackParamList = {
  Locations: undefined;
  LocationDetail: { locationId: string; locationName: string };
  ClaimDevice: { locationId: string };
  DeviceDetail: { deviceId: string };
  DeviceConfig: { deviceId: string };
  DeviceHealth: { deviceId: string };
  CalibrateSoilSensor: { deviceId: string };
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
      <Stack.Screen name="ClaimDevice" component={ClaimDeviceScreen} options={{ title: "Añadir dispositivo" }} />
      <Stack.Screen name="DeviceDetail" component={DeviceDetailScreen} options={{ title: "Dispositivo" }} />
      <Stack.Screen name="DeviceConfig" component={DeviceConfigScreen} options={{ title: "Configuración" }} />
      <Stack.Screen name="DeviceHealth" component={DeviceHealthScreen} options={{ title: "Salud de la planta" }} />
      <Stack.Screen
        name="CalibrateSoilSensor"
        component={CalibrateSoilSensorScreen}
        options={{ title: "Calibrar sensor" }}
      />
    </Stack.Navigator>
  );
}
