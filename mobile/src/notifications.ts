import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { Platform } from "react-native";

import { registerPushToken } from "./api/notifications";

// Comportamiento cuando llega una notificacion con la app en primer
// plano: se muestra igualmente (banner + sonido), en vez del
// comportamiento por defecto de ignorarla en foreground.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

// Se llama tras cada login/registro con exito. Si el permiso se
// deniega o falla por lo que sea, no bloquea el resto de la app - las
// notificaciones son una mejora, no un requisito para usarla.
export async function registerForPushNotifications(): Promise<void> {
  try {
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "default",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;
    if (existingStatus !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== "granted") return;

    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    const { data: pushToken } = await Notifications.getExpoPushTokenAsync({ projectId });

    await registerPushToken(pushToken);
  } catch (err) {
    console.warn("No se pudo registrar el token de notificaciones push:", err);
  }
}
