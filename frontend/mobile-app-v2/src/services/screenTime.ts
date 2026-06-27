/**
 * Bridge JS → module natif ScreenTimeModule (Android uniquement).
 *
 * Setup :
 * 1. Copie ScreenTimeModule.kt et ScreenTimePackage.kt dans
 *    android/app/src/main/java/com/santeconnectv2/
 *
 * 2. Dans android/app/src/main/java/com/santeconnectv2/MainApplication.kt,
 *    ajoute dans getPackages() :
 *      packages.add(ScreenTimePackage())
 *
 * 3. Dans AndroidManifest.xml, ajoute dans <manifest> :
 *    <uses-permission
 *      android:name="android.permission.PACKAGE_USAGE_STATS"
 *      tools:ignore="ProtectedPermissions" />
 *
 *    Et en haut du manifest :
 *    xmlns:tools="http://schemas.android.com/tools"
 */

import { NativeModules, Platform } from 'react-native';

const { ScreenTimeModule } = NativeModules;

export interface ScreenTimeService {
  /** Temps d'écran du jour en heures. Retourne -1 si permission manquante. */
  getDailyScreenTime(): Promise<number>;
  /** Vérifie si la permission PACKAGE_USAGE_STATS est accordée. */
  hasPermission(): Promise<boolean>;
  /** Ouvre les paramètres d'accès à l'utilisation des apps. */
  openPermissionSettings(): Promise<void>;
}

function notAvailable(): Promise<any> {
  return Promise.resolve(-1);
}

export const screenTime: ScreenTimeService =
  Platform.OS === 'android' && ScreenTimeModule
    ? {
        getDailyScreenTime: () => ScreenTimeModule.getDailyScreenTime(),
        hasPermission:      () => ScreenTimeModule.hasPermission(),
        openPermissionSettings: () => ScreenTimeModule.openPermissionSettings(),
      }
    : {
        getDailyScreenTime:     notAvailable,
        hasPermission:          () => Promise.resolve(false),
        openPermissionSettings: notAvailable,
      };