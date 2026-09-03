import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";

import LocationsStack from "./LocationsStack";
import ProfileScreen from "../screens/ProfileScreen";

export type AppTabsParamList = {
  LocationsTab: undefined;
  Profile: undefined;
};

const Tab = createBottomTabNavigator<AppTabsParamList>();

export default function AppTabs() {
  return (
    <Tab.Navigator screenOptions={{ headerShown: false }}>
      <Tab.Screen name="LocationsTab" component={LocationsStack} options={{ title: "Ubicaciones" }} />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ title: "Perfil", headerShown: true }}
      />
    </Tab.Navigator>
  );
}
