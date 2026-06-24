/**
 * Notifications push (FCM via Firebase).
 *
 * Le backend envoie les push avec le SDK Firebase Admin (token FCM NATIF, pas
 * un token Expo) → on utilise `getDevicePushTokenAsync()` et on enregistre le
 * token côté backend (PUT /patients/me/device-token).
 */

import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { registerDeviceToken } from "./api";

/** Affiche les notifications reçues quand l'app est au premier plan. */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/**
 * Demande la permission, récupère le token FCM natif et l'enregistre.
 * Sans effet sur émulateur (pas de Play Services). Échoue en silence — le push
 * est best-effort, il ne doit jamais bloquer l'app.
 */
export async function registerForPush(): Promise<void> {
  try {
    if (!Device.isDevice) return; // émulateur → pas de token FCM

    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;
    if (existing !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== "granted") return;

    // Canal Android obligatoire pour afficher les notifications.
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "Mood-IoT",
        importance: Notifications.AndroidImportance.HIGH,
      });
    }

    const tokenResp = await Notifications.getDevicePushTokenAsync();
    const token = tokenResp?.data ? String(tokenResp.data) : "";
    if (token) {
      await registerDeviceToken(token);
    }
  } catch (e) {
    console.warn("[push] registerForPush error:", e);
  }
}
